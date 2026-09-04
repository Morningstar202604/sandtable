"""编制表（ORBAT）：职位即智能体。

组织树 + 每个职位的职责卡。职位声明了权限边界（能指挥哪些部队、
能向谁报告），智能体层据此做硬校验——越权命令在提交处被拦截，
而不是靠提示词自觉。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .schemas import SIDE_NAME, Side

SIDE_CODE = {"red": "红", "blue": "蓝"}


class Position(BaseModel):
    """一个指挥职位。id 形如 red:div1；虚拟职位（上级司令部）不挂智能体。"""

    id: str
    title: str
    side: Side
    side_name: str = ""          # 阵营显示名（红军/盟军/德军…），供角色卡与前端用
    archetype: str = ""          # 角色原型：army_cmd / cos / intel / log / div_cmd / reg_cmd
    parent: str | None = None
    units: list[str] = Field(default_factory=list)  # 直接指挥的世界单位 id
    staff: bool = False          # 参谋职位：无指挥权，只服务主官
    virtual: bool = False        # 虚拟职位（如上级司令部）：只收不发，不挂智能体
    config: dict = Field(default_factory=dict)  # 场景定制：指挥风格/性格/行为参数覆盖


# 角色卡：注入每个智能体 system prompt 的职责与指挥规范。
# 任务式指挥（Auftragstaktik）：上级给"任务-意图"，"如何达成"留给下级裁量。
# {side} 是阵营名（红军/蓝军/盟军/德军…由场景决定），{title} 是职位全名。
ROLE_PROMPTS: dict[str, str] = {
    "army_cmd": (
        "你是{side}{title}，本阵营最高指挥员。职责：接收上级意图，定下作战决心，"
        "向所属部队主官下达任务式命令（说明任务、目的与约束，不规定具体打法），"
        "掌握战役进程并向上级报告。你有权直接调动：{units}。"
    ),
    "cos": (
        "你是{side}{title}。职责：依据主官意图拟定作战方案，通常给出两个以上选项"
        "（含主攻方向与各部任务区分），供主官择定。你无权直接指挥部队。"
    ),
    "intel": (
        "你是{side}{title}。职责：汇总各部侦察上报的敌情，剔除重复与过期信息，"
        "形成简明敌情通报呈报主官。你无权指挥部队。"
    ),
    "log": (
        "你是{side}{title}。职责：受理部队补给与后送请示，安排前送并答复请示单位，"
        "重大保障困难上报主官。你无权指挥战斗部队。"
    ),
    "div_cmd": (
        "你是{side}{title}。职责：受领上级任务后，向所属团主官下达命令（保留机动兵力，"
        "组织配属炮兵火力支援），掌握本部战况并向上级报告。你有权直接调动：{units}（直属），"
        "下属团部队只能通过给团主官下达命令来调动。"
    ),
    "reg_cmd": (
        "你是{side}{title}。职责：受领上级命令后组织本部行动，"
        "占领目标后按命令中的后续任务自主推进，并及时向上报告战况与损失。"
        "你有权调动：{units}。损失过重或遇重大情况时向上告警请示。"
    ),
}


def _pos(side: Side, key: str, title: str, archetype: str, parent: str | None,
         units: list[str] | None = None, staff: bool = False,
         virtual: bool = False, side_name: str = "",
         config: dict | None = None) -> Position:
    return Position(
        id=f"{side}:{key}", title=title, side=side, archetype=archetype,
        parent=parent, units=units or [], staff=staff, virtual=virtual,
        side_name=side_name, config=config or {},
    )


def build_camp_org(side: Side, titles: dict[str, str] | None = None,
                   side_name: str | None = None,
                   configs: dict[str, dict] | None = None,
                   orbat: list[dict] | None = None) -> list[Position]:
    """构建一个阵营的完整指挥体系（ORBAT）。

    结构固定（军—师—团 × 2）能满足标准训练想定；但一场"各种大型战役"
    往往有不同兵力编成、不同指挥层级——为此支持场景用 orbat 覆盖整棵编制：
      orbat: [{key, title?, archetype, parent?, units?, staff?, virtual?}]
    parent 可写简写键（如 "army"）或全名（如 "red:army"）。
    命名、职位级配置（指挥风格/性格/行为参数）始终可由场景 titles/configs 覆盖。
    """
    s = side_name or SIDE_NAME.get(side, side)
    t = titles or {}
    cf = configs or {}
    u = lambda n: f"{side}-u-{n}"  # noqa: E731  世界单位 id 前缀与阵营一致

    def t_title(key: str, default: str) -> str:
        return t.get(key, default)

    # 场景自定义编制：真正意义的各种大型战役不必套固定模板
    if orbat:
        out: list[Position] = []
        for node in orbat:
            key = node["key"]
            parent = node.get("parent")
            if parent and not str(parent).startswith(f"{side}:"):
                parent = f"{side}:{parent}"
            out.append(_pos(
                side, key,
                node.get("title") or t_title(key, str(key)),
                node.get("archetype", "army_cmd"),
                parent,
                units=[u(str(x)) for x in node.get("units", [])],
                staff=bool(node.get("staff", False)),
                virtual=bool(node.get("virtual", False)),
                side_name=s, config=cf.get(key)))
        return out

    positions = [
        # 上级司令部：虚拟职位，只注入任务不参与推演
        _pos(side, "hq", t_title("hq", f"上级统帅部（{s}）"), "hq", None,
             virtual=True, side_name=s, config=cf.get("hq")),
        _pos(side, "army", t_title("army", f"{s}集团军司令"), "army_cmd", f"{side}:hq",
             units=[u("r1")], side_name=s, config=cf.get("army")),
        _pos(side, "cos", t_title("cos", f"{s}参谋长"), "cos", f"{side}:army",
             staff=True, side_name=s, config=cf.get("cos")),
        _pos(side, "intel", t_title("intel", f"{s}情报参谋"), "intel", f"{side}:army",
             staff=True, side_name=s, config=cf.get("intel")),
        _pos(side, "log", t_title("log", f"{s}后勤参谋"), "log", f"{side}:army",
             staff=True, side_name=s, config=cf.get("log")),
        _pos(side, "div1", t_title("div1", f"{s}第1突击师师长"), "div_cmd", f"{side}:army",
             units=[u("a1")], side_name=s, config=cf.get("div1")),
        _pos(side, "div2", t_title("div2", f"{s}第2装甲师师长"), "div_cmd", f"{side}:army",
             units=[u("a2")], side_name=s, config=cf.get("div2")),
        _pos(side, "div1-b1", t_title("div1-b1", f"{s}第1团团长"), "reg_cmd", f"{side}:div1",
             units=[u("b1")], side_name=s, config=cf.get("div1-b1")),
        _pos(side, "div1-b2", t_title("div1-b2", f"{s}第2团团长"), "reg_cmd", f"{side}:div1",
             units=[u("b2")], side_name=s, config=cf.get("div1-b2")),
        _pos(side, "div2-b3", t_title("div2-b3", f"{s}第3团团长"), "reg_cmd", f"{side}:div2",
             units=[u("b3")], side_name=s, config=cf.get("div2-b3")),
        _pos(side, "div2-b4", t_title("div2-b4", f"{s}第4团团长"), "reg_cmd", f"{side}:div2",
             units=[u("b4")], side_name=s, config=cf.get("div2-b4")),
        # 前线侦察哨：虚拟职位，引擎的敌情速报以此名义流入情报参谋
        _pos(side, "front", t_title("front", "前线侦察哨"), "front", f"{side}:army",
             virtual=True, side_name=s, config=cf.get("front")),
    ]
    return positions


class Registry:
    """全量职位注册表（红蓝都在），供编址、层级查询与越权校验使用。"""

    def __init__(self, positions: list[Position]) -> None:
        self.by_id: dict[str, Position] = {p.id: p for p in positions}

    def get(self, pos_id: str) -> Position | None:
        return self.by_id.get(pos_id)

    def title(self, pos_id: str) -> str:
        p = self.by_id.get(pos_id)
        if p:
            return p.title
        if pos_id.startswith("unit:"):
            return f"部队[{pos_id[5:]}]"
        return pos_id

    def children(self, pos_id: str) -> list[Position]:
        return [p for p in self.by_id.values() if p.parent == pos_id]

    def agents(self, side: Side) -> list[Position]:
        """按层级排序返回该阵营需要挂智能体的职位。

        参谋职位（staff）同样挂智能体——他们要思考、要发方案，
        只是没有部队指挥权（权限由 units 列表约束）。
        virtual 职位（上级司令部/侦察哨）只是消息地址，不参与决策。
        """
        rank = {"army_cmd": 0, "cos": 1, "intel": 2, "log": 3, "div_cmd": 4, "reg_cmd": 5}
        return sorted(
            (p for p in self.by_id.values()
             if p.side == side and not p.virtual),
            key=lambda p: rank.get(p.archetype, 9),
        )

    def owner_of_unit(self, unit_id: str) -> Position | None:
        for p in self.by_id.values():
            if unit_id in p.units:
                return p
        return None

    def same_camp(self, a: str, b: str) -> bool:
        pa, pb = self.get(a), self.get(b)
        return bool(pa and pb and pa.side == pb.side)
