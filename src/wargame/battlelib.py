"""战役定制库：把"一场战役像什么样"拆成通用、可量化的参数，让用户傻瓜式调节。

设计思路
--------
从十余场经典战役（两栖强攻、装甲纵深、城市巷战、山岭攻坚、极端天气突击……）
提炼出跨战役通用的参数维度，分为三层：

1. 环境层 env   —— 天气脚本 + 地形密集度（森林/丘陵/沼泽），决定战场"像什么地形、什么天气"
2. 全局层 global —— 直接映射世界引擎 tuning 键（战斗烈度/火力/装甲/机动/后勤/士气/空军……）
3. 阵营层 sides —— 每方独立实力维度（兵员数量 hp、火力 atk、装甲 def、机动力 speed、
                    后勤 supply、士气 spirit、制空 air），缺省 1.0 = 无修正

`apply_battle(sim, cfg)` 把一份 cfg 落进世界引擎：覆写 tuning、播种地形、设天气、
按方写入 side_mod（血量写入单位 strength_max）与空军力量。cfg 留空进场商店即退化为
原始想定（不调用则保持自带默认）。

前端据 PARAM_GROUPS 自动生成滑块组，据 BATTLE_PRESETS 渲染预置战役卡片；
一次点击即"套入精调 → 一键启动"。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 阵营层维度（两方/多方通用；每项可量化）
# ---------------------------------------------------------------------------
SIDE_DIMS: list[dict] = [
    {"key": "hp",     "label": "兵员数量", "unit": "倍",
     "hint": "整军总兵力当量：越高单位越耐打、战线越厚实。",
     "min": 0.3, "max": 2.5, "step": 0.1, "default": 1.0},
    {"key": "atk",    "label": "火力强度", "unit": "倍",
     "hint": "单兵/单车火力与弹药投射量：决定一次交火的输出。",
     "min": 0.2, "max": 3.0, "step": 0.1, "default": 1.0},
    {"key": "def",    "label": "装甲防护", "unit": "倍",
     "hint": "防护力（装甲/工事/反斜面）：越低越容易被一轮打穿。",
     "min": 0.2, "max": 3.0, "step": 0.1, "default": 1.0},
    {"key": "speed",  "label": "机动力",   "unit": "倍",
     "hint": "行军速度（摩托化/装甲化程度）：决定谁能先到位、先合围。",
     "min": 0.2, "max": 3.0, "step": 0.1, "default": 1.0},
    {"key": "supply", "label": "后勤补给", "unit": "倍",
     "hint": "补给站辐射效率：越高越能维持高强度连续作战。",
     "min": 0.2, "max": 3.0, "step": 0.1, "default": 1.0},
    {"key": "spirit", "label": "战斗意志", "unit": "倍",
     "hint": "士气/抗崩溃：越高，残兵越少因伤亡而整线崩盘。",
     "min": 0.2, "max": 3.0, "step": 0.1, "default": 1.0},
    {"key": "air",    "label": "制空权",   "unit": "分",
     "hint": "空中力量（0=无空军→1.5=绝对制空）：越高对敌方行军纵队的遮断越凶。",
     "min": 0.0, "max": 1.5, "step": 0.1, "default": 0.3},
]

_SIDE_DIM_DEFAULT = {d["key"]: d["default"] for d in SIDE_DIMS}

# ---------------------------------------------------------------------------
# 全局层参数（滑块 → 引擎 tuning 键；带上下限与傻瓜提示）
# ---------------------------------------------------------------------------
@dataclass
class Knob:
    id: str
    label: str
    group: str
    lo: float
    hi: float
    default: float
    step: float = 0.1
    hint: str = ""
    unit: str = ""

    @property
    def asdict(self) -> dict:
        return {"id": self.id, "label": self.label, "group": self.group,
                "min": self.lo, "max": self.hi, "step": self.step,
                "default": self.default, "unit": self.unit, "hint": self.hint}


GLOBAL_KNOBS: list[Knob] = [
    # —— 战斗烈度 ——
    Knob("combat_scale",      "伤亡烈度",   "战斗烈度", 0.3, 3.0, 1.0, hint="整场战役的杀伤与消耗节奏：越低越拉锯持久，越高越一击决胜负。"),
    Knob("entrench_bonus",    "工事纵深",   "战斗烈度", 0.0, 1.5, 0.4, hint="铁丝网/堑壕/堡垒纵深：越高，据守方的减伤越明显。"),
    Knob("flank_bonus",       "侧翼夹击",   "战斗烈度", 0.0, 2.0, 0.5, hint="多单位围攻加成：越高越鼓励穿插侧击、合围歼敌。"),
    Knob("overrun_scale",     "歼灭追击",   "战斗烈度", 0.0, 1.0, 0.25, hint="对已残破目标追加伤害：越高，败退之师越容易被全歼。"),
    # —— 地形与机动 ——
    Knob("terrain_def_scale","地形防御系数","地形与机动", 0.0, 2.5, 1.0, hint="森林/丘陵/沼泽给据守方的减伤加成倍率：越高，复杂地形越难啃。", unit="倍"),
    Knob("move_scale",        "全军机动性", "地形与机动", 0.3, 3.0, 1.0, hint="全体行军速度倍率：越高地图越显紧凑、节奏越快。", unit="倍"),
    Knob("terrain_cost_scale","越野难度",   "地形与机动", 0.3, 3.0, 1.0, hint="道路以外的越野通行难度：越高，森林/丘陵/渡场越拖慢装甲。", unit="倍"),
    Knob("road_bonus",        "道路效率",   "地形与机动", 0.3, 3.0, 1.0, hint="铁路公路的机动效率：越高，补给干线与机动走廊越值钱。", unit="倍"),
    Knob("arty_scale",        "炮兵威力",   "地形与机动", 0.3, 3.0, 1.0, hint="炮火对目标的杀伤倍率：火炮齐射在此战役中的分量。", unit="倍"),
    Knob("arty_range_scale",  "火炮射程",   "地形与机动", 0.5, 2.5, 1.0, hint="炮兵打击纵深：越高，后队可越远提供支援火力。", unit="倍"),
    # —— 后勤 ——
    Knob("supply_regen",      "补给恢复",   "后勤保障", 0.0, 15.0, 5.0, hint="补给站覆盖内每拍回复量：越高越能持续高强度作战。", unit="/拍"),
    Knob("supply_drain",      "补给消耗",   "后勤保障", 0.0, 12.0, 3.0, hint="脱离补给覆盖后每拍消耗：越高，断补给越致命。", unit="/拍"),
    Knob("depot_radius",      "补给半径",   "后勤保障", 2.0, 16.0, 7.0, hint="补给站辐射的曼哈顿格数：决定后勤弧线能铺多远。", unit="格"),
    Knob("supply_combat_scale","补给-战力", "后勤保障", 0.0, 1.0, 0.5, hint="补给影响战力的强度：拖泥带水（0）还是弹尽粮绝即瘫（1）。"),
    # —— 士气与认知 ——
    Knob("morale_scale",      "士气权重",   "士气与认知", 0.0, 2.0, 1.0, hint="战线崩溃机制的整体权重：越高，伤亡对战斗力的侵蚀越重。"),
    Knob("low_strength_penalty","残兵崩溃", "士气与认知", 0.0, 0.9, 0.3, hint="兵力低于四成时战力的折扣：越接近 1，残师越接近瘫痪。"),
    Knob("recon_scale",       "侦察覆盖",   "士气与认知", 0.3, 4.0, 1.0, hint="敌方踪迹能在多远被看到：越高战场信息越透。", unit="倍"),
    Knob("intel_error",       "敌情误差",   "士气与认知", 0.0, 3.0, 1.0, hint="敌情坐标的偏移格数：越大，情报迷雾越浓。", unit="±格"),
    # —— 空军遮断 ——
    Knob("air_scale",         "空袭强袭",   "空军遮断", 0.0, 3.0, 1.0, hint="空中遮断体系整体强度（0=关闭空战维度）。", unit="倍"),
    Knob("air_dmg",           "空袭威力",   "空军遮断", 0.0, 12.0, 3.0, hint="单次空袭对行军纵队的基准杀伤。", unit="伤"),
    Knob("air_prob",          "空袭频率",   "空军遮断", 0.0, 0.5, 0.12, hint="对已机动敌方单位的空袭命中概率基数。"),
]

_KNOB_DEFAULT = {k.id: k.default for k in GLOBAL_KNOBS}

# 只允许落进引擎的全局键（防御性过滤）
_ENGINE_TUNING_KEYS = set(_KNOB_DEFAULT)

# ---------------------------------------------------------------------------
# 环境层
# ---------------------------------------------------------------------------
WEATHER_OPTIONS = [
    {"id": "auto",     "label": "沿用想定", "script": None, "desc": "不覆盖，按所选想定的历史天气。"},
    {"id": "clear",    "label": "晴 · 视线良好", "script": [("clear")], "desc": "全天晴朗：空军遮断全功率，越野不怕泥泞。"},
    {"id": "overcast", "label": "阴 · 云层压顶", "script": [("overcast")], "desc": "多云：空军打折，地面坦克不再暴露于空中。"},
    {"id": "rain",     "label": "雨 · 泥泞攻坚", "script": [("rain")], "desc": "大雨：航空与机动同时受限，装甲深陷泥沼。"},
    {"id": "storm",    "label": "风暴 · 极端气象", "script": [("storm")], "desc": "风暴：天上几乎失明，越是登陆/渡河越是绝境。"},
]

ENV_KNOBS = [
    {"id": "forest", "label": "森林/树篱密布", "min": 0.0, "max": 1.0, "step": 0.05, "default": 0.0,
     "hint": "伏击与堑蔽并存：越高，装甲越难展开，步兵越有依托。"},
    {"id": "hill",   "label": "丘陵高地",     "min": 0.0, "max": 1.0, "step": 0.05, "default": 0.0,
     "hint": "山地要点：给据守方地利加成，也藏得住炮位。"},
    {"id": "swamp",  "label": "沼泽/水网",    "min": 0.0, "max": 1.0, "step": 0.05, "default": 0.0,
     "hint": "科唐坦式水网：迟滞一切快速部队，把战场切成窄道。"},
]

# ---------------------------------------------------------------------------
# 12 场经典战役预置
# ---------------------------------------------------------------------------
@dataclass
class BattlePreset:
    pid: str
    name: str
    codename: str
    era: str
    theater: str
    category: str          # 两栖强攻 / 装甲纵深 / 城市巷战 / 山岭攻坚 / 极端天气 / 大兵团会战
    desc: str
    env: dict              # env 参数模板（weather + 地形密度）
    params: dict           # global knob 覆盖
    sides: list[dict]      # 按顺序作用于当前想定的各方（第 i 方 ← sides[i]）
    briefing: str = ""     # 战役简报全文（简报屏幕 + 推演中战报用）

    def meta(self) -> dict:
        r = {"id": self.pid, "name": self.name, "codename": self.codename,
             "era": self.era, "theater": self.theater, "category": self.category,
             "desc": self.desc, "env": self.env, "params": self.params,
             "sides": self.sides}
        if self.briefing:
            r["briefing"] = self.briefing
        return r


_S = lambda d: {**_SIDE_DIM_DEFAULT, **d}  # noqa: E731  d 为 {dim: 值} 覆盖缺省

BATTLE_PRESETS: list[BattlePreset] = [
    # —— 两栖强攻 ——
        BattlePreset(
        "normandy_1944", "诺曼底登陆『霸王行动』", "OVERLORD · D-DAY", "二战 1944·6",
        "英吉利海峡 · 滩头 → 内陆", "两栖强攻",
        "史上最大两栖战役：盟军五滩上陆、空降控扼侧翼，德军依托大西洋壁垒与装甲预备队反突击。风暴、滩头、沼泽水网并存。",
        {"weather": "storm", "forest": 0.25, "hill": 0.12, "swamp": 0.16},
        {"combat_scale": 1.2, "terrain_cost_scale": 1.5, "entrench_bonus": 0.75,
         "depot_radius": 5, "supply_combat_scale": 0.6, "air_scale": 1.4},
        [_S({"hp": 1.0, "atk": 1.2, "def": 0.9, "speed": 0.9, "supply": 1.2, "spirit": 1.1, "air": 1.2}),
         _S({"hp": 1.2, "atk": 0.9, "def": 1.5, "speed": 0.7, "supply": 0.8, "spirit": 1.3, "air": 0.2})],
        briefing="""【战役背景】
