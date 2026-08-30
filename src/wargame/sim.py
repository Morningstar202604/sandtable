"""仿真编排：tick 循环 = 投递 → 决策 → 引擎 → 侦察。

顺序确定：阵营 red→blue，职位按层级序；世界随机性全部来自
固定种子 rng。全部事件进内存事件流并落盘 JSONL，供 SSE 与复盘。
两阵营在此被组装，但从不互通——唯一的交汇点是共享的世界引擎。
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

from .agents.base import Agent, SituationView
from .agents.llm_policy import LLMPolicy
from .agents.rule_policy import RulePolicy
from .camps import Camp
from .config import settings
from .engine.world import UNIT_NAME, WEATHER_CN, World
from .llm import llm_client
from .org import Position, Registry, build_camp_org
from .schemas import Message, MsgKind, WorldAction


class Simulation:
    def __init__(self, policy_mode: str = "auto", seed: int | None = None,
                 default_intents: bool = True, run_dir: Path | None = None,
                 scenario: str | None = None, tuning: dict | None = None,
                 intent_overrides: dict | None = None,
                 role_overrides: dict | None = None,
                 battle_config: dict | None = None) -> None:
        from .scenarios import DEFAULT_SCENARIO, load_scenario

        self.seed = settings.seed if seed is None else seed
        self.rng = random.Random(self.seed)
        # 场景决定地图、编制命名、开局意图与参谋方案
        self.scenario_key = scenario or DEFAULT_SCENARIO
        mod = load_scenario(self.scenario_key)
        self.scenario_name = mod.SCENARIO_NAME
        # 多方阵营：FACTIONS 为 [{id,name}]（钢铁雄心式任意多方；缺省红蓝双阵营）
        factions = []
        for f in (getattr(mod, "FACTIONS", None)
                  or [{"id": "red", "name": "红军"}, {"id": "blue", "name": "蓝军"}]):
            if isinstance(f, dict):
                factions.append({"id": f["id"], "name": f.get("name") or str(f["id"])})
            else:
                factions.append({"id": str(f), "name": str(f)})
        self.factions = [f["id"] for f in factions]
        self.camp_names = {f["id"]: f["name"] for f in factions}
        titles = getattr(mod, "ORG_TITLES", None) or {}
        configs = getattr(mod, "ORG_CONFIG", None) or {}
        orbats = getattr(mod, "ORBAT", None) or {}
        self.registry = Registry(sum(
            (build_camp_org(f["id"], titles=titles.get(f["id"]),
                            side_name=f["name"], configs=configs.get(f["id"]),
                            orbat=orbats.get(f["id"]))
             for f in factions), []))
        self.world: World = mod.build_world()
        self.world.set_weather(getattr(mod, "WEATHER", None) or [(0, "clear")])
        self.world.set_air_power(getattr(mod, "AIR_POWER", None) or {})
        self.world.set_war_pairs(getattr(mod, "WAR_PAIRS", None) or [])
        self.world.set_objectives(getattr(mod, "OBJECTIVES", None) or [])
        self._reinforcements = sorted(getattr(mod, "REINFORCEMENTS", None) or [],
                                      key=lambda r: r.get("tick", 0))
        # 调参字典以引用共享：world 直接读写它，Web 端实时修改即时生效
        if tuning:
            self.world.tuning.update(tuning)
        self.tuning = self.world.tuning
        # 战役定制：在场景基础上套一层"环境/全局/双方实力"（battlelib）
        self.battle: dict = dict(battle_config or {})
        self.battle_summary: dict = dict(self.battle)
        if battle_config:
            try:
                from . import battlelib
                self.battle_summary = battlelib.apply_battle(self, battle_config)
            except Exception:  # noqa: BLE001  定制异常不阻塞推演，回退想定原始
                self.battle_summary = {"preset": self.battle.get("preset", ""),
                                       "env": {}, "global": {}, "sides": {}}

        mode = policy_mode
        if mode == "auto":
            mode = "llm" if llm_client.available else "rule"
        self.policy_mode = mode
        self.policy = LLMPolicy(llm_client) if mode == "llm" else RulePolicy()
        self._rule_fallback = RulePolicy()

        # 组织摩擦旋钮：延迟倍率与消息丢失率（Web 设置面板实时可调）
        self.friction: dict = {"latency_scale": 1.0, "loss_rate": 0.0}
        self.camps: dict[str, Camp] = {
            s: Camp(s, self.registry, self.policy,
                    rng=self.rng, friction=self.friction, tuning=self.tuning)
            for s in self.factions
        }
        for s, camp in self.camps.items():
            camp.plans = list(getattr(mod, "PLANS", {}).get(s, []))
            camp.recon_target = getattr(mod, "RECON_TARGET", {}).get(s)
        self.tick = 0
        self.events: list[dict] = []
        self.seq = 0
        # 智能体决策 trace（调试中心）：每次决策一条，含视野/决策/LLM 交换
        self.traces: list[dict] = []
        self._trace_max = 3000
        self._trace_seq = 0
        self.run_dir = (Path(run_dir) if run_dir
                        else Path("runs") / time.strftime("run-%Y%m%d-%H%M%S"))
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._jsonl_path = self.run_dir / "events.jsonl"
        self._pending_lines: list[str] = []  # 每 tick 批量落盘，避免逐事件开关文件
        self._intents: dict[str, str] = dict(getattr(mod, "DEFAULT_INTENTS", {}))
        # 导演部的开局意图覆盖（将台作业室设定各参演方初始任务后持久化）
        if intent_overrides:
            self._intents.update({
                s: v for s, v in intent_overrides.items()
                if s in self.factions and v and v.strip()})
        # 导演部对子智能体的角色配置覆盖（性格/指挥风格/行为参数）
        if role_overrides:
            for pos_id, cfg in role_overrides.items():
                p = self.registry.get(pos_id)
                if p:
                    p.config.update(cfg)
        if default_intents:
            self._inject_default_intents()
        # 导演部导调剧本：按 tick 自动触发的情况序列（"模拟各种情况"的批量入口）
        self.director_script: list[dict] = []
        self.script_index = 0

    # ---- 事件流 ----
    def _emit(self, type_: str, **kw) -> dict:
        self.seq += 1
        e = {"seq": self.seq, "t": self.tick, "type": type_, **kw}
        self.events.append(e)
        self._pending_lines.append(json.dumps(e, ensure_ascii=False))
        return e

    def events_since(self, since: int) -> list[dict]:
        return [e for e in self.events if e["seq"] > since]

    # ---- 意图注入 ----
    def inject_intent(self, side: str, text: str) -> None:
        msg = Message.create(self.tick, f"{side}:hq", f"{side}:army",
                             MsgKind.INTENT, "上级作战意图", text, priority=0)
        self.camps[side].bus.send(msg)
        self._emit("msg", camp=side, sender=msg.sender, recipient=msg.recipient,
                   kind="intent", subject=msg.subject, body=text[:200], priority=0)

    def _inject_default_intents(self) -> None:
        for side, text in self._intents.items():
            self.inject_intent(side, text)

    # ---- 导演部情况注入 ----
    def director_message(self, side: str, recipient: str, kind: str,
                         subject: str, body: str, sender: str | None = None,
                         priority: int = 0) -> bool:
        """将台导演部：在推演中向指定参演方角色注入任意情况。

        这是"模拟各种情况"的入口——上级新任务、战场异动、情报通报、
        天气/局势巨变等，都以一条电文的形式即刻送入对应角色的信箱，
        交由该子智能体在下一轮决策中消化。
        """
        if side not in self.camps:
            return False
        sender = sender or f"{side}:hq"
        if self.registry.get(sender) is None or self.registry.get(recipient) is None \
                or self.registry.get(recipient).side != side:
            return False
        try:
            k = MsgKind(kind) if isinstance(kind, str) else MsgKind.INTENT
        except ValueError:
            k = MsgKind.INTENT
        msg = Message.create(self.tick, sender, recipient, k,
                             subject or "导演部情况通报", body or "",
                             {}, max(0, min(2, int(priority))))
        try:
            ok = self.camps[side].bus.send(msg)
        except ValueError:
            return False
        self._emit("msg", camp=side, sender=msg.sender, recipient=msg.recipient,
                   kind=msg.kind.value, subject=msg.subject[:90],
                   body=msg.body[:220], priority=msg.priority, director=True)
        return ok

    # ---- 导演部导调剧本 ----
    def set_director_script(self, script: list[dict] | None) -> None:
        """导演部预置一批'导调情况'：到指定 tick 自动注入对应子智能体。"""
        arr: list[dict] = []
        for s in (script or []):
            if not isinstance(s, dict):
                continue
            try:
                arr.append({
                    "tick": max(0, int(s.get("tick", 0))),
                    "side": str(s.get("side", "")),
                    "recipient": str(s.get("recipient", "")),
                    "kind": str(s.get("kind", "intent")),
                    "subject": str(s.get("subject", ""))[:60],
                    "body": str(s.get("body", ""))[:600],
                })
            except (TypeError, ValueError):
                continue
        self.director_script = sorted(arr, key=lambda x: x["tick"])
        self.script_index = 0

    def _step_director_script(self) -> None:
        idx = self.script_index
        while idx < len(self.director_script):
            s = self.director_script[idx]
            if s["tick"] > self.tick:
                break
            if self.director_message(
                    s["side"], s["recipient"], s["kind"], s["subject"], s["body"]):
                self._emit("dirscript", camp=s["side"], recipient=s["recipient"],
                           tick_at=s["tick"], kind=s["kind"],
                           subject=s["subject"], body=s["body"][:180])
            else:
                self._emit("dirscript_failed", camp=s["side"], recipient=s["recipient"])
            idx += 1
        self.script_index = idx

    # ---- 主循环 ----
    def run_tick(self) -> None:
        self.tick += 1
        llm_client.reset_budget()
        self._reinforce()
        self._deliver()
        self._step_director_script()
        self._decide()
        self._engine()
        self._recon()
        w = self.world.weather_at(self.tick)
        if w != self.world.weather:
            self.world.weather = w
            self._emit("weather", weather=w, name=WEATHER_CN.get(w, w))
        if self._pending_lines:
            with self._jsonl_path.open("a", encoding="utf-8") as f:
                f.write("\n".join(self._pending_lines) + "\n")
            self._pending_lines.clear()

    def _deliver(self) -> None:
        for side in self.factions:
            for recipient, msgs, handled in self.camps[side].deliver(self.tick):
                if not handled:
                    self._emit("drop", camp=side, recipient=recipient, n=len(msgs))

    def _decide(self) -> None:
        for side in self.factions:
            camp = self.camps[side]
            for pos in self.registry.agents(side):
                agent = camp.agents[pos.id]
                if not agent.should_wake(self.tick):
                    continue
                view = SituationView(agent, camp, self.registry, self.world, self.tick)
                llm_client.reset_capture()
                decision = None
                err = None
                fallback = False
                try:
                    decision = agent.decide(view)
                    agent.consume_inbox(view)
                except Exception as exc:  # noqa: BLE001
                    err = str(exc)
                    if not isinstance(self.policy, LLMPolicy):
                        self._emit("error", camp=side, pos=pos.id, error=err[:200])
                        continue
                    # LLM 失败（网络/解析/预算）→ 默认降级为规则策略；
                    # 关闭容错（fallback_enabled=0）则失败即记录并跳过本拍，便于暴露问题
                    self._emit("llm_fallback", camp=side, pos=pos.id, error=err[:160])
                    if not settings.fallback_enabled:
                        self._emit("error", camp=side, pos=pos.id,
                                   error=("LLM 失败且已关闭容错降级: " + err)[:200])
                        continue
                    fallback = True
                    try:
                        decision = self._rule_fallback.decide(agent, view)
                        agent.consume_inbox(view)
                    except Exception as exc2:  # noqa: BLE001
                        err = str(exc2)
                        self._emit("error", camp=side, pos=pos.id, error=err[:200])
                        continue
                agent.last_active = self.tick
                agent.last_thought = decision.thoughts
                self._emit("agent", camp=side, pos=pos.id,
                           thoughts=decision.thoughts[:120])
                self._trace(side, pos, agent, view, decision,
                            llm_client.drain_capture(), err, fallback)
                self._apply_decision(side, camp, pos, decision)

    def _trace(self, side: str, pos: Position, agent: Agent, view: SituationView,
               decision, llm_calls: list[dict], err: str | None,
               fallback: bool) -> None:
        """记录一次智能体决策的完整可观测快照（调试中心数据源）。"""
        self._trace_seq += 1
        t = {
            "seq": self._trace_seq, "tick": self.tick, "side": side,
            "pos": pos.id, "title": pos.title, "archetype": pos.archetype,
            "policy": "rule" if fallback else self.policy_mode,
            "fallback": fallback, "error": err,
            "structured": bool(any(c.get("tool_calls") for c in llm_calls)),
            "thoughts": (decision.thoughts or "")[:200],
            "view": {
                "inbox": len(view.position.parent or agent.inbox) if False else len(agent.inbox),
                "own_units": len(view.own_units),
                "intel": len(view.intel),
                "children": len(view.children),
            },
            "messages": [],
            "actions": [],
            "llm": llm_calls,
            "budget": {"used": len(llm_calls),
                       "max": settings.max_llm_calls_per_tick},
        }
        for md in (decision.messages or []):
            t["messages"].append({
                "to": str(md.get("to", "")), "kind": str(md.get("kind", "")),
                "subject": str(md.get("subject", ""))[:80],
                "body": str(md.get("body", ""))[:200],
            })
        for ad in (decision.world_actions or []):
            t["actions"].append({"kind": ad.kind, "unit": ad.unit,
                                 "target": list(ad.target or [])})
        self.traces.append(t)
        if len(self.traces) > self._trace_max:
            del self.traces[: len(self.traces) - self._trace_max]

    def agent_snapshot(self, pos_id: str | None = None) -> dict:
        """调试中心：各子智能体的实时内部状态（任务/记忆/信箱/局部状态）。"""
        out: dict[str, dict] = {}
        for side in self.factions:
            camp = self.camps[side]
            for p in self.registry.agents(side):
                if pos_id and p.id != pos_id:
                    continue
                a = camp.agents[p.id]
                out[p.id] = {
                    "pos": p.id, "side": side, "title": p.title,
                    "archetype": p.archetype, "virtual": p.virtual,
                    "policy": self.policy_mode,
                    "wake": a.should_wake(self.tick),
                    "inbox": [{"kind": m.kind.value, "sender": m.sender,
                               "subject": m.subject, "body": m.body[:160]}
                              for m in a.inbox],
                    "tasks": [{"desc": t.desc, "status": t.status,
                               "created": t.created} for t in a.tasks],
                    "memory": list(a.memory),
                    "state": dict(a.state),
                    "last_active": a.last_active,
                    "last_thought": a.last_thought,
                }
        return out

    def _apply_decision(self, side: str, camp: Camp, pos: Position,
                        decision) -> None:
        for md in decision.messages:
            try:
                msg = Message.create(
                    self.tick, pos.id, str(md.get("to", "")),
                    md.get("kind", "sitrep"), str(md.get("subject", ""))[:120],
                    str(md.get("body", "")), md.get("data") or {},
                    int(md.get("priority", 1)))
            except Exception:  # noqa: BLE001
                self._emit("error", camp=side, pos=pos.id, error="畸形消息被丢弃")
                continue
            if not self.registry.same_camp(pos.id, msg.recipient):
                self._emit("isolation_blocked", camp=side, sender=pos.id,
                           recipient=msg.recipient, reason="收件人不属于本阵营")
                continue
            try:
                delivered = camp.bus.send(msg)
            except ValueError as exc:
                self._emit("isolation_blocked", camp=side, sender=pos.id,
                           recipient=msg.recipient, detail=str(exc)[:140])
                continue
            if not delivered:
                self._emit("msg_lost", camp=side, sender=msg.sender,
                           recipient=msg.recipient, subject=msg.subject[:60])
                continue
            self._emit("msg", camp=side, sender=msg.sender, recipient=msg.recipient,
                       kind=msg.kind.value, subject=msg.subject[:90],
                       body=msg.body[:220], priority=msg.priority)
        for wa in decision.world_actions:
            if wa.unit not in pos.units:
                self._emit("authority_blocked", camp=side, pos=pos.id, unit=wa.unit,
                           reason="越权指挥非直属部队")
                continue
            unit = self.world.units.get(wa.unit)
            if unit and self.world.apply_action(unit, wa):
                self._emit("action", camp=side, unit=wa.unit, kind=wa.kind,
                           target=wa.target, pos=pos.id)
            else:
                self._emit("action_rejected", camp=side, unit=wa.unit, pos=pos.id)

    # ---- 增援批次：按场景时刻表入场，编入指定指挥官麾下 ----
    def _reinforce(self) -> None:
        due = [r for r in self._reinforcements if r.get("tick") == self.tick]
        for r in due:
            self.world.add_unit(r["id"], r["side"], r["name"],
                                r.get("kind", "infantry"), r["x"], r["y"])
            pos = self.registry.get(r.get("pos", ""))
            if pos:
                pos.units.append(r["id"])
            self._emit("reinforce", camp=r["side"], unit=r["id"], name=r["name"],
                       pos=r.get("pos", ""), x=r["x"], y=r["y"])

    # ---- 世界引擎结算 + 单位→指挥官的通知 ----
    def _engine(self) -> None:
        for e in self.world.step(self.rng):
            et = e["type"]
            unit = self.world.units.get(e.get("unit", ""))
            if et == "reached":
                self._emit("reached", camp=unit.side if unit else "?",
                           unit=e["unit"], name=e.get("name", ""), x=e["x"], y=e["y"])
                self._notify_unit_event(unit, "reached", "位置报告",
                                        f"我部已到达 ({e['x']},{e['y']})。", e)
            elif et == "combat":
                self._emit("combat", camp=unit.side if unit else "?", unit=e["unit"],
                           name=e.get("name", ""), taken=e["taken"], vs=e["vs"])
                self._notify_unit_event(
                    unit, "contact", "接敌报告",
                    f"我部与{'、'.join(e['vs'])}交战，本轮损失{e['taken']}，"
                    f"当前兵力{round(unit.strength) if unit else '?'}.", e)
            elif et == "fire":
                target = self.world.units.get(e["target"])
                self._emit("fire", camp=unit.side if unit else "?", unit=e["unit"],
                           name=e.get("name", ""), target=e["target"],
                           target_name=e.get("target_name", ""),
                           dmg=e["dmg"], x=e["x"], y=e["y"])
                if target:
                    owner = self.registry.owner_of_unit(target.id)
                    if owner:
                        msg = Message.create(
                            self.tick, f"unit:{target.id}", owner.id,
                            MsgKind.SITREP, "遭敌炮袭",
                            f"我部遭敌炮兵急袭，损失{e['dmg']}。",
                            {"event": "fire", "dmg": e["dmg"],
                             "x": target.x, "y": target.y})
                        try:
                            self.camps[target.side].bus.send(msg)
                        except ValueError:
                            pass
            elif et == "destroyed":
                self._emit("destroyed", camp=e["side"], unit=e["unit"],
                           name=e["name"], x=e["x"], y=e["y"])
                self._notify_unit_event(unit, "destroyed", "部队全损",
                                        f"{e['name']}已全损，退出战斗。", e)

    def _notify_unit_event(self, unit, event: str, subject: str,
                           body: str, data: dict) -> None:
        if not unit:
            return
        owner = self.registry.owner_of_unit(unit.id)
        if not owner:
            return
        payload = {"event": event, "x": unit.x, "y": unit.y,
                   "strength": round(unit.strength)}
        for k, v in data.items():
            if k != "type":
                payload.setdefault(k, v)
        msg = Message.create(
            self.tick, f"unit:{unit.id}", owner.id,
            MsgKind.ESCALATION if event == "destroyed" else MsgKind.SITREP,
            subject, body, payload)
        try:
            self.camps[unit.side].bus.send(msg)
        except ValueError:
            pass

    # ---- 侦察：敌情流入各自阵营（阵营间唯一信息通道）----
    def _recon(self) -> None:
        for side in self.factions:
            camp = self.camps[side]
            seen = self.world.sightings(side, self.rng, self.tick)
            if not seen:
                continue
            camp.intel.update(seen)
            recipient = f"{side}:intel"
            if self.registry.get(recipient) is None:
                recipient = f"{side}:army"
            for s in seen:
                body = f"发现敌{UNIT_NAME.get(s['kind'], s['kind'])}分队于 ({s['x']},{s['y']})。"
                msg = Message.create(
                    self.tick, f"{side}:front", recipient, MsgKind.INTEL,
                    "敌情速报", body,
                    {"unit_id": s["unit_id"], "kind": s["kind"], "name": s["name"],
                     "x": s["x"], "y": s["y"], "tick": s["tick"]}, priority=0)
                try:
                    camp.bus.send(msg)
                except ValueError:
                    pass
            self._emit("intel", camp=side, n=len(seen))

    # ---- 复盘指标 ----
    def compute_metrics(self) -> dict:
        """从事件流统计指挥链健康度：命令下行量、确认率与延迟、
        反馈量、通信摩擦。这是"组织机器运转质量"的量化视图。"""
        import statistics

        out: dict = {"tick": self.tick, "scenario": self.scenario_key, "camps": {}}
        for side in self.factions:
            msgs = [e for e in self.events
                    if e["type"] == "msg" and e.get("camp") == side]
            kinds: dict[str, int] = {}
            for m in msgs:
                kinds[m["kind"]] = kinds.get(m["kind"], 0) + 1
            orders = [m for m in msgs if m["kind"] == "order"]
            acks = [m for m in msgs if m["kind"] == "ack"]
            acked, latencies = 0, []
            for o in orders:
                matches = [a for a in acks
                           if a["sender"] == o["recipient"]
                           and a["recipient"] == o["sender"] and a["t"] >= o["t"]]
                if matches:
                    acked += 1
                    latencies.append(min(a["t"] for a in matches) - o["t"])
            units = self.world.side_units_view(side)
            total = sum(1 for u in self.world.units.values() if u.side == side)
            ev_count = lambda t: sum(  # noqa: E731
                1 for e in self.events if e["type"] == t and e.get("camp") == side)
            out["camps"][side] = {
                "kinds": kinds,
                "orders": len(orders),
                "ack_rate": round(acked / len(orders), 2) if orders else None,
                "ack_latency": round(statistics.mean(latencies), 1) if latencies else None,
                "sitreps": kinds.get("sitrep", 0),
                "requests": kinds.get("request", 0),
                "escalations": kinds.get("escalation", 0),
                "intel": kinds.get("intel", 0),
                "decisions": ev_count("agent"),
                "msg_lost": ev_count("msg_lost"),
                "isolation_blocked": ev_count("isolation_blocked"),
                "llm_fallback": ev_count("llm_fallback"),
                "units_alive": len(units),
                "units_total": total,
                "strength": round(sum(u["strength"] for u in units)),
            }
        # 战役目标控制与得分（多方各计各的分）
        score = {f: 0 for f in self.factions}
        for o in self.world.objectives:
            if o.get("controller") in score:
                score[o["controller"]] += o.get("value", 1)
        out["objectives"] = [{"name": o["name"], "controller": o.get("controller"),
                              "value": o.get("value", 1)} for o in self.world.objectives]
        out["score"] = score
        return out

    # ---- 快照 ----
    def _org_tree(self, side: str) -> dict:
        def node(p: Position) -> dict:
            short = p.title
            if p.side_name and short.startswith(p.side_name):
                short = short[len(p.side_name):]
            return {"id": p.id, "title": p.title, "short": short,
                    "archetype": p.archetype,
                    "staff": p.staff, "virtual": p.virtual, "units": p.units,
                    "children": [node(c) for c in self.registry.children(p.id)]}

        return node(self.registry.get(f"{side}:hq"))  # type: ignore[arg-type]

    def snapshot(self) -> dict:
        return {
            "tick": self.tick, "scenario": self.scenario_name,
            "scenario_key": self.scenario_key,
            "side_names": self.camp_names,
            "policy_mode": self.policy_mode, "seed": self.seed,
            "llm": {"available": llm_client.available, "model": llm_client.model},
            "w": self.world.w, "h": self.world.h,
            "map": ["".join(row) for row in self.world.grid],
            "weather": self.world.weather,
            "battle": self.battle_summary,
            "side_mod": {s: {k: round(v, 2) for k, v in m.items()}
                         for s, m in self.world.side_mod.items()},
            "depots": [dict(d) for d in self.world.depots],
            "objectives": [{"name": o["name"], "x": o["x"], "y": o["y"],
                            "value": o.get("value", 1), "controller": o.get("controller")}
                           for o in self.world.objectives],
            "camps": {s: {"org": self._org_tree(s),
                          "units": self.world.side_units_view(s),
                          "intel": camp.intel.view()}
                      for s, camp in self.camps.items()},
            "seq": self.seq,
        }
