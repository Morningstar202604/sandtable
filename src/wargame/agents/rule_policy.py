"""规则策略：无 LLM 时的确定性决策，也是 LLM 失败时的降级路径。

按职位原型分派。动作结构与 LLM 模式完全一致（同样的消息类型、
同样的世界动作），保证两种"脑"产出可互换——差异只在文本与判断质量。
想改剧本战术，改这里即可，完全离线可跑。
"""

from __future__ import annotations

from ..schemas import AgentDecision, MsgKind, WorldAction
from .base import Agent, SituationView


def _m(to: str, kind: MsgKind, subject: str, body: str,
       data: dict | None = None, priority: int = 1) -> dict:
    return {"to": to, "kind": kind, "subject": subject, "body": body,
            "data": data or {}, "priority": priority}


def _stagger(target: list[int], i: int, side: str, defense: bool) -> list[int]:
    """同目标多路梯队的错位展开点：进攻方在接近侧梯次展开，防御方在纵深侧错位。"""
    x, y = target
    if defense:
        return [x, y + i]
    return [x - i, y] if side == "red" else [x + i, y]


# ---------------------------------------------------------------- 军长
def army_cmd(agent: Agent, view: SituationView) -> AgentDecision:
    msgs, acts = [], []
    side = view.camp_side
    for m in agent.inbox:
        if m.kind == MsgKind.INTENT:
            agent.state["intent"] = m.body
            agent.add_task("定下作战决心", m.tick)
            msgs.append(_m(view.pid("cos"), MsgKind.REQUEST, "请求拟定作战方案",
                           f"上级意图：{m.body}。请拟制两个以上方案，"
                           "明确主攻方向与各部任务区分。", {"need": "plan"}))
        elif m.kind == MsgKind.PLAN and m.data.get("options"):
            opt = m.data["options"][0]  # 采纳参谋首选方案
            for div_id, asg in opt["assignments"].items():
                msgs.append(_m(div_id, MsgKind.ORDER, opt["name"],
                               f"任务：{asg['mission']}。意图：{opt['intent']}", asg))
            agent.complete_tasks()
            agent.add_task("掌握战役进程，协调各师行动", view.tick)
            if view.parent:
                msgs.append(_m(view.position.parent, MsgKind.SITREP, "决心已定",
                               f"已采纳方案[{opt['name']}]，并向各师下达任务。"))
        elif m.kind == MsgKind.REQUEST and m.data.get("need") == "supply":
            msgs.append(_m(view.pid("log"), MsgKind.ORDER, "保障任务",
                           m.body or "请安排补给前送。", {"from": m.sender}))
        elif m.kind == MsgKind.REQUEST:
            msgs.append(_m(m.sender, MsgKind.ACK, "收到请示",
                           "按既定任务继续执行，视情予以支援。"))
        elif m.kind == MsgKind.ESCALATION:
            if view.parent:
                msgs.append(_m(view.position.parent, MsgKind.ESCALATION, m.subject,
                               f"{view.title(m.sender)}报告：{m.body}",
                               m.data, priority=0))
        elif m.kind == MsgKind.INTEL:
            pass  # 情报参谋汇总后统一呈报
    # 一次性向前部署侦察分队（目标点由场景给出，缺省指向渡河正面）
    if not agent.state.get("recon_set"):
        rid = f"{side}-u-r1"
        if any(u["id"] == rid for u in view.own_units):
            acts.append(WorldAction(kind="move", unit=rid,
                                    target=view.recon_target or [10, 3]))
            agent.state["recon_set"] = True
    # 周期战况上报
    if (view.parent and agent.has_active_task()
            and view.tick - agent.state.get("last_rep", -99)
            >= int(view.tuning.get("report_interval", 8))):
        agent.state["last_rep"] = view.tick
        msgs.append(_m(view.position.parent, MsgKind.SITREP,
                       "战役态势报告", view.units_summary()))
    return AgentDecision(
        thoughts=f"军部处理{len(agent.inbox)}件：发{len(msgs)}、动作{len(acts)}。",
        messages=msgs, world_actions=acts)