1944年6月6日，盟军发起"霸王行动"(Operation Overlord)，在法国诺曼底五处海滩实施人类历史上规模最大的两栖登陆作战。美英加三国联军约156,000人分东西两线同时上陆， airborne空降兵在前夜控扼侧翼交通枢纽；德军依托大西洋壁垒一线设防，装甲预备队部署在内陆待命。

【兵力对比】
美军（西侧）：主攻奥马哈、犹他两滩，以第29、第4步兵师为第一波，第82、第101空降师 airborne 纵深着陆。火力占优，舰炮与航空支援充足。
英加军（东侧）：主攻宝剑、朱诺、黄金三滩，第3步兵师与加第3师先上陆，第6空降师控制奥恩河桥梁。目标为夺卡昂，打通内陆通道。
德军：第7集团军驻守法国西北部海岸，第352步兵师固守奥马哈附近。装甲师分散部署，需铁路机动集结。防御体系依托混凝土碉堡与海岸障碍。

【地形要点】
科唐坦半岛西部水网纵横，沼泽与树篱交错——德军称" bocage"，是装甲部队最大的天敌。东海岸相对平坦，适合大规模机动。多座桥梁跨越奥恩河与维河的交汇处是必争的战略节点。

【天气预判】
登陆当日风暴肆虐，浪高超过预期，航空掩护大幅打折；登陆后2-3天转阴，随后渐晴。气象变化将在整个战役期间持续影响空军出击率与地面机动。

