"""阵营容器：一个阵营 = 一条总线 + 一组智能体 + 一个情报库 + 战术Agent群。
阵营是隔离的边界单元：跨阵营没有任何共享对象，
情报库只记录"本方侦察到的敌方轮廓"，不触碰敌方真实状态。
战术Agent群绑定到每个作战Unit，提供一线局部自主智能（本地感知+自主行动+异步上报）。
"""
from __future__ import annotations

from .agents.base import Agent, Policy
from .agents.tactical import TacticalManager
from .bus import Bus
from .org import Registry
from .schemas import Message


class IntelStore:
    """本阵营的敌情库：最后一次目击的敌方轮廓（带误差坐标）。"""
    def __init__(self) -> None:
        self.last_known: dict[str, dict] = {}

    def update(self, sightings: list[dict]) -> None:
        for s in sightings:
            self.last_known[s["unit_id"]] = {
                "unit_id": s["unit_id"], "name": s["name"], "kind": s["kind"],
                "x": s["x"], "y": s["y"], "tick": s["tick"],
            }

    def view(self) -> list[dict]:
        return sorted(self.last_known.values(), key=lambda d: d["unit_id"])


class Camp:
    def __init__(self, side: str, registry: Registry, policy: Policy,
                 rng=None, friction: dict | None = None,
                 tuning: dict | None = None) -> None:
        self.side = side
        self.registry = registry
        self.bus = Bus(side, registry, rng=rng, friction=friction)
        self.tuning = tuning if tuning is not None else {}
        self.agents: dict[str, Agent] = {
            p.id: Agent(p, policy, tuning=self.tuning) for p in registry.agents(side)
        }
        self.intel = IntelStore()
        # 战术Agent群：每个作战Unit绑定一个轻量战术智能体
        # 拥有本地即时感知（直接读world）、局部自主行动、异步上报（走bus）
        # policy_mode（rule/llm）与 llm_client 由 sim 层在 _tactical_decide 中配置
        self.tactical = TacticalManager(side, registry, self.bus, tuning=self.tuning)
        # 场景附件：战略方案选项（参谋长用）与侦察目标点（军长部署侦察用）
        self.plans: list[dict] = []
        self.recon_target: list[int] | None = None

    def deliver(self, tick: int) -> list[tuple[str, list[Message], bool]]:
        """投递到期消息。返回 [(收件人, 消息, 是否有智能体签收)]。
        上级司令部/侦察哨等虚拟职位只作地址存在——发给它们的消息
        等于发进了黑洞，这正是"报告上去了"与"上面知道了"的区别。
        """
        out: list[tuple[str, list[Message], bool]] = []
        for recipient, msgs in self.bus.due(tick).items():
            agent = self.agents.get(recipient)
            if agent:
                agent.receive(msgs)
                out.append((recipient, msgs, True))
            else:
                out.append((recipient, msgs, False))
        return out

    def tactical_snapshot(self) -> list[dict]:
        """导出本阵营所有战术Agent状态（供前端态势图与调试用）。"""
        return self.tactical.snapshot()
