"""智能体基类：信箱 + 任务队列 + 记忆 + 可插拔决策策略。

智能体之间零共享：能看到什么完全由 SituationView 决定——
严格限本阵营、限指挥范围。记忆只来自自己收到的消息，
这正是"军长不知道团长在干什么，除非报告送达"的实现方式。
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

from ..org import Position, Registry
from ..schemas import AgentDecision, Message, MsgKind

if TYPE_CHECKING:
    from ..engine.world import World
    from ..camps import Camp

KIND_SHORT = {
    MsgKind.INTENT: "意图", MsgKind.ORDER: "命令", MsgKind.ACK: "确认",
    MsgKind.SITREP: "报告", MsgKind.REQUEST: "请示", MsgKind.INTEL: "情报",
    MsgKind.PLAN: "方案", MsgKind.ESCALATION: "告警",
}


class Task(BaseModel):
    id: int
    desc: str
    status: str = "active"  # active / done
    created: int


class SituationView:
    """一次决策所能看到的全部信息（阵营内、指挥范围内的投影）。"""

    def __init__(self, agent: "Agent", camp: "Camp", registry: Registry,
                 world: "World", tick: int) -> None:
        self.tick = tick
        self.camp_side = camp.side
        self.registry = registry
        self.position: Position = agent.position
        # 指挥范围：本级 + 直接下级；军长可见全阵营部队
        scope_ids = {self.position.id} | {c.id for c in registry.children(self.position.id)}
        if self.position.archetype == "army_cmd":
            scope_ids = {q.id for q in registry.by_id.values() if q.side == camp.side}
        units = []
        for pid in scope_ids:
            pos = registry.get(pid)
            for uid in (pos.units if pos else []):
                u = world.units.get(uid)
                if u and u.alive:
                    units.append(u)
        self.own_units = [world.unit_view(u) for u in units]
        # 情报权限：只有军部（军长/参谋长/情报参谋）能看敌情汇总库。
        # 师团级只能从命令与下级报告里了解敌人——阵营内的信息不对称。
        self.intel: list[dict] = (
            camp.intel.view()
            if self.position.archetype in ("army_cmd", "cos", "intel") else []
        )
        self.children = registry.children(self.position.id)
        self.parent = registry.get(self.position.parent) if self.position.parent else None
        # 场景提供的战略方案与侦察目标（参谋长据此拟案、军长据此部署侦察）
        self.plans = getattr(camp, "plans", []) or []
        self.recon_target = getattr(camp, "recon_target", None)
        # 调参字典引用（与 world 同源），策略读告警阈值/报告节奏等
        self.tuning = getattr(camp, "tuning", {}) or {}

    def title(self, pos_id: str) -> str:
        return self.registry.title(pos_id)

    def pid(self, key: str) -> str:
        return f"{self.camp_side}:{key}"

    def units_summary(self) -> str:
        parts = []
        for u in self.own_units:
            parts.append(f"{u['name']}:兵力{u['strength']}/补给{u['supply']}@({u['x']},{u['y']})"
                         + ("【据守】" if u["entrenched"] else ""))
        return "；".join(parts) if parts else "无直属部队"


class Policy(Protocol):
    """决策策略接口：同一位智能体可换装规则脑或 LLM 脑。"""

    def decide(self, agent: "Agent", view: SituationView) -> AgentDecision: ...


class Agent:
    _task_seq = 0

    def __init__(self, position: Position, policy: Policy,
                 tuning: dict | None = None) -> None:
        self.position = position
        self.policy = policy
        self.tuning = tuning if tuning is not None else {}
        self.inbox: list[Message] = []
        self.tasks: list[Task] = []
        self.memory: deque[str] = deque(maxlen=40)
        self.state: dict = {}  # 跨决策周期的局部状态（后续目标、已告警标记等）
        self.last_thought = ""
        self.last_active = -99

    def receive(self, msgs: list[Message]) -> None:
        self.inbox.extend(msgs)

    def should_wake(self, tick: int) -> bool:
        """有信必醒；无信但手头有进行中的任务时，按周期间隔醒来做例行报告。"""
        if self.inbox:
            return True
        interval = int(self.tuning.get("report_interval", 8))
        if any(t.status == "active" for t in self.tasks) and tick - self.last_active >= interval:
            return True
        return False

    def decide(self, view: SituationView) -> AgentDecision:
        return self.policy.decide(self, view)

    def consume_inbox(self, view: SituationView) -> None:
        """处理完邮件后归档进记忆。记忆是"我经历过什么"，
        而不是全知日志——别的智能体的事我只有收到消息才知道。"""
        for m in self.inbox:
            self.memory.append(
                f"T{m.tick}[{KIND_SHORT.get(m.kind, m.kind.value)}]"
                f"{view.title(m.sender)}→我：{m.subject or m.body[:24]}")
        self.inbox = []

    def add_task(self, desc: str, tick: int) -> None:
        Agent._task_seq += 1
        self.tasks.append(Task(id=Agent._task_seq, desc=desc, created=tick))

    def complete_tasks(self) -> None:
        for t in self.tasks:
            t.status = "done"

    def has_active_task(self) -> bool:
        return any(t.status == "active" for t in self.tasks)
