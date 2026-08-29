"""阵营消息总线：延迟投递 + 隔离硬校验。

每个阵营一条总线实例——跨阵营根本没有第二条总线可达，
这是结构上的隔离，不依赖任何约定。阵营内也一样：
智能体之间不共享内存，信息只能通过总线上的消息流动。
"""

from __future__ import annotations

import random
from collections import defaultdict

from .org import Registry
from .schemas import Message


class Bus:
    """一个阵营的通信基础设施。发送即排队，按 deliver_at 到期投递。

    friction 提供组织摩擦旋钮：latency_scale（延迟倍率）与 loss_rate（丢失率），
    用于实验"上级基于迟到且不完整的信息决策"。
    """

    def __init__(self, side: str, registry: Registry,
                 rng: random.Random | None = None, friction: dict | None = None) -> None:
        self.side = side
        self.registry = registry
        self.rng = rng or random.Random()
        self.friction = friction if friction is not None else {}
        self._queue: list[Message] = []
        self.sent_count = 0
        self.lost_count = 0

    def send(self, msg: Message) -> bool:
        """入队一条消息。收发双方必须同属本阵营，否则拒绝（隔离红线）。

        返回 False 表示电文在通信摩擦中丢失。
        """
        for pos_id in (msg.sender, msg.recipient):
            if not self._check(pos_id):
                raise ValueError(
                    f"[隔离拦截] {self.side} 总线拒绝非本阵营地址: {pos_id}")
        loss = float(self.friction.get("loss_rate", 0.0))
        if loss > 0 and self.rng.random() < loss:
            self.lost_count += 1
            return False
        scale = float(self.friction.get("latency_scale", 1.0))
        if scale != 1.0:
            msg.deliver_at = msg.tick + max(1, round((msg.deliver_at - msg.tick) * scale))
        self._queue.append(msg)
        self.sent_count += 1
        return True

    def _check(self, pos_id: str) -> bool:
        # 职位地址必须带本阵营前缀原样匹配——剥前缀再拼回会把 blue:div1 误认成 red:div1
        if pos_id.startswith("unit:"):
            # 部队归属查编制表（单位 id 前缀约定不适用于任意多方阵营 id）
            owner = self.registry.owner_of_unit(pos_id[5:])
            return owner is not None and owner.side == self.side
        p = self.registry.get(pos_id)
        return p is not None and p.side == self.side

    def due(self, tick: int) -> list[Message]:
        """取出本 tick 应送达的消息，按收件人分组返回。"""
        due, keep = [], []
        for m in self._queue:
            (due if m.deliver_at <= tick else keep).append(m)
        self._queue = keep
        by_recipient: dict[str, list[Message]] = defaultdict(list)
        for m in due:
            by_recipient[m.recipient].append(m)
        return dict(by_recipient)

    def pending(self) -> int:
        return len(self._queue)