【历史参考】
D-Day 伤亡约10,000人（其中美军奥马哈海滩尤为惨烈），盟军成功建立稳固滩头阵地，为最终解放西欧奠定基础。战役持续约90天，以法莱斯包围战告终，德军西线主力被歼灭。"""),
    BattlePreset(
        "iwo_jima_1945", "硫磺岛战役", "DETACHMENT", "太平洋 1945·2", "火山岛 · 折钵山矶部",
        "两栖强攻",
        "八平方公里火山岛，硫磺土让坦克深陷、机枪隧道纵横。美军以压倒性海空力量强攻，日军一线死守、纵深坑道抵抗到底。",
        {"weather": "clear", "forest": 0.0, "hill": 0.28, "swamp": 0.22},
        {"combat_scale": 1.3, "terrain_cost_scale": 1.9, "entrench_bonus": 1.2,
         "air_scale": 1.6, "arty_scale": 1.4, "recon_scale": 0.8},
        [_S({"hp": 1.4, "atk": 1.1, "def": 0.7, "speed": 0.8, "supply": 1.0, "spirit": 1.0, "air": 1.4}),
         _S({"hp": 0.8, "atk": 1.0, "def": 2.0, "speed": 0.4, "supply": 0.5, "spirit": 1.3, "air": 0.0})]),
    BattlePreset(
        "okinawa_1945", "冲绳战役『冰雹』", "ICEBERG", "太平洋 1945·4", "琉球群岛 · 全境攻坚",
        "两栖强攻",
        "太平洋战场最后也是最大的登陆战。神风特攻与海军炮轰并举，日军依托全岛纵深工事打消耗仗，血流成河。",
        {"weather": "overcast", "forest": 0.3, "hill": 0.24, "swamp": 0.12},
        {"combat_scale": 1.35, "terrain_def_scale": 1.4,
         "air_scale": 1.2, "air_dmg": 4.5, "air_prob": 0.18, "supply_combat_scale": 0.6},
        [_S({"hp": 1.3, "atk": 1.2, "def": 0.8, "speed": 0.85, "supply": 1.1, "spirit": 1.0, "air": 1.3}),
         _S({"hp": 1.1, "atk": 1.0, "def": 1.9, "speed": 0.5, "supply": 0.6, "spirit": 1.5, "air": 0.0})]),
    # —— 装甲纵深 ——
    BattlePreset(
        "kursk_1943", "库尔斯克会战『堡垒』", "ZITADELLE", "苏德 1943·7", "库尔斯克突出部",
        "装甲纵深",
        "人类史上最大的坦克会战。德军以装甲矛头南北对进，苏军布设纵深反坦克阵地层层剥壳；防线延绵，机动与堡垒激烈拉锯。",
        {"weather": "clear", "forest": 0.18, "hill": 0.16, "swamp": 0.08},
        {"combat_scale": 0.9, "flank_bonus": 0.8, "overrun_scale": 0.3,
         "terrain_def_scale": 1.3, "entrench_bonus": 0.7, "move_scale": 1.2},
        [_S({"hp": 1.1, "atk": 0.95, "def": 1.2, "speed": 1.0, "supply": 0.9, "spirit": 0.9, "air": 0.3}),
         _S({"hp": 1.3, "atk": 1.15, "def": 1.5, "speed": 1.1, "supply": 0.9, "spirit": 1.3, "air": 0.6})]),
    BattlePreset(
        "el_alamein_1942", "阿拉曼战役", "LIGHTFOOT", "北非 1942·10", "埃及西部沙漠",
        "装甲纵深",
        "北非机动作战的转折点。英军在绝对物资优势下正面强攻，隆美尔非洲军团补给濒绝、机动衰退，被逐出阿拉曼防线。",
        {"weather": "clear", "forest": 0.0, "hill": 0.22, "swamp": 0.0},
        {"combat_scale": 1.1, "move_scale": 1.5, "road_bonus": 1.3, "arty_scale": 1.2,
         "supply_combat_scale": 0.7, "low_strength_penalty": 0.4},
        [_S({"hp": 1.3, "atk": 1.1, "def": 0.9, "speed": 1.2, "supply": 1.4, "spirit": 1.0, "air": 1.1}),
         _S({"hp": 1.0, "atk": 1.1, "def": 1.1, "speed": 1.1, "supply": 0.5, "spirit": 1.0, "air": 0.4})]),
    BattlePreset(
        "bulge_1944", "阿登反击战『守望莱茵』", "WACHT AM RHEIN", "西线 1944·12", "阿登森林",
        "极端天气",
        "德军在恶劣风雪中发起的装甲奇袭，企图重演1940年闪击割裂盟军。浓云令空军瘫痪，装甲纵队曾一度深插；天气一转晴又成强弩之末。",
        {"weather": "storm", "forest": 0.34, "hill": 0.2, "swamp": 0.0},
        {"combat_scale": 1.15, "air_scale": 0.4, "air_dmg": 4.0,
         "terrain_cost_scale": 1.6, "move_scale": 1.2, "low_strength_penalty": 0.5},
        [_S({"hp": 1.0, "atk": 1.3, "def": 1.1, "speed": 1.3, "supply": 0.7, "spirit": 1.4, "air": 0.1}),
         _S({"hp": 1.2, "atk": 0.9, "def": 1.0, "speed": 0.9, "supply": 1.4, "spirit": 0.9, "air": 1.4})]),
    # —— 城市巷战 ——
    BattlePreset(
        "stalingrad_1942", "斯大林格勒会战", "URANUS", "苏德 1942·8", "伏尔加河畔城市带",
        "城市巷战",
        "人类历史上最惨烈的城市绞肉机。巷战把战场切割成废墟与地下室，双方在每一栋楼反复争夺；补给与救援只有一条窄道。",
        {"weather": "overcast", "forest": 0.05, "hill": 0.08, "swamp": 0.0},
        {"combat_scale": 1.4, "entrench_bonus": 1.2, "terrain_cost_scale": 1.4,
         "depot_radius": 4, "supply_combat_scale": 0.8, "arty_scale": 1.3},
        [_S({"hp": 1.2, "atk": 1.0, "def": 1.6, "speed": 0.6, "supply": 0.7, "spirit": 1.5, "air": 0.3}),
         _S({"hp": 1.0, "atk": 1.25, "def": 1.1, "speed": 0.8, "supply": 0.9, "spirit": 1.2, "air": 0.8})],
        briefing="""\