# ---------------------------------------------------------------- 参谋长
def cos(agent: Agent, view: SituationView) -> AgentDecision:
    msgs = []
    for m in agent.inbox:
        if m.kind == MsgKind.REQUEST and m.data.get("need") == "plan":
            # 方案由场景提供（历史战役）；缺省回退到内置渡河方案
            options = view.plans or _builtin_river_plans(view)
            msgs.append(_m(m.sender, MsgKind.PLAN, "作战方案建议",
                           "方案已拟妥呈审，请主官择定。", {"options": options}))
    return AgentDecision(thoughts=f"参谋部处理{len(agent.inbox)}件。",
                         messages=msgs, world_actions=[])


def _builtin_river_plans(view: SituationView) -> list[dict]:
    """内置渡河方案：场景未提供 PLANS 时的保底。"""
    side = view.camp_side
    if side == "red":
        return [
            {"name": "北桥主攻",
             "intent": "集中主力自北桥渡河夺占河东城镇，一部南桥助攻牵制",
             "assignments": {
                 view.pid("div1"): {"mission": "主攻：自北桥（12,4）渡河，夺占河东城镇（18,7）",
                                    "target": [12, 4], "next": [18, 7], "fire_support": [12, 4]},
                 view.pid("div2"): {"mission": "助攻：自南桥（12,11）渡河，牵制敌军并向城镇发展",
                                    "target": [12, 11], "next": [18, 8], "fire_support": [12, 11]},
             }},
            {"name": "南桥主攻",
             "intent": "集中主力自南桥渡河夺占河东城镇，一部北桥助攻牵制",
             "assignments": {
                 view.pid("div1"): {"mission": "助攻：自北桥（12,4）渡河，牵制敌军",
                                    "target": [12, 4], "next": [18, 7], "fire_support": [12, 4]},
                 view.pid("div2"): {"mission": "主攻：自南桥（12,11）渡河，夺占河东城镇（18,8）",
                                    "target": [12, 11], "next": [18, 8], "fire_support": [12, 11]},
             }},
        ]
    return [
        {"name": "河岸纵深防御",
         "intent": "依托东岸要点固守，火力控制两处渡场，迟滞消耗进攻之敌",
         "assignments": {
             view.pid("div1"): {"mission": "坚守北桥东岸要点，炮兵压制渡场",
                                "target": [13, 4], "entrench": True, "fire_support": [12, 4]},
             view.pid("div2"): {"mission": "坚守南桥东岸要点，第4团为师预备队",
                                "target": [13, 11], "entrench": True,
                                "fire_support": [12, 11],
                                "reserve": view.pid("div2-b4"), "reserve_pos": [16, 10]},
         }},
    ]


# ---------------------------------------------------------------- 情报参谋
def intel(agent: Agent, view: SituationView) -> AgentDecision:
    msgs = []
    buf: dict = agent.state.setdefault("buf", {})
    for m in agent.inbox:
        if m.kind == MsgKind.INTEL and m.data.get("unit_id"):
            buf[m.data["unit_id"]] = m.data
    if buf and (len(buf) >= 3 or view.tick - agent.state.get("last_summary", -99) >= 6):
        lines = [f"敌{UNIT_KIND_CN.get(d['kind'], d['kind'])}分队 约({d['x']},{d['y']})（T{d['tick']}上报）"
                 for d in buf.values()]
        msgs.append(_m(view.pid("army"), MsgKind.INTEL, "敌情综合",
                       "；".join(lines) + "。", {"entries": list(buf.values())}))
        agent.state["last_summary"] = view.tick
        buf.clear()
    return AgentDecision(thoughts=f"情报台处理{len(agent.inbox)}件。",
                         messages=msgs, world_actions=[])


UNIT_KIND_CN = {"infantry": "步兵", "armor": "装甲", "artillery": "炮兵", "recon": "侦察"}


