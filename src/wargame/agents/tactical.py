"""战术Agent层（v6）：一线作战单元的局部自主智能。

与司令部Agent（走消息总线、有延迟、有摩擦）不同，战术Agent直接绑定
到世界引擎中的 Unit，拥有：
  1. 本地即时感知 —— 直接读 world 周边状态，视线内敌情无需报文流转
  2. 局部自主行动 —— 遇敌接战、受创后撤、迂回、休整、重组、火力协同
  3. 异步上报 —— 关键事件整理成报告走 bus 上报，带通信延迟

v6 增强：
  - LLM 驱动支持（可选）：战术分队也可由大模型决策，规则作兜底
  - LLM 节流：每 N 拍唤醒一次，重要事件立即唤醒，控制成本
  - 更多战术行为：夜间保守、疲劳休整、士气重组、迂回机动、火力协同请示
  - 状态机扩展：推进/接战/防御/后撤/待命/休整/溃退/重组
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..engine.world import Unit, World
from ..schemas import MsgKind, WorldAction

if TYPE_CHECKING:
    from ..bus import Bus
    from ..llm import LLMClient
    from ..org import Registry

# 战术Agent状态机
TACT_STATES = {
    "advancing": "推进中",
    "engaging": "接战中",
    "defending": "防御中",
    "withdrawing": "后撤中",
    "holding": "待命",
    "resting": "休整中",
    "reorganizing": "重组中",
    "destroyed": "全损",
}
TACT_CN = {
    "attack": "攻击", "move": "机动", "entrench": "筑垒",
    "hold": "待命", "retreat": "后撤", "rest": "休整",
}


@dataclass
class TacticalAgent:
    """绑定到一个作战 Unit 的轻量战术智能体。"""
    unit_id: str
    side: str
    owner_pos: str  # 上级指挥官职位 id（用于上报）
    state: str = "holding"
    last_report_tick: int = -99
    last_contact_tick: int = -99
    contact_foes: list[str] = field(default_factory=list)
    withdrew: bool = False
    last_llm_tick: int = -99
    memory: list[str] = field(default_factory=list)  # 近期感知/决策记忆
    last_decision: str = ""  # 最近一次决策摘要（调试用）
    last_thought: str = ""   # LLM 思考摘要
    _tick: int = 0

    # ---- 本地即时感知 ----
    def perceive(self, world: World, radius: int | None = None) -> dict:
        """直接读取 world 获取本地战场态势，不走任何消息总线。"""
        unit = world.units.get(self.unit_id)
        if not unit or not unit.alive:
            return {"enemies": [], "friends": [], "terrain": ".", "surrounded": False,
                    "unit": None, "period": world.period}
        r = radius if radius is not None else max(2, unit.recon + 1)
        enemies, friends = [], []
        for other in world.units.values():
            if not other.alive or other.id == unit.id:
                continue
            dist = abs(other.x - unit.x) + abs(other.y - unit.y)
            if dist <= r:
                if world.at_war(unit.side, other.side):
                    enemies.append({
                        "id": other.id, "name": other.name, "kind": other.kind,
                        "x": other.x, "y": other.y, "strength": round(other.strength),
                        "dist": dist, "entrenched": other.entrenched,
                    })
                elif other.side == unit.side:
                    friends.append({
                        "id": other.id, "name": other.name, "kind": other.kind,
                        "x": other.x, "y": other.y, "strength": round(other.strength),
                    })
        adjacent_enemies = sum(1 for e in enemies if e["dist"] <= 1)
        return {
            "enemies": sorted(enemies, key=lambda e: e["dist"]),
            "friends": friends,
            "terrain": world.terrain(unit.x, unit.y),
            "surrounded": adjacent_enemies >= 2,
            "adjacent_enemies": adjacent_enemies,
            "unit": unit,
            "period": world.period,
            "unit_strength": round(unit.strength) if unit else 0,
            "unit_morale": round(unit.morale) if unit else 0,
            "unit_fatigue": round(unit.fatigue, 1) if unit else 0,
        }

    # ---- 决策入口 ----
    def decide(self, world: World, tick: int, tuning: dict,
               bus: "Bus" | None = None, registry: "Registry" | None = None,
               llm_client: "LLMClient" | None = None,
               llm_interval: int = 4) -> list[WorldAction]:
        """战术决策入口。LLM 可用且到唤醒时机则用 LLM，否则走规则。"""
        self._tick = tick
        unit = world.units.get(self.unit_id)
        if not unit or not unit.alive:
            self.state = "destroyed"
            return []
        perc = self.perceive(world)

        # LLM 驱动：可用且到节流间隔（或重要事件立即唤醒）
        if llm_client is not None and llm_client.available:
            important = (perc["enemies"] and (tick - self.last_contact_tick >= 2)) \
                or (tick - self.last_llm_tick >= llm_interval)
            if important:
                self.last_llm_tick = tick
                return self._llm_decide(world, perc, tuning, bus, registry, llm_client)

        return self._rule_decide(world, perc, tuning, bus, registry)

    # ---- LLM 决策 ----
    def _llm_decide(self, world: World, perc: dict, tuning: dict,
                    bus: "Bus" | None, registry: "Registry" | None,
                    llm_client: "LLMClient") -> list[WorldAction]:
        unit = perc["unit"]
        enemy_lines = "；".join(
            f"{e['name']}({e['kind']})@{e['x']},{e['y']}兵力{e['strength']}距{e['dist']}格"
            for e in perc["enemies"][:5]) or "无"
        friend_lines = "；".join(
            f"{f['name']}@{f['x']},{f['y']}" for f in perc["friends"][:3]) or "无"
        order = (unit.order or {}).get("kind") or "无"
        order_tgt = (unit.order or {}).get("target") or "无"
        system = (
            "你是一名分队指挥员，正在战场上指挥一支作战部队。根据当前态势做出决策。"
            "输出严格 JSON（不要任何其他文字）：\n"
            '{"action":"attack|move|defend|retreat|hold|rest","target":[x,y]或null,'
            '"report":"一句话向团长汇报当前情况（无重要情况则空字符串）"}\n'
            "规则：敌人在相邻格优先 attack；敌人在视距内且己方占优可攻击或前出；"
            "兵力或士气过低选择 retreat 或 defend；疲劳过高且无敌情选择 rest；"
            "有上级命令时遵循上级命令的方向。target 必须为整数坐标。"
        )
        prompt = (
            f"我方部队：{unit.name}（{unit.kind}），位置({unit.x},{unit.y})，"
            f"兵力{perc['unit_strength']}，士气{perc['unit_morale']}，疲劳{perc['unit_fatigue']}，"
            f"地形{perc['terrain']}，时段{perc['period']}。\n"
            f"上级命令：{order} 目标{order_tgt}\n"
            f"视野内敌人：{enemy_lines}\n"
            f"附近友军：{friend_lines}\n"
            f"你被{perc['adjacent_enemies']}个敌人包围。请决策。"
        )
        try:
            raw = llm_client.chat(system, prompt)
            spec = llm_client.extract_json(raw)
            self.last_thought = raw[:120]
        except Exception as exc:  # noqa: BLE001
            self.last_thought = f"LLM失败:{str(exc)[:60]}，回退规则"
            return self._rule_decide(world, perc, tuning, bus, registry)

        actions: list[WorldAction] = []
        action = str(spec.get("action", "hold"))
        report = str(spec.get("report", ""))
        target = spec.get("target")
        if action == "attack" and isinstance(target, list) and len(target) == 2:
            actions.append(WorldAction(kind="attack", unit=unit.id,
                                       target=[int(target[0]), int(target[1])]))
            self.state = "engaging"
        elif action == "move" and isinstance(target, list) and len(target) == 2:
            actions.append(WorldAction(kind="move", unit=unit.id,
                                       target=[int(target[0]), int(target[1])]))
            self.state = "advancing"
        elif action == "defend":
            if not unit.entrenched:
                actions.append(WorldAction(kind="entrench", unit=unit.id))
            self.state = "defending"
        elif action == "retreat":
            retreat = self._retreat_target(unit, perc["enemies"], world)
            if retreat:
                actions.append(WorldAction(kind="move", unit=unit.id, target=retreat))
                self.state = "withdrawing"
            elif not unit.entrenched:
                actions.append(WorldAction(kind="entrench", unit=unit.id))
                self.state = "defending"
        elif action == "rest":
            if unit.order:
                actions.append(WorldAction(kind="hold", unit=unit.id))
            self.state = "resting"
        else:
            self.state = "holding"
        self.last_decision = f"LLM:{action} {target or ''}"
        if report and bus and registry:
            self._send_report(bus, registry, unit, MsgKind.SITREP, "分队报告",
                              report, {"event": "tactical_report", "x": unit.x,
                                       "y": unit.y, "strength": round(unit.strength),
                                       "tactical_state": self.state})
        return actions

    # ---- 规则决策（确定性，离线兜底）----
    def _rule_decide(self, world: World, perc: dict, tuning: dict,
                     bus: "Bus" | None, registry: "Registry" | None) -> list[WorldAction]:
        unit = perc["unit"]
        enemies = perc["enemies"]
        has_order = unit.order is not None
        order_kind = (unit.order or {}).get("kind") if has_order else None
        strength_pct = unit.strength / unit.strength_max if unit.strength_max else 0
        fatigue = unit.fatigue
        morale = unit.morale
        morale_state = unit.morale_state
        is_night = perc["period"] == "night"
        actions: list[WorldAction] = []

        # === 士气崩溃/重组中：不主动行动，等待重组 ===
        if morale_state in ("breaking", "reorg"):
            self.state = "reorganizing"
            self._report_reorg(unit, bus, registry, morale_state)
            return []

        # === 炮兵特殊逻辑：发现射程内敌人自动开火 ===
        if unit.kind == "artillery":
            target = self._artillery_target(unit, enemies, world)
            if target and (not has_order or order_kind != "attack"):
                actions.append(WorldAction(kind="attack", unit=unit.id,
                                           target=[target["x"], target["y"]]))
                self.state = "engaging"
                self._maybe_report_contact(unit, enemies, tick=self._tick,
                                           bus=bus, registry=registry, perc=perc)
            elif not has_order:
                self.state = "holding"
            return actions

        # === 受创严重/士气崩溃：自主后撤或就地防御 ===
        withdraw_thr = float(tuning.get("tactical_withdraw_threshold", 25))
        if (strength_pct * 100 < withdraw_thr or morale < 30) and not self.withdrew:
            if enemies and perc["adjacent_enemies"] > 0:
                # 有敌人贴身：先就地防御扛一轮，下拍再撤
                if not unit.entrenched:
                    actions.append(WorldAction(kind="entrench", unit=unit.id))
                self.state = "defending"
                self.withdrew = True
                self._report_escalation(unit, enemies, self._tick, bus, registry,
                                        "损失过重，就地转入防御", perc)
                return actions
            elif enemies:
                retreat = self._retreat_target(unit, enemies, world)
                if retreat:
                    actions.append(WorldAction(kind="move", unit=unit.id, target=retreat))
                    self.state = "withdrawing"
                    self.withdrew = True
                    self._report_escalation(unit, enemies, self._tick, bus, registry,
                                            "损失过重，自主后撤", perc)
                    return actions

        # === 疲劳过高且无敌情：休整 ===
        if fatigue > 60 and not enemies and not has_order and not unit.entrenched:
            actions.append(WorldAction(kind="hold", unit=unit.id))
            self.state = "resting"
            self._maybe_report(unit, self._tick, bus, registry, tuning,
                               f"部队疲劳，就地休整恢复。")
            return actions

        # === 夜间保守：无强敌不主动接战，倾向防御 ===
        if is_night and not enemies and not has_order and not unit.entrenched:
            self.state = "holding"
            return actions

        # === 遇敌：自主接战 ===
        if enemies:
            nearest = enemies[0]
            # 相邻敌人：自动接战（不需要上级命令）
            if nearest["dist"] <= 1:
                self.state = "engaging"
                self.contact_foes = [e["name"] for e in enemies if e["dist"] <= 1]
                self.last_contact_tick = self._tick
                if has_order and order_kind == "attack":
                    pass  # 继续执行上级攻击命令
                elif not unit.entrenched and not has_order:
                    actions.append(WorldAction(kind="entrench", unit=unit.id))
                    self.state = "defending"
                self._maybe_report_contact(unit, enemies, self._tick, bus, registry, perc)
                return actions

            # 敌人在视距内但未相邻：
            if has_order and order_kind in ("move", "attack"):
                target = unit.order.get("target") if unit.order else None
                if target:
                    tx, ty = target
                    dist_to_target = abs(tx - unit.x) + abs(ty - unit.y)
                    # 敌人挡在前进路线上：主动攻击最近敌人
                    if nearest["dist"] <= dist_to_target or nearest["dist"] <= 3:
                        actions.append(WorldAction(
                            kind="attack", unit=unit.id,
                            target=[nearest["x"], nearest["y"]]))
                        self.state = "engaging"
                        self._maybe_report_contact(unit, enemies, self._tick,
                                                   bus, registry, perc)
                        return actions
            elif not has_order and not unit.entrenched:
                aggression = float(tuning.get("aggression_scale", 1.0))
                if aggression >= 0.5 and nearest["dist"] <= 3 and not is_night:
                    actions.append(WorldAction(
                        kind="attack", unit=unit.id,
                        target=[nearest["x"], nearest["y"]]))
                    self.state = "engaging"
                    self._maybe_report_contact(unit, enemies, self._tick,
                                               bus, registry, perc)
                    return actions

            self._maybe_report_contact(unit, enemies, self._tick, bus, registry, perc)
            return actions

        # === 无敌情：保持上级命令或待命 ===
        if has_order:
            self.state = "advancing" if order_kind in ("move", "attack") else "defending"
        elif unit.entrenched:
            self.state = "defending"
        else:
            self.state = "holding"

        self._maybe_routine_report(unit, self._tick, bus, registry, tuning)
        return actions

    # ---- 炮兵目标选择 ----
    def _artillery_target(self, unit: Unit, enemies: list[dict],
                          world: World) -> dict | None:
        """从视野内敌人中选择炮击目标：优先打密集处/兵力多的。"""
        from ..engine.world import _arty_range
        rng = _arty_range(world, unit)
        in_range = [e for e in enemies if e["dist"] <= rng + 1]
        if not in_range:
            return None
        return max(in_range, key=lambda e: e["strength"])

    # ---- 后撤方向计算 ----
    def _retreat_target(self, unit: Unit, enemies: list[dict],
                        world: World) -> list[int] | None:
        """找一个远离敌人的可通行格作为后撤点。"""
        if not enemies:
            return None
        cx = sum(e["x"] for e in enemies) / len(enemies)
        cy = sum(e["y"] for e in enemies) / len(enemies)
        dx = 1 if unit.x < cx else -1
        dy = 1 if unit.y < cy else -1
        for dist in (2, 3, 4):
            for nx, ny in [
                (unit.x + dx * dist, unit.y),
                (unit.x, unit.y + dy * dist),
                (unit.x + dx * dist, unit.y + dy * dist),
            ]:
                if (0 <= nx < world.w and 0 <= ny < world.h
                        and world.passable(nx, ny)
                        and not world.unit_at(nx, ny)):
                    return [nx, ny]
        return None

    # ---- 异步上报 ----
    def _maybe_report_contact(self, unit: Unit, enemies: list[dict], tick: int,
                              bus: "Bus" | None, registry: "Registry" | None,
                              perc: dict) -> None:
        if not bus or not registry:
            return
        interval = max(2, int(perc.get("report_interval", 6) or 6))
        if tick - self.last_contact_tick < interval:
            return
        if not enemies:
            return
        self.last_contact_tick = tick
        foe_names = "、".join(e["name"] for e in enemies[:3])
        body = (f"我部在 ({unit.x},{unit.y}) 发现敌{foe_names}"
                f"（最近距离{enemies[0]['dist']}格），已自主接战。"
                f"当前兵力{round(unit.strength)}。")
        self._send_report(bus, registry, unit, MsgKind.SITREP,
                          "接触报告", body,
                          {"event": "tactical_contact",
                           "x": unit.x, "y": unit.y,
                           "foes": [e["id"] for e in enemies],
                           "strength": round(unit.strength),
                           "tactical_state": self.state})

    def _report_escalation(self, unit: Unit, enemies: list[dict], tick: int,
                           bus: "Bus" | None, registry: "Registry" | None,
                           reason: str, perc: dict) -> None:
        if not bus or not registry:
            return
        foe_names = "、".join(e["name"] for e in enemies[:3]) if enemies else "敌军"
        body = (f"{reason}。位置({unit.x},{unit.y})，当面之敌：{foe_names}，"
                f"当前兵力{round(unit.strength)}/{round(unit.strength_max)}。")
        self._send_report(bus, registry, unit, MsgKind.ESCALATION,
                          "战术告警", body,
                          {"event": "tactical_escalation",
                           "x": unit.x, "y": unit.y,
                           "strength": round(unit.strength),
                           "reason": reason,
                           "tactical_state": self.state}, priority=0)

    def _report_reorg(self, unit: Unit, bus: "Bus" | None,
                      registry: "Registry" | None, state: str) -> None:
        if not bus or not registry or not unit:
            return
        if state == "reorg":
            body = (f"我部{unit.name}在({unit.x},{unit.y})重组完毕，恢复至"
                    f"兵力{round(unit.strength)}，重新投入战斗。")
            self._send_report(bus, registry, unit, MsgKind.SITREP,
                              "重组完成", body,
                              {"event": "tactical_reorg",
                               "x": unit.x, "y": unit.y,
                               "strength": round(unit.strength),
                               "tactical_state": self.state})

    def _maybe_routine_report(self, unit: Unit, tick: int,
                              bus: "Bus" | None, registry: "Registry" | None,
                              tuning: dict) -> None:
        if not bus or not registry:
            return
        interval = max(4, int(tuning.get("tactical_report_interval", 10)))
        if tick - self.last_report_tick < interval:
            return
        self.last_report_tick = tick
        body = (f"战术例行报告：位置({unit.x},{unit.y})，"
                f"兵力{round(unit.strength)}/{round(unit.strength_max)}，"
                f"补给{round(unit.supply)}，状态{TACT_STATES.get(self.state, self.state)}。")
        self._send_report(bus, registry, unit, MsgKind.SITREP,
                          "分队报告", body,
                          {"event": "tactical_report",
                           "x": unit.x, "y": unit.y,
                           "strength": round(unit.strength),
                           "supply": round(unit.supply),
                           "tactical_state": self.state})

    def _maybe_report(self, unit: Unit, tick: int, bus: "Bus" | None,
                      registry: "Registry" | None, tuning: dict, body: str) -> None:
        if not bus or not registry:
            return
        self.last_report_tick = tick
        self._send_report(bus, registry, unit, MsgKind.SITREP,
                          "分队报告", body,
                          {"event": "tactical_report",
                           "x": unit.x, "y": unit.y,
                           "strength": round(unit.strength),
                           "tactical_state": self.state})

    # ---- 实际发送上报消息 ----
    def _send_report(self, bus: "Bus", registry: "Registry", unit: Unit,
                     kind: MsgKind, subject: str, body: str,
                     data: dict, priority: int = 1) -> None:
        from ..schemas import Message
        owner = registry.owner_of_unit(unit.id)
        recipient = owner.id if owner else self.owner_pos
        sender = f"unit:{unit.id}"
        try:
            msg = Message.create(
                tick=getattr(self, "_tick", 0),
                sender=sender, recipient=recipient,
                kind=kind, subject=subject, body=body,
                data=data, priority=priority)
            bus.send(msg)
        except (ValueError, Exception):
            pass  # 上报失败不影响战术行动


class TacticalManager:
    """管理一个阵营所有战术Agent的容器。支持规则/LLM 两种策略。"""
    def __init__(self, side: str, registry: "Registry", bus: "Bus",
                 tuning: dict | None = None, policy_mode: str = "rule",
                 llm_client: "LLMClient" | None = None,
                 llm_interval: int = 4) -> None:
        self.side = side
        self.registry = registry
        self.bus = bus
        self.tuning = tuning or {}
        self.policy_mode = policy_mode
        self.llm_client = llm_client
        self.llm_interval = llm_interval
        self.agents: dict[str, TacticalAgent] = {}
        self.decision_log: list[dict] = []  # 最近决策记录（调试用）
        self._log_max = 200

    def ensure_agent(self, unit_id: str, owner_pos: str = "") -> TacticalAgent:
        if unit_id not in self.agents:
            self.agents[unit_id] = TacticalAgent(
                unit_id=unit_id, side=self.side, owner_pos=owner_pos)
        return self.agents[unit_id]

    def sync_units(self, world: World) -> None:
        for uid, unit in world.units.items():
            if unit.side != self.side:
                continue
            owner = self.registry.owner_of_unit(uid)
            owner_pos = owner.id if owner else f"{self.side}:army"
            agent = self.ensure_agent(uid, owner_pos)
            if not unit.alive:
                agent.state = "destroyed"

    def decide_all(self, world: World, tick: int) -> list[tuple[str, WorldAction]]:
        self.sync_units(world)
        results: list[tuple[str, WorldAction]] = []
        for uid, agent in self.agents.items():
            unit = world.units.get(uid)
            if not unit or not unit.alive:
                continue
            llm = self.llm_client if self.policy_mode == "llm" else None
            actions = agent.decide(world, tick, self.tuning, self.bus,
                                   self.registry, llm, self.llm_interval)
            self._log_decision(agent, unit, world, tick)
            for act in actions:
                results.append((uid, act))
        return results

    def _log_decision(self, agent: TacticalAgent, unit: Unit,
                      world: World, tick: int) -> None:
        """记录决策快照（调试中心数据源）。"""
        self.decision_log.append({
            "tick": tick, "unit_id": agent.unit_id, "name": unit.name,
            "state": agent.state, "state_name": TACT_STATES.get(agent.state, agent.state),
            "x": unit.x, "y": unit.y, "strength": round(unit.strength),
            "morale": round(unit.morale), "fatigue": round(unit.fatigue),
            "decision": agent.last_decision,
            "thought": agent.last_thought[:160],
        })
        if len(self.decision_log) > self._log_max:
            del self.decision_log[: len(self.decision_log) - self._log_max]

    def snapshot(self) -> list[dict]:
        out = []
        for uid, a in self.agents.items():
            out.append({
                "unit_id": uid,
                "side": a.side,
                "state": a.state,
                "state_name": TACT_STATES.get(a.state, a.state),
                "owner": a.owner_pos,
                "last_contact": a.last_contact_tick,
                "last_report": a.last_report_tick,
                "withdrew": a.withdrew,
                "last_decision": a.last_decision,
                "last_thought": a.last_thought,
            })
        return out

    def recent_decisions(self, limit: int = 50) -> list[dict]:
        return self.decision_log[-limit:]
