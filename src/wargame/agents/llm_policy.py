"""LLM 决策策略：角色卡 + 态势 → 模型产出决策 JSON。

LLM 只生成"决策内容"（消息与动作的表述），执行与校验仍在引擎侧：
越权收件人、越权部队、畸形输出都会被硬校验拦截或降级为规则策略。
配置 LLM_API_KEY 即启用；每 tick 有调用预算上限防失控。
"""

from __future__ import annotations

import json

from ..config import settings
from ..llm import LLMClient
from ..org import ROLE_PROMPTS, SIDE_NAME
from ..schemas import AgentDecision, MsgKind, WorldAction
from .base import Agent, SituationView

_VALID_KINDS = {k.value for k in MsgKind}

# 原生工具调用 schema：模型以 decide 工具的一次调用产出完整决策。
# 类型化动作 + 枚举 + 坐标数组，全部走 OpenAI 兼容 tools 标准（框架同款机制）。
DECIDE_TOOLS = [{
    "type": "function",
    "function": {
        "name": "decide",
        "description": "输出本 tick 的决策：一句话思考、要向本阵营职位发送的电文、要对本部部队下达的动作。"
                       "无新情况时 messages 与 world_actions 都返回空数组。",
        "parameters": {
            "type": "object",
            "properties": {
                "thoughts": {"type": "string",
                             "description": "一句话决策理由"},
                "messages": {
                    "type": "array",
                    "description": "要向本阵营职位发送的电文，可为空数组",
                    "items": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string",
                                   "description": "收件人职位 id，必须是本阵营内职位"},
                            "kind": {"type": "string",
                                     "enum": sorted(_VALID_KINDS),
                                     "description": "消息类型"},
                            "subject": {"type": "string"},
                            "body": {"type": "string"},
                            "priority": {"type": "integer",
                                         "description": "0特急/1加急/2例行，默认1"},
                        },
                        "required": ["to", "kind"],
                    },
                },
                "world_actions": {
                    "type": "array",
                    "description": "要对本部部队下达的世界动作，可为空数组",
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string",
                                     "enum": ["move", "attack", "entrench", "hold"]},
                            "unit": {"type": "string", "description": "本部部队单位 id"},
                            "target": {"type": "array", "items": {"type": "integer"},
                                       "description": "目标网格坐标 [x,y]"},
                        },
                        "required": ["kind", "unit"],
                    },
                },
            },
            "required": ["thoughts", "messages", "world_actions"],
        },
    },
}]


class PolicyError(Exception):
    """LLM 输出不可用时抛出，由仿真层降级为规则策略。"""