# ---------------------------------------------------------------- 后勤处长
def log(agent: Agent, view: SituationView) -> AgentDecision:
    msgs = []
    for m in agent.inbox:
        if m.kind == MsgKind.ORDER and m.data.get("from"):
            msgs.append(_m(m.data["from"], MsgKind.ACK, "补给安排",
                           "已安排运输队前送，注意依托补给站地域组织接收。"))
    return AgentDecision(thoughts=f"后勤处理{len(agent.inbox)}件。",
                         messages=msgs, world_actions=[])


# ---------------------------------------------------------------- 师长
def div_cmd(agent: Agent, view: SituationView) -> AgentDecision:
    msgs, acts = [], []
    side = view.camp_side
    regs = [c for c in view.children if c.archetype == "reg_cmd"]
    for m in agent.inbox:
        if m.kind == MsgKind.ORDER:
            d = m.data or {}
            agent.add_task(m.subject or "执行师任务", m.tick)
            msgs.append(_m(m.sender, MsgKind.ACK, "收到命令",
                           f"[{m.subject}]已受领，正在向各团部署。"))
            reserve = d.get("reserve")
            reg_targets = d.get("reg_targets") or {}
            for i, reg in enumerate(regs):
                if reserve and reg.id == reserve:
                    msgs.append(_m(reg.id, MsgKind.ORDER, "预备队",
                                   "为师预备队，在指定地域待命，随时准备投入。",
                                   {"target": d.get("reserve_pos", [16, 10]),
                                    "entrench": False}))
                    continue
                defense = bool(d.get("entrench"))
                # 场景可为每个团指定单独目标（如诺曼底五滩各自方向）；
                # 未指定时按惯例：第一团取主目标，其余团在接近侧梯次展开
                tgt = reg_targets.get(reg.id)
                if tgt is None:
                    base = d.get("target")
                    if base:
                        tgt = list(base) if i == 0 else _stagger(list(base), i, side, defense)
                if tgt:
                    msgs.append(_m(reg.id, MsgKind.ORDER, m.subject,
                                   f"任务：{d.get('mission', m.subject)}",
                                   {"target": tgt, "next": d.get("next"),
                                    "entrench": defense}))
            if d.get("fire_support") and agent.position.units:
                # 炮兵 attack：引擎内会自主机动至射程后保持火力
                acts.append(WorldAction(kind="attack", unit=agent.position.units[0],
                                        target=d["fire_support"]))
        elif m.kind == MsgKind.ESCALATION:
            if view.position.parent:
                msgs.append(_m(view.position.parent, MsgKind.ESCALATION, m.subject,
                               f"{view.title(m.sender)}报告：{m.body}",
                               m.data, priority=0))
            # 火力机动：师属炮兵调向告警地点
            if m.data.get("x") is not None and agent.position.units:
                acts.append(WorldAction(kind="attack", unit=agent.position.units[0],
                                        target=[m.data["x"], m.data["y"]]))
                msgs.append(_m(m.sender, MsgKind.ACK, "火力支援",
                               "师炮兵已向你们方向转移火力。"))
    if (view.position.parent and agent.has_active_task()
            and view.tick - agent.state.get("last_rep", -99)
            >= int(view.tuning.get("report_interval", 8))):
        agent.state["last_rep"] = view.tick
        msgs.append(_m(view.position.parent, MsgKind.SITREP,
                       "师战况报告", view.units_summary()))
    return AgentDecision(thoughts=f"师部处理{len(agent.inbox)}件：发{len(msgs)}、动作{len(acts)}。",
                         messages=msgs, world_actions=acts)