【战役背景】
1942年8月，德军第6集团军向斯大林格勒发起进攻，意图夺取伏尔加河畔工业城市，切断苏军南翼补给线。苏军以第62、第64集团军在城内有组织地实施逐街逐屋抵抗，将德军拖入惨烈的城市消耗战。

【兵力对比】
苏军（ defenders）：第62集团军（崔可夫）守城核心，依托伏尔加河东岸建立补给通道；第64集团军负责外围支援。总兵力约16万人，弹药与粮食极度匮乏，但士气高昂。
德军（ attackers）：第6集团军（保卢斯）为主攻力量，辅以罗马尼亚第3、第4集团军掩护侧翼。总兵力约27万人，装甲与火力占优，但补给线过长、侧翼薄弱。

【地形要点】
伏尔加河是唯一补给生命线，渡河船艇随时遭空袭。市区内工厂区、火车站、巴甫洛夫大楼等关键点成为反复争夺的堡垒。10月后气温骤降，未做好冬装的部队战斗效能急剧下降。

【天气预判】
8-9月秋高气爽，利于德军装甲机动；10月起秋雨连绵，泥泞延缓一切行动；11月冬雪降临，双方均遭受严寒考验。苏军反攻时机选择在德军侧翼由罗军把守的薄弱地带。

