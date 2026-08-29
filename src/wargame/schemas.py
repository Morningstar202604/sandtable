"""协议层：消息、世界动作、智能体决策的统一 schema。

组织模拟的全部通信都走类型化消息——没有共享黑板。
阵营隔离、权限校验都在上层用这里的字段做硬校验。
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# 阵营 id 泛化为任意字符串（red/blue 是默认双阵营；多方战役可用
# usa/uk/ger 等任意 id）。显示名由场景 CAMP_NAMES 提供。
Side = str

SIDE_NAME = {"red": "红军", "blue": "蓝军"}


class MsgKind(str, Enum):
    """消息类型。类型化是为了让上层可以按类型做路由与统计（如意图保真度分析）。"""

    INTENT = "intent"        # 上级作战意图（做什么+为什么）
    ORDER = "order"          # 命令（含任务式指挥的 mission 数据）
    ACK = "ack"              # 执行确认
    SITREP = "sitrep"        # 态势报告（上行）
    REQUEST = "request"      # 请示 / 请求支援（上行）
    INTEL = "intel"          # 情报通报
    PLAN = "plan"            # 参谋方案（含选项，供主官择定）
    ESCALATION = "escalation"  # 例外告警（遭袭/补给断/损失过重）


# 优先级 → 投递延迟（tick）。紧急消息同级 next-tick 送达，例行多一等。
# 延迟是有意保留的摩擦：上级基于延迟信息决策是本模拟要观察的核心现象。
MSG_LATENCY = {0: 1, 1: 1, 2: 2}
PRIORITY_NAME = {0: "特急", 1: "加急", 2: "例行"}


class Message(BaseModel):
    """阵营内流动的唯一信息载体。sender/recipient 均为本阵营职位 id（或 unit:/hq: 前缀）。"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    tick: int                      # 发出的 tick
    deliver_at: int                # 送达 tick（含通信延迟）
    sender: str
    recipient: str
    kind: MsgKind
    subject: str = ""
    body: str = ""                 # 自然语言正文，LLM 模式下由模型生成/阅读
    data: dict[str, Any] = Field(default_factory=dict)  # 结构化附加数据（如方案选项、目标坐标）
    priority: int = 1

    @classmethod
    def create(
        cls,
        tick: int,
        sender: str,
        recipient: str,
        kind: MsgKind | str,
        subject: str = "",
        body: str = "",
        data: dict[str, Any] | None = None,
        priority: int = 1,
    ) -> Message:
        return cls(
            tick=tick,
            deliver_at=tick + MSG_LATENCY.get(priority, 1),
            sender=sender,
            recipient=recipient,
            kind=MsgKind(kind),
            subject=subject,
            body=body,
            data=data or {},
            priority=priority,
        )


class WorldAction(BaseModel):
    """智能体提交给世界引擎的动作。target 为网格坐标 [x, y]。

    只允许位置坐标、不允许"敌单位 id"——情报是有误差的，
    指挥员打的是地图上的点，而不是上帝视角的敌人实体。
    """

    kind: Literal["move", "attack", "entrench", "hold"]
    unit: str
    target: list[int] | None = None


class AgentDecision(BaseModel):
    """一次醒来的决策产物。messages 里的 dict 稍后经 Message.create 落地。"""

    thoughts: str = ""
    messages: list[dict[str, Any]] = Field(default_factory=list)
    world_actions: list[WorldAction] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.messages and not self.world_actions