# ---------------------------------------------------------------- 团长
def reg_cmd(agent: Agent, view: SituationView) -> AgentDecision:
    msgs, acts = [], []
    unit_id = agent.position.units[0] if agent.position.units else None
    for m in agent.inbox:
        if m.kind == MsgKind.ORDER:
            d = m.data or {}
            agent.add_task(m.subject or "执行任务", m.tick)
            agent.state["next"] = d.get("next")
            agent.state["entrench_after"] = bool(d.get("entrench"))
            agent.state["esc_sent"] = False
            agent.state["last_contact_fwd"] = -99
            msgs.append(_m(m.sender, MsgKind.ACK, "收到命令",
                           f"[{m.subject}]已受领，即向 {tuple(d['target']) if d.get('target') else '待机地域'} 机动。"))
            if unit_id and d.get("target"):
                acts.append(WorldAction(kind="move", unit=unit_id, target=d["target"]))
        elif m.sender.startswith("unit:") and m.data.get("event"):
            ev, up = m.data["event"], view.position.parent
            strength = m.data.get("strength", 100)
            # 职位级参数覆盖全局调参——保守的指挥官会提早告警收缩；
            # 进攻倾向 aggression_scale 越高，等效撤退阈值越低（越敢打）
            agg = max(0.2, float(view.tuning.get("aggression_scale", 1.0)))
            threshold = int((view.position.config.get("withdraw_threshold")
                             or view.tuning.get("withdraw_threshold", 40)) / agg)
            if ev == "contact":
                # 告警延迟 escalation_delay：连败多拍才向上告警，避免一受挫就呼叫
                delay = max(0, int(view.tuning.get("escalation_delay", 0)))
                if strength < threshold:
                    agent.state["low_t"] = agent.state.get("low_t", 0) + 1
                else:
                    agent.state["low_t"] = 0
                if (strength < threshold and not agent.state.get("esc_sent")
                        and agent.state.get("low_t", 0) > delay):
                    agent.state["esc_sent"] = True
                    if up:
                        msgs.append(_m(up, MsgKind.ESCALATION, "战况告警",
                                       f"我部损失过重（兵力{strength}），请求支援或调整任务。",
                                       {"x": m.data.get("x"), "y": m.data.get("y"),
                                        "strength": strength, "need": "support"}, priority=0))
                    if unit_id:
                        acts.append(WorldAction(kind="entrench", unit=unit_id))
                elif (up and view.tick - agent.state.get("last_contact_fwd", -99)
                      >= int(view.tuning.get("contact_fwd_interval", 4))):
                    agent.state["last_contact_fwd"] = view.tick
                    foes = "、".join(m.data.get("vs", [])) or "敌军"
                    msgs.append(_m(up, MsgKind.SITREP, "接触报告",
                                   f"我部与{foes}交战中（兵力{strength}）。"))
            elif ev == "fire" and up:
                msgs.append(_m(up, MsgKind.SITREP, "遭敌炮袭",
                               f"我部遭敌炮兵急袭，损失{m.data.get('dmg', 0)}。"))
            elif ev == "reached":
                nxt = agent.state.pop("next", None)
                if nxt and unit_id:
                    acts.append(WorldAction(kind="move", unit=unit_id, target=nxt))
                    if up:
                        msgs.append(_m(up, MsgKind.SITREP, "阶段报告",
                                       f"已夺占既定目标，正继续向 {tuple(nxt)} 推进。"))
                else:
                    if agent.state.get("entrench_after") and unit_id:
                        acts.append(WorldAction(kind="entrench", unit=unit_id))
                        agent.state["entrench_after"] = False
                    if up:
                        msgs.append(_m(up, MsgKind.SITREP, "任务完成",
                                       "已到达目标地域，部署完毕。"))
                    agent.complete_tasks()
        elif m.kind == MsgKind.ACK:
            pass
    if (view.position.parent and agent.has_active_task()
            and view.tick - agent.state.get("last_rep", -99)
            >= int(view.tuning.get("report_interval", 8))):
        agent.state["last_rep"] = view.tick
        msgs.append(_m(view.position.parent, MsgKind.SITREP, "战况报告",
                       view.units_summary()))
    return AgentDecision(thoughts=f"团部处理{len(agent.inbox)}件：发{len(msgs)}、动作{len(acts)}。",
                         messages=msgs, world_actions=acts)


_DISPATCH = {
    "army_cmd": army_cmd, "cos": cos, "intel": intel,
    "log": log, "div_cmd": div_cmd, "reg_cmd": reg_cmd,
}


class RulePolicy:
    """确定性策略：按职位原型分派。"""

    def decide(self, agent: Agent, view: SituationView) -> AgentDecision:
        fn = _DISPATCH.get(agent.position.archetype)
        if fn is None:
            return AgentDecision(thoughts="无原型策略，待命。")
        return fn(agent, view)