【历史参考】
斯大林格勒战役是二战苏德战场的转折点，德军第6集团军全军覆没，约30万人伤亡或被俘。城市巷战的惨烈程度令后世震惊，战役深刻体现了"组织摩擦"在极端条件下对胜负的决定性影响。"""),
    BattlePreset(
        "berlin_1945", "柏林战役", "BASTION", "苏德 1945·4", "德国首都 · 决战",
        "城市巷战",
        "欧洲第二次大战的终点。苏军以绝对兵力对柏林发起总攻，红军以德军的厌战崩溃与装备衰弱对最后的堡垒群展开巷战。",
        {"weather": "rain", "forest": 0.0, "hill": 0.06, "swamp": 0.0},
        {"combat_scale": 1.5, "entrench_bonus": 1.0, "arty_scale": 1.5, "air_dmg": 4.5,
         "supply_regen": 7.0, "low_strength_penalty": 0.6},
        [_S({"hp": 1.8, "atk": 1.2, "def": 0.8, "speed": 0.9, "supply": 1.3, "spirit": 1.1, "air": 1.0}),
         _S({"hp": 0.7, "atk": 0.8, "def": 1.4, "speed": 0.5, "supply": 0.5, "spirit": 0.6, "air": 0.1})]),
    # —— 山岭攻坚 ——
    BattlePreset(
        "monte_cassino_1944", "卡西诺战役", "OLIVE", "意大利 1944·1", "古斯塔夫防线 · 卡西诺山",
        "山岭攻坚",
        "盟军为打通罗马钥匙而围攻卡西诺修道院附近的高地群。山岭给守军天然纵深，德军一段防线守了数月；正面强攻代价惨重。",
        {"weather": "rain", "forest": 0.2, "hill": 0.4, "swamp": 0.0},
        {"combat_scale": 1.25, "terrain_def_scale": 1.8, "entrench_bonus": 1.0,
         "terrain_cost_scale": 1.8, "move_scale": 0.8, "arty_scale": 1.3},
        [_S({"hp": 1.2, "atk": 1.0, "def": 0.7, "speed": 0.7, "supply": 1.0, "spirit": 0.9, "air": 1.0}),
         _S({"hp": 0.9, "atk": 0.9, "def": 2.2, "speed": 0.4, "supply": 0.7, "spirit": 1.3, "air": 0.2})]),
    # —— 大兵团会战 ——
    BattlePreset(
        "barbarossa_1941", "巴巴罗萨行动", "BARBAROSSA", "苏德 1941·6", "东线纵深 2000 公里",
        "大兵团会战",
        "史上最大规模的军事入侵。德军用装甲钳形运动战包围并消灭苏军重兵集团，纵深辽阔、补给线被拉至极限，机动优势空前。",
        {"weather": "clear", "forest": 0.28, "hill": 0.14, "swamp": 0.12},
        {"combat_scale": 1.2, "move_scale": 1.4, "road_bonus": 1.4, "flank_bonus": 1.0,
         "supply_drain": 4.5, "depot_radius": 5, "air_scale": 1.2},
        [_S({"hp": 1.0, "atk": 1.2, "def": 1.1, "speed": 1.3, "supply": 0.7, "spirit": 1.2, "air": 0.7}),
         _S({"hp": 1.6, "atk": 0.8, "def": 0.7, "speed": 0.7, "supply": 0.6, "spirit": 0.6, "air": 0.4})]),
    BattlePreset(
        "guadalcanal_1942", "瓜达尔卡纳尔战役", "WATCHTOWER", "太平洋 1942·8", "所罗门群岛雨林",
        "大兵团会战",
        "太平洋由守转攻的转折。美日在丛林与泥沼中打消耗与增援的拉锯战，补给在恶劣海况下时断时续，双方在雨林中困兽犹斗。",
        {"weather": "rain", "forest": 0.42, "hill": 0.1, "swamp": 0.28},
        {"combat_scale": 1.3, "terrain_cost_scale": 1.9, "supply_combat_scale": 0.8,
         "supply_regen": 3.0, "supply_drain": 5.0, "recon_scale": 0.7},
        [_S({"hp": 1.1, "atk": 1.0, "def": 0.8, "speed": 0.6, "supply": 0.6, "spirit": 0.9, "air": 0.8}),
         _S({"hp": 0.9, "atk": 1.0, "def": 1.0, "speed": 0.7, "supply": 0.5, "spirit": 1.1, "air": 0.5})]),
    BattlePreset(
        "gettysburg_1863", "葛底斯堡会战", "THE HIGH WATER MARK", "内战 1863·7", "宾夕法尼亚高岗",
        "线膛时代会战",
        "美军内战最血腥的一战。线膛枪在开阔高地上把正面冲锋打成绞肉阵，两军短促机动后陷入集约兵力的消耗对峙。",
        {"weather": "clear", "forest": 0.16, "hill": 0.24, "swamp": 0.0},
        {"combat_scale": 1.4, "move_scale": 0.6, "terrain_def_scale": 1.2,
         "entrench_bonus": 0.3, "arty_scale": 0.9, "air_scale": 0.0,
         "morale_scale": 1.4, "low_strength_penalty": 0.55},
        [_S({"hp": 1.0, "atk": 0.9, "def": 0.8, "speed": 0.7, "supply": 0.8, "spirit": 1.2, "air": 0.0}),
         _S({"hp": 0.95, "atk": 1.0, "def": 0.9, "speed": 0.7, "supply": 0.8, "spirit": 1.3, "air": 0.0})]),
    BattlePreset(
        "poland_1939", "波兰战役『白色方案』", "FALL WEISS", "二战 1939·9", "波兰走廊 · 平原突进",
        "大兵团会战",
        "二战开篇的装甲闪击战。德军以坦克与俯冲轰炸机组成的闪电战撕开波军防线，机动力与火力的代差在开阔平原上化为鹅卵石般的突进。",
        {"weather": "clear", "forest": 0.12, "hill": 0.1, "swamp": 0.06},
        {"combat_scale": 1.15, "move_scale": 1.5, "road_bonus": 1.3, "flank_bonus": 1.2,
         "overrun_scale": 0.5, "air_scale": 1.4, "arty_scale": 1.2},
        [_S({"hp": 1.1, "atk": 1.3, "def": 1.1, "speed": 1.5, "supply": 1.0, "spirit": 1.2, "air": 1.1}),
         _S({"hp": 1.0, "atk": 0.7, "def": 0.8, "speed": 0.6, "supply": 0.8, "spirit": 0.7, "air": 0.3})]),
]

BATTLE_PRESET_MAP: dict[str, BattlePreset] = {p.pid: p for p in BATTLE_PRESETS}

# ---------------------------------------------------------------------------
# 应用：把一份战役定制 cfg 落进世界引擎
# ---------------------------------------------------------------------------
def apply_battle(sim, cfg: dict | None) -> dict:
    """把战役定制应用到 sim。返回实际生效摘要（供前端展示当前配置）。
    cfg 为空/None：只清理战役作用（调回想定原始），不清掉 tuning（那属于设置面板）。"""
    cfg = cfg or {}
    env = cfg.get("env") or {}
    globs = cfg.get("global") or {}
    sides = cfg.get("sides") or {}
    world = sim.world

    # 1) 全局 tuning 覆盖（只写引擎已知键，并夹在合法区间内）
    for k, v in globs.items():
        if k not in _ENGINE_TUNING_KEYS:
            continue
        knob = next((g for g in GLOBAL_KNOBS if g.id == k), None)
        if knob is None:
            continue
        try:
            world.tuning[k] = max(knob.lo, min(knob.hi, float(v)))
        except (TypeError, ValueError):
            continue

    # 2) 环境层：天气脚本
    w = env.get("weather") or "auto"
    if w in ("clear", "overcast", "rain", "storm"):
        world.set_weather([(0, w)])

    # 3) 环境层：地形密集度播种（森林/丘陵/沼泽），保留地图原有要素
    for key in ("forest", "hill", "swamp"):
        if key in env:
            try:
                env[key] = max(0.0, min(1.0, float(env[key])))
            except (TypeError, ValueError):
                env[key] = 0.0
    if any(v > 0 for v in (env.get("forest", 0), env.get("hill", 0), env.get("swamp", 0))):
        world.geo_seed(env.get("forest", 0), env.get("hill", 0), env.get("swamp", 0))

    # 4) 阵营层：side_mod（血量→当量）+ 空军力量
    mods, air = {}, {}
    for fid, m in (sides or {}).items():
        if fid not in sim.factions or not isinstance(m, dict):
            continue
        mods[fid] = {k: _clamp_side(k, m.get(k, 1.0)) for k in _SIDE_DIM_DEFAULT if k != "air"}
        air[fid] = max(0.0, min(1.5, _float_or(m.get("air"), 0.3)))
    if mods:
        world.set_side_mods(mods)
    if air:
        world.set_air_power({**world.air_power, **air})

    return summarize(sim, cfg)


def summarize(sim, cfg: dict | None) -> dict:
    cfg = cfg or {}
    return {
        "preset": cfg.get("preset") or "",
        "env": dict(cfg.get("env") or {}),
        "global": dict(cfg.get("global") or {}),
        "sides": {fid: dict(m) for fid, m in (cfg.get("sides") or {}).items()},
    }


def _clamp_side(key: str, v) -> float:
    d = next(x for x in SIDE_DIMS if x["key"] == key)
    return max(d["min"], min(d["max"], _float_or(v, d["default"])))


def _float_or(v, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------

def reset_battle(sim) -> None:
    """将世界引擎 tuning 恢复为 DEFAULT_TUNING 默认值，用于战役定制撤销。"""
    from .engine.world import DEFAULT_TUNING
    sim.world.tuning.clear()
    sim.world.tuning.update(DEFAULT_TUNING)

# ---------------------------------------------------------------------------
def global_knobs_meta() -> list[dict]:
    return [k.asdict for k in GLOBAL_KNOBS]


def presets_meta() -> list[dict]:
    return [p.meta() for p in BATTLE_PRESETS]


def params_meta() -> dict:
    return {
        "side_dims": SIDE_DIMS,
        "global": global_knobs_meta(),
        "env": ENV_KNOBS,
        "weather": WEATHER_OPTIONS,
        "side_default": dict(_SIDE_DIM_DEFAULT),
    }