class LLMPolicy:
    def __init__(self, client: LLMClient) -> None:
        self.client = client
        self._last_reason: str = "unknown"

    @property
    def last_reason(self) -> str:
        return self._last_reason

    def decide(self, agent: Agent, view: SituationView) -> AgentDecision:
        system = self._system(agent, view)
        user = self._situation(agent, view)
        # 主路径：原生工具调用（结构化输出）——各大 agent 框架的标准做法，
        # 由模型按 schema 产出类型化动作，取代手搓 JSON 提示词。
        if getattr(settings, "llm_use_tools", True):
            try:
                r = self.client.chat_tools(
                    system, user, DECIDE_TOOLS,
                    tool_choice={"type": "function", "function": {"name": "decide"}})
                if r["tool_calls"]:
                    obj = r["tool_calls"][0]["arguments"]
                    if isinstance(obj, dict) and obj:
                        self._last_reason = "tool_calls"
                        return self._parse(obj, agent, view)
                # 无工具调用但返回文本（端点忽略 tools）：走 JSON 提示词解析
                if r["text"].strip():
                    self._last_reason = "json_prompt"
                    return self._parse(self.client.extract_json(r["text"]),
                                       agent, view)
            except Exception:  # noqa: BLE001  端点不支持 tools → 自动回退 JSON 路径
                pass
        # 回退：JSON 提示词路径（保留原有行为）
        return self._fallback(system, user, agent, view)

    def _fallback(self, system: str, user: str, agent: Agent,
                  view: SituationView) -> AgentDecision:
        try:
            obj = self.client.extract_json(self.client.chat(system, user))
        except Exception:
            # 首次失败多为推理型模型把思维链写满输出：带提醒重试一次
            nudge = (user + "\n\n【重要】上一次输出未包含合法 JSON。"
                     "请跳过一切解释与推理过程，直接输出一个完整的 JSON 对象。\n"
                     "必须包含 thoughts、messages、world_actions 三个字段。")
            try:
                obj = self.client.extract_json(self.client.chat(system, nudge))
            except Exception:
                # 二次失败：强制输出纯 JSON，不附加任何说明
                hard_nudge = (user + "\n\n【强制】你必须只输出一个合法的 JSON 对象，"
                              "不要有任何前言、解释、markdown 或代码块。"
                              "直接以 { 开始，以 } 结束。")
                try:
                    obj = self.client.extract_json(self.client.chat(system, hard_nudge))
                except Exception as e:
                    raise PolicyError(f"输出解析失败: {e}") from e
        self._last_reason = "json_prompt"
        return self._parse(obj, agent, view)

    # ---- 提示词 ----
    def _system(self, agent: Agent, view: SituationView) -> str:
        p = agent.position
        side_name = getattr(p, "side_name", "") or SIDE_NAME[p.side]
        role = ROLE_PROMPTS.get(p.archetype, "你是本阵营的一名军官。").format(
            side=side_name, title=p.title,
            units="、".join(p.units) or "无（参谋/机关职位）")
        directory = ["【通讯录（只能发给本阵营以下职位）】"]
        for q in view.registry.by_id.values():
            if q.side == p.side:
                directory.append(f"  {q.id} — {q.title}" + ("（只收不发）" if q.virtual else ""))
        # 场景注入的指挥风格/历史性格——"把智能体的各种设置准备好"就落在这里
        style = (p.config or {}).get("style")
        style_block = f"\n【你的指挥风格与性格】{style}\n" if style else ""
        return (
            f"{role}\n{chr(10).join(directory)}{style_block}\n"
            "【指挥规范】\n"
            "1. 收到上级命令先回确认（ack）再行动；完成阶段任务或战况变化时向上级发态势报告（sitrep）。\n"
            "2. 给下级的命令用任务式指挥：说明任务与目的，具体打法留给下级。\n"
            "3. 超出权限、损失过重或遇重大情况时向上请示/告警（request/escalation，priority=0）。\n"
            f"4. 你只能调动自己的部队：{'、'.join(p.units) or '无'}。"
            "world_actions 只能填这些单位，发给别的单位会被拒绝。\n"
            "5. 敌情来自侦察报告，有误差和延迟；不要臆造未报告的敌情。\n"
            "【输出】严格输出 JSON，不要任何其他文字：\n"
            '{"thoughts":"一句话决策理由",'
            '"messages":[{"to":"职位id","kind":"order|ack|sitrep|request|intel|plan|escalation",'
            '"subject":"简短主题","body":"正文","priority":0}],'
            '"world_actions":[{"kind":"move|attack|entrench|hold","unit":"单位id","target":[x,y]}]}\n"'
            "无新情况时输出空的 messages 与 world_actions。body 用简洁的中文军用文书语气。"
            " /no_think"
        )

    def _situation(self, agent: Agent, view: SituationView) -> str:
        p = agent.position
        lines = [f"当前 T{view.tick}。"]
        if agent.tasks:
            ts = "；".join(f"[{t.status}]{t.desc}" for t in agent.tasks[-4:])
            lines.append(f"任务台账：{ts}")
        if agent.memory:
            lines.append("近期纪要：\n  " + "\n  ".join(list(agent.memory)[-8:]))
        if agent.inbox:
            lines.append(f"待处理电文 {len(agent.inbox)} 件：")
            for m in agent.inbox[:10]:
                data = f" 数据:{json.dumps(m.data, ensure_ascii=False)[:200]}" if m.data else ""
                lines.append(f"  [T{m.tick}|{m.kind.value}] {view.title(m.sender)}→我《{m.subject}》{m.body[:160]}{data}")
        else:
            lines.append("待处理电文：无（本轮为周期性掌握态势）。")
        if view.own_units:
            lines.append("本部部队：" + view.units_summary())
        if view.intel:
            its = "；".join(f"敌{i['name']}@({i['x']},{i['y']}) T{i['tick']}"
                           for i in view.intel[-8:])
            lines.append(f"已知敌情：{its}")
        lines.append("请给出本轮决策 JSON。")
        return "\n".join(lines)

    # ---- 输出解析 ----
    def _parse(self, obj: dict, agent: Agent, view: SituationView) -> AgentDecision:
        msgs = []
        for md in obj.get("messages", [])[:8]:
            if not isinstance(md, dict):
                continue
            to = self._resolve_to(str(md.get("to", "")), view)
            if to is None:
                continue  # 收件人无法解析：静默丢弃（引擎侧另有越权拦截）
            kind = str(md.get("kind", "sitrep"))
            if kind not in _VALID_KINDS:
                kind = "sitrep"
            try:
                priority = max(0, min(2, int(md.get("priority", 1))))
            except (TypeError, ValueError):
                priority = 1
            msgs.append({
                "to": to, "kind": kind,
                "subject": str(md.get("subject", ""))[:80],
                "body": str(md.get("body", ""))[:600],
                "priority": priority,
                "data": md.get("data") if isinstance(md.get("data"), dict) else {},
            })
        acts = []
        for ad in obj.get("world_actions", [])[:6]:
            if not isinstance(ad, dict):
                continue
            try:
                acts.append(WorldAction(kind=ad.get("kind", "move"),
                                        unit=str(ad.get("unit", "")),
                                        target=ad.get("target")))
            except Exception:  # noqa: BLE001  畸形动作直接丢弃
                continue
        return AgentDecision(thoughts=str(obj.get("thoughts", ""))[:200],
                             messages=msgs, world_actions=acts)

    def _resolve_to(self, to: str, view: SituationView) -> str | None:
        if not to:
            return None
        p = view.registry.get(to)
        if p and p.side == view.camp_side:
            return to
        # 容错：模型可能写职位名称而非 id
        for q in view.registry.by_id.values():
            if q.side == view.camp_side and (to in q.title or q.title in to):
                return q.id
        return None
