"""世界引擎：让组织层的命令产生真实后果。

只负责机动、交战、补给、侦察、天气/空军遮断、补给站争夺、战役目标。
所有随机性来自注入的 rng——固定种子整场可复现。引擎是双方共享的
"物理世界"，也是两阵营之间唯一的间接通道（行动 → 世界 → 对方侦察）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..schemas import WorldAction

GRID_W, GRID_H = 24, 16

# 进入地形的机动点消耗。桥梁消耗刻意调高——渡场拥堵是组织摩擦的真实来源
# "m" 沼泽：诺曼底科唐坦水网，迟滞装甲；"r" 道路/铁路：重建机动力走廊
ENTER_COST: dict[str, float] = {".": 1.0, "f": 2.0, "h": 1.5, "B": 2.0, "C": 1.5,
                                "m": 3.0, "r": 0.6}
# 防御地形加成：受伤量除以 (1 + bonus)
TERRAIN_DEF: dict[str, float] = {"f": 0.25, "h": 0.35, "C": 0.5, "m": 0.1}

#            机动/拍  攻击  防护  射程(曼哈顿)  侦察半径
UNIT_STATS = {
    "infantry":  (1, 1.0, 1.0, 1, 2),
    "armor":     (2, 1.5, 1.0, 1, 2),
    "artillery": (1, 1.8, 0.5, 4, 1),
    "recon":     (2, 0.3, 0.6, 1, 5),
}
UNIT_GLYPH = {"infantry": "步", "armor": "装", "artillery": "炮", "recon": "侦"}
UNIT_NAME = {"infantry": "步兵", "armor": "装甲", "artillery": "炮兵", "recon": "侦察"}

# 天气对空军遮断的放大系数（storm 基本瘫痪空中力量——1944 年 6 月 6 日）
WEATHER_AIR = {"clear": 1.0, "overcast": 0.5, "rain": 0.3, "storm": 0.1}
WEATHER_CN = {"clear": "晴", "overcast": "阴", "rain": "雨", "storm": "风暴"}

# 可调参数默认值（Web 设置面板实时可改；dict 以引用共享给 sim/host）
DEFAULT_TUNING: dict = {
    # 战斗
    "combat_scale": 1.0,        # 全局伤害倍率
    "arty_scale": 1.0,          # 炮兵伤害倍率
    "entrench_bonus": 0.4,      # 工事防御加成（受伤除以 1+bonus）
    "terrain_def_scale": 1.0,   # 地形防御加成倍率
    "supply_combat_scale": 0.5, # 补给影响战力的强度（0=无影响，1=完全由补给决定）
    # 士气与战损
    "morale_scale": 1.0,        # 士气影响强度（放大幅值；0=士气无影响）
    "low_strength_penalty": 0.3,# 兵力低于 40% 时的战力折扣（0=无，1=几乎崩溃）
    "flank_bonus": 0.5,         # 侧翼夹击：围攻同一目标时每多一人的伤害加成
    "overrun_scale": 0.25,      # 追击：对已残损目标按战损比例追加的伤害
    # 机动
    "move_scale": 1.0,          # 单位移速倍率
    "road_bonus": 1.0,          # 道路/铁路机动效率倍率（越大路走得越快）
    "terrain_cost_scale": 1.0,  # 越野通行惩罚倍率（沼泽/森林/渡场越难走）
    "arty_range_scale": 1.0,    # 炮兵射程倍率（影响射程判定与停车保持火力）
    # 后勤
    "supply_regen": 5.0,        # 补给站半径内每拍回复
    "supply_drain": 3.0,        # 补给站半径外每拍消耗
    "depot_radius": 7,          # 补给站作用半径（曼哈顿格）
    # 侦察
    "recon_scale": 1.0,         # 侦察半径倍率
    "intel_error": 1,           # 敌情坐标误差（±格）
    # 智能体节奏（rule 策略经共享字典读取；LLM 模式下影响唤醒周期）
    "report_interval": 8,       # 例行报告间隔（拍）
    "withdraw_threshold": 40,   # 兵力低于此值触发告警并转入据守
    "contact_fwd_interval": 4,  # 接触战况上报的最小间隔（拍）
    # 智能体性格与认知
    "aggression_scale": 1.0,    # 进攻倾向：越高越敢打（等效压低告警撤退阈值）
    "escalation_delay": 0,      # 告警上报延迟（拍）：连败几拍才向上告警
    "memory_size": 40,          # 每个子智能体的记忆容量（条）
    # 空军遮断
    "air_scale": 1.0,           # 遮断强度倍率（0 = 关闭空军）
    "air_dmg": 3.0,             # 单次遮断打击基准伤害
    "air_prob": 0.12,           # 对每个已机动敌单位的遮断命中概率基数
    # === 战役特征增强（v6）===
    # 昼夜循环
    "daynight_enabled": 0,      # 1=启用昼夜循环（0/24拍晴昼，6/18昏，12夜）; 0=恒昼
    "night_recon": 0.6,         # 夜间侦察半径倍率
    "night_arty": 0.7,          # 夜间炮兵射程倍率
    "night_melee": 0.8,         # 夜间接战伤害倍率
    "night_move": 0.8,          # 夜间机动速度倍率
    # 疲劳与休整
    "fatigue_enabled": 1,       # 1=启用疲劳（连续作战/机动累积疲劳→战力衰减）
    "fatigue_move": 0.8,        # 每次机动累积的疲劳
    "fatigue_combat": 1.2,      # 每次交火累积的疲劳
    "fatigue_rest": 0.35,       # 待机/防御每拍恢复
    "fatigue_penalty": 0.004,   # 每点疲劳的战力折扣
    # 士气崩溃与重组
    "morale_enabled": 1,        # 1=启用士气状态机（溃退/重组）
    "morale_shock": 0.35,       # 单拍损失占最大兵力的比例超过此值→士气骤降
    "morale_break": 0.25,       # 士气低于此值→崩溃溃退
    "morale_recover": 0.06,     # 脱离接触后每拍士气恢复
    "reorg_strength": 0.45,     # 溃退重组后恢复的兵力比例
    # 炮火压制（软杀伤）
    "suppression_enabled": 1,   # 1=炮击对目标施加"被压制"状态（战力/机动下降）
    "suppression_penalty": 0.35,# 被压制期间战力折扣
    "suppression_ticks": 3,     # 压制持续拍数
    # 电子战/通信干扰
    "ew_jamming": 0.0,          # 通信干扰强度 0~0.2（叠加到消息丢失率/延迟）
    # 方向性侧翼
    "flank_dir_bonus": 0.3,     # 从目标背后/侧方（曼哈顿距离反方向）进攻的额外加成
    # === v0.9.7 九大战场因素 ===
    # 1.后勤补给线
    "supply_line_enabled": 1,   # 1=启用补给线系统（线路径/切断/弹药燃料分离）
    "ammo_drain": 2.0,          # 每拍弹药消耗（战斗时加倍）
    "fuel_drain": 1.5,          # 每拍燃料消耗（机动时加倍）
    "supply_line_cut_radius": 2,# 敌军距补给线多少格视为切断
    "ammo_combat_penalty": 0.5, # 弹药不足时战力折扣
    "fuel_move_penalty": 0.4,   # 燃料不足时机动折扣
    # 2.战争迷雾与侦察
    "fog_enabled": 1,           # 1=启用战争迷雾（视野/伪装/情报延迟）
    "camouflage_bonus": 0.5,    # 伪装单位被侦察到的概率折扣
    "intel_fade_ticks": 12,     # 情报过期拍数（过期后位置淡化）
    "recon_active_range": 3,    # 侦察单位主动侦搜额外范围
    # 3.指挥范围与控制
    "command_enabled": 1,       # 1=启用指挥范围系统
    "command_radius": 6,        # 指挥官指挥范围（曼哈顿格）
    "command_out_of_range_penalty": 0.25,  # 超出指挥范围战力折扣
    "command_break_morale": 15, # 指挥官阵亡时附近友军士气下降
    # 4.兵种协同与克制
    "synergy_enabled": 1,       # 1=启用兵种协同与克制
    "inf_arty_synergy": 0.2,    # 步炮协同加成（步兵+炮兵相邻）
    "armor_inf_synergy": 0.25,  # 装步协同加成
    "inf_anti_armor": 0.3,      # 步兵对装甲克制加成
    # 5.工程与工事
    "engineering_enabled": 1,   # 1=启用工程与工事系统
    "entrench_time": 3,         # 构筑工事所需拍数
    "entrench_level_bonus": 0.2,# 每级工事额外防御加成
    "engineer_speed": 2.0,      # 工兵构筑速度倍率
    # 6.天气影响增强
    "weather_effect_enabled": 1,# 1=启用天气对视野/移动/炮兵的影响
    "rain_move_penalty": 0.2,   # 雨天机动折扣
    "fog_sight_penalty": 0.4,   # 雾天视野折扣
    "storm_arty_penalty": 0.3,  # 风暴炮兵精度折扣
    # 7.部队经验与训练
    "experience_enabled": 1,    # 1=启用经验系统
    "exp_combat_gain": 2.0,     # 每次交火获得经验
    "exp_veteran_bonus": 0.15,  # 老兵战力加成
    "exp_elite_bonus": 0.3,     # 精锐战力加成
    "exp_morale_bonus": 0.2,    # 经验对士气的保护
    # 8.指挥官特质
    "leader_enabled": 1,        # 1=启用指挥官特质
    "leader_attack_bonus": 0.1, # 攻击型指挥官加成
    "leader_defense_bonus": 0.1,# 防御型指挥官加成
    "leader_casualty_penalty": 0.3, # 指挥官阵亡战力折扣
    # 9.接敌行军与展开
    "deployment_enabled": 1,    # 1=启用队形与展开系统
    "deployment_time": 1,       # 从行军队形展开到战斗队形所需拍数
    "march_combat_penalty": 0.4,# 行军队形中遇敌战力折扣
    "march_move_bonus": 0.3,    # 行军队形机动加成
}


@dataclass
class Unit:
    id: str
    side: str
    name: str
    kind: str
    x: int
    y: int
    strength: float = 100.0
    strength_max: float = 100.0   # 战役定制：阵营"数量规模"可放大/收缩单位总耐久
    supply: float = 100.0
    order: dict | None = None          # {"kind": move/attack, "target": [x,y]}
    path: list = field(default_factory=list)
    mp: float = 0.0
    entrenched: bool = False
    alive: bool = True
    moved_this_tick: bool = False       # 空军遮断只打击已机动的目标（行军纵队）
    # === 战役特征增强（v6）===
    fatigue: float = 0.0        # 疲劳度 0~100：越高战力越差
    morale: float = 100.0       # 士气 0~100：低于 break 值进入溃退
    morale_state: str = "steady"  # steady / shaken / breaking / reorg
    suppressed: int = 0         # 被炮火压制的剩余拍数（>0 表示被压制）
    reorg_ticks: int = 0        # 重组所需剩余拍数
    facing: tuple[int, int] | None = None  # 最近移动方向（用于方向性侧翼判定）
    # === v0.9.7 九大战场因素 ===
    # 1.后勤：弹药/燃料/食品
    ammo: float = 100.0
    fuel: float = 100.0
    rations: float = 100.0
    supply_line_cut: bool = False  # 补给线是否被切断
    # 2.侦察：伪装状态
    camouflaged: bool = False
    # 3.指挥：是否为指挥官单位 + 指挥范围
    is_commander: bool = False
    command_radius: int = 6
    in_command: bool = True
    # 4.协同：相邻友军兵种缓存（每拍更新）
    nearby_arty: bool = False
    nearby_inf: bool = False
    nearby_armor: bool = False
    # 5.工程：工事构筑进度（0~entrench_time，完成后entrenched=True）
    entrench_progress: float = 0.0
    entrench_level: int = 0  # 工事等级 0/1/2/3
    # 7.经验
    experience: float = 0.0  # 0-100
    exp_level: str = "green"  # green/regular/veteran/elite
    # 8.指挥官特质
    leader_style: str = "balanced"  # cautious/aggressive/balanced
    leader_skill: float = 0.5  # 0-1
    # 9.队形与展开
    formation: str = "march"  # march/combat
    deploying: int = 0  # 剩余展开拍数

    @property
    def speed(self) -> float: return UNIT_STATS[self.kind][0]
    @property
    def atk(self) -> float: return UNIT_STATS[self.kind][1]
    @property
    def dfn(self) -> float: return UNIT_STATS[self.kind][2]
    @property
    def rng(self) -> int: return UNIT_STATS[self.kind][3]
    @property
    def recon(self) -> int: return UNIT_STATS[self.kind][4]


def build_river_map(w: int = GRID_W, h: int = GRID_H) -> list[list[str]]:
    """默认渡河地图：南北向河流把战场一分为二，两座桥，河东有一座城镇。"""
    grid = [["."] * w for _ in range(h)]
    for y in range(h):
        grid[y][w // 2] = "~"                   # 河流
    for x, y in [(w // 2, h // 4), (w // 2, h * 11 // 16)]:
        grid[y][x] = "B"                        # 北桥 / 南桥
    for x, y in [(w - 6, h // 2 - 1), (w - 5, h // 2 - 1),
                 (w - 6, h // 2), (w - 5, h // 2)]:
        grid[y][x] = "C"                        # 河东城镇（红方目标）
    for x, y in [(7, 1), (8, 1), (8, 2), (16, 2), (17, 2), (16, 3),
                 (7, 13), (8, 14), (15, 13), (16, 14), (3, 5), (4, 5)]:
        if x < w and y < h:
            grid[y][x] = "f"                    # 森林
    for x, y in [(5, 6), (10, 8), (13, 9), (14, 6), (6, 9), (9, 12), (20, 3)]:
        if x < w and y < h:
            grid[y][x] = "h"                    # 丘陵
    return grid


def _d(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _arty_range(world: "World", unit: Unit) -> int:
    """炮兵有效射程：基础射程 × 射程倍率（设置面板可调）× 昼夜/天气修正。"""
    r = unit.rng * float(world.tuning.get("arty_range_scale", 1.0))
    if world.period == "night":
        r *= float(world.tuning.get("night_arty", 0.7))
    elif world.period == "dusk":
        r *= 0.9
    return max(1, int(r))

# 昼夜时段定义（按 tick 模 24 计算：0=昼 6=昏 12=夜 18=昏）
DAY_CYCLE = {0: "day", 6: "dusk", 12: "night", 18: "dusk"}
PERIOD_CN = {"day": "昼", "dusk": "昏", "night": "夜"}


class World:
    def __init__(self, w: int = GRID_W, h: int = GRID_H) -> None:
        self.w, self.h = w, h
        self.grid = build_river_map(w, h)
        self.units: dict[str, Unit] = {}
        self.depots: list[dict] = []    # [{"x","y","owner"}]——可被敌军夺占
        self.objectives: list[dict] = []  # [{"name","x","y","value","controller"}]
        self.weather_schedule: list[tuple[int, str]] = [(0, "clear")]
        self.weather = "clear"
        self.air_power: dict = {"red": 0.0, "blue": 0.0}
        # 交战关系（钢铁雄心式多方格局）：空集 = 所有不同阵营互为交战方；
        # 声明了关系对则只按声明开战——同盟阵营即便接壤也不交火
        self.war_pairs: set = set()
        self.tuning: dict = dict(DEFAULT_TUNING)
        # 每方独立属性（战役定制"从人到武器到双方装备"）：side → {hp,atk,def,speed,supply,spirit}
        # 缺省 1.0 = 无修正。hp 在 set_side_mods 时写入单位 strength_max。
        self.side_mod: dict = {}
        # 昼夜时段（day/dusk/night），由 tick 推演，随 run_tick 更新
        self.period: str = "day"
        self.tick: int = 0  # 世界时钟（与 sim 层同步，step 内自增）

    # ---- 构建 ----
    def add_unit(self, uid: str, side: str, name: str, kind: str, x: int, y: int) -> None:
        self.units[uid] = Unit(id=uid, side=side, name=name, kind=kind, x=x, y=y)

    def set_side_mods(self, mods: dict | None) -> None:
        """战役定制：设置每方(数量/火力/装甲/机动/后勤/士气)修正，并应用到全部单位当量血量。"""
        self.side_mod = {s: {"hp": 1.0, "atk": 1.0, "def": 1.0, "speed": 1.0,
                             "supply": 1.0, "spirit": 1.0, **m}
                         for s, m in (mods or {}).items()}
        for u in self.units.values():
            hp = max(0.3, float(self.side_mod.get(u.side, {}).get("hp", 1.0)))
            u.strength_max = 100.0 * hp
            u.strength = min(u.strength_max, max(u.strength, 5.0))
            u.strength = u.strength_max  # 数量规模在开局即定当量：耐久上限即当前量

    def set_depot(self, side: str, x: int, y: int) -> None:
        self.depots.append({"x": x, "y": y, "owner": side})

    def set_objectives(self, items: list[dict]) -> None:
        for o in items:
            self.objectives.append({**o, "controller": None})

    def set_weather(self, schedule: list[tuple[int, str]]) -> None:
        self.weather_schedule = sorted(schedule)
        self.weather = self.weather_schedule[0][1]

    def geo_seed(self, forest: float = 0.0, hill: float = 0.0,
                 swamp: float = 0.0) -> None:
        """战役定制：按密度在原有地图的可通行格上播种森林/丘陵/沼泽。

        只在 "." 开阔格上落种——绝不覆盖河流、桥梁、城镇、道路与想定原有的
        地形要素，避免破坏历史地图的关键走廊与目标点。种子固定，可复现。
        """
        walkable = [(x, y) for y in range(self.h) for x in range(self.w)
                    if self.grid[y][x] == "."]
        if not walkable:
            return
        rng = random.Random(0xCAFE + int(forest * 1000) + int(hill * 1000)
                            + int(swamp * 1000))
        for ch, den in (("f", forest), ("h", hill), ("m", swamp)):
            n = min(len(walkable), int(den * len(walkable)))
            for x, y in rng.sample(walkable, n):
                self.grid[y][x] = ch

    def set_air_power(self, air: dict) -> None:
        self.air_power = dict(air)

    def set_war_pairs(self, pairs: list) -> None:
        self.war_pairs = {frozenset(p) for p in pairs}

    def at_war(self, a: str, b: str) -> bool:
        if a == b:
            return False
        if not self.war_pairs:
            return True  # 未声明关系：所有不同阵营互为敌对
        return frozenset((a, b)) in self.war_pairs

    def weather_at(self, tick: int) -> str:
        cur = self.weather_schedule[0][1]
        for until, name in self.weather_schedule:
            if tick >= until:
                cur = name
        return cur

    def day_period(self, tick: int) -> str:
        """按 tick 计算昼夜时段（24拍一昼夜）。

        区间划分（模拟真实日照）：
          0-5   → day（昼）
          6-11  → dusk（昏：晨昏光线，侦察/火力轻度受限）
          12-17 → night（夜：侦察/火力/机动大幅受限）
          18-23 → dusk（昏）
        daynight_enabled=0 时恒为白天。
        """
        if not float(self.tuning.get("daynight_enabled", 0)):
            return "day"
        hour = tick % 24
        if 12 <= hour < 18:
            return "night"
        if hour >= 6:
            return "dusk"
        return "day"

    # ---- 查询 ----
    def terrain(self, x: int, y: int) -> str:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.grid[y][x]
        return "~"

    def passable(self, x: int, y: int) -> bool:
        return self.terrain(x, y) != "~"

    def unit_at(self, x: int, y: int) -> Unit | None:
        for u in self.units.values():
            if u.alive and u.x == x and u.y == y:
                return u
        return None

    def route(self, unit: Unit, target: tuple[int, int]) -> list:
        """BFS 最短路（4 向）。跨河只能走桥，天然形成渡场瓶颈；
        道路/铁路因消耗低会成为天然的机动走廊。"""
        start, goal = (unit.x, unit.y), tuple(target)
        if start == goal:
            return []
        prev: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        queue = [start]
        while queue:
            cur = queue.pop(0)
            if cur == goal:
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt in prev or not self.passable(*nxt):
                    continue
                prev[nxt] = cur
                queue.append(nxt)
        if goal not in prev:
            return []
        path, cur = [], goal
        while cur != start:
            path.append(cur)
            cur = prev[cur]  # type: ignore[assignment]
        path.reverse()
        return path

    # ---- 命令 ----
    def apply_action(self, unit: Unit, action: WorldAction) -> bool:
        if not unit.alive:
            return False
        if action.kind == "entrench":
            unit.entrenched = True
            unit.order, unit.path = None, []
            return True
        if action.kind == "hold":
            unit.order, unit.path = None, []
            return True
        if not action.target or len(action.target) != 2:
            return False
        tx, ty = int(action.target[0]), int(action.target[1])
        if not self.passable(tx, ty):
            return False
        unit.entrenched = False
        # 非炮兵的 attack 等价于向目标机动——接触后自动进入近战
        unit.order = {"kind": action.kind, "target": [tx, ty]}
        unit.path = self.route(unit, (tx, ty))
        return True

    # ---- 推进 ----
    def step(self, rng: random.Random) -> list[dict]:
        self.tick += 1
        events: list[dict] = []
        for u in self.units.values():
            u.moved_this_tick = False
        self._day_night()
        self._weather_effects()
        self._update_command_control(events)   # 3.指挥范围
        self._update_synergy()                  # 4.兵种协同缓存
        self._update_supply_lines(events)       # 1.补给线
        self._engineering(events)               # 5.工程构筑
        self._deployment(events)                # 9.队形展开
        self._movement(events)
        self._air_interdiction(rng, events)
        self._melee(rng, events)
        self._artillery(rng, events)
        self._supply()
        self._experience(events)                # 7.经验累积
        self._fatigue(events)
        self._morale(events)
        self._suppression_decay()
        self._depots(events)
        self._objectives(events)
        for u in self.units.values():
            if u.alive and u.strength <= 0:
                u.alive = False
                events.append({"type": "destroyed", "unit": u.id, "side": u.side,
                               "name": u.name, "x": u.x, "y": u.y})
                self._leader_casualty(u, events)  # 8.指挥官阵亡影响
        return events

    def _movement(self, events: list[dict]) -> None:
        for unit in sorted(self.units.values(), key=lambda u: u.id):
            if not unit.alive or unit.entrenched or not unit.order:
                continue
            # 士气崩溃/重组中的单位不能机动
            if unit.morale_state in ("breaking", "reorg"):
                unit.order, unit.path = None, []
                continue
            # 炮兵进入射击阵地后停车保持火力，不向目标贴脸
            if (unit.kind == "artillery" and unit.order.get("kind") == "attack"
                    and _d((unit.x, unit.y), tuple(unit.order["target"]))
                    <= _arty_range(self, unit)):
                unit.path = []
                continue
            # 机动速度：基础 × 昼夜修正 × 疲劳修正 × 被压制修正 × 燃料 × 队形 × 天气
            speed = unit.speed * float(self.tuning.get("move_scale", 1.0))
            if self.period == "night":
                speed *= float(self.tuning.get("night_move", 0.8))
            elif self.period == "dusk":
                speed *= 0.9
            if unit.fatigue > 0:
                speed *= 1.0 - float(self.tuning.get("fatigue_penalty", 0.004)) * unit.fatigue
            if unit.suppressed > 0:
                speed *= 0.6
            # 9.队形：行军队形机动加成
            if float(self.tuning.get("deployment_enabled", 1)) and unit.formation == "march":
                speed *= 1.0 + float(self.tuning.get("march_move_bonus", 0.3))
            # 1.燃料：燃料不足机动折扣
            if float(self.tuning.get("supply_line_enabled", 1)) and unit.fuel < 20:
                speed *= 1.0 - float(self.tuning.get("fuel_move_penalty", 0.4))
            # 6.天气：雨天机动折扣
            if float(self.tuning.get("weather_effect_enabled", 1)) and self.weather == "rain":
                speed *= 1.0 - float(self.tuning.get("rain_move_penalty", 0.2))
            elif self.weather == "storm":
                speed *= 0.6
            unit.mp += max(0.1, speed)
            moved_any = False
            while unit.order and unit.path:
                nx, ny = unit.path[0]
                occ = self.unit_at(nx, ny)
                # 友军占位则停车（渡场拥堵）；敌军占位则停下交火
                if occ is not None:
                    break
                if not self.passable(nx, ny):
                    break
                t = self.terrain(nx, ny)
                cost = ENTER_COST[t]
                if t == "r":  # 道路/铁路：road_bonus 越高走得越快
                    cost /= max(0.1, float(self.tuning.get("road_bonus", 1.0)))
                else:  # 越野：terrain_cost_scale 越高越难通过（沼泽/森林/渡场）
                    cost *= max(0.1, float(self.tuning.get("terrain_cost_scale", 1.0)))
                if unit.mp < cost:
                    break
                unit.mp -= cost
                # 记录朝向（方向性侧翼判定用）
                unit.facing = (nx - unit.x, ny - unit.y)
                unit.x, unit.y = nx, ny
                unit.path.pop(0)
                unit.moved_this_tick = True
                moved_any = True
            if unit.order and [unit.x, unit.y] == unit.order["target"]:
                unit.order, unit.path = None, []
                events.append({"type": "reached", "unit": unit.id,
                               "name": unit.name, "x": unit.x, "y": unit.y})

    def _day_night(self) -> None:
        """昼夜循环：随 tick 更新时段，并在转换时产出事件。"""
        new_period = self.day_period(self.tick)
        if new_period != self.period:
            self.period = new_period
            # 事件由 sim 层读取 weather 变化时统一 emit（见 sim.run_tick）

    def _fatigue(self, events: list[dict]) -> None:
        """疲劳系统：机动/战斗累积疲劳，待机/防御恢复。疲劳越高战力越差。"""
        if not float(self.tuning.get("fatigue_enabled", 1)):
            return
        f_move = float(self.tuning.get("fatigue_move", 0.8))
        f_rest = float(self.tuning.get("fatigue_rest", 0.35))
        for u in self.units.values():
            if not u.alive:
                continue
            if u.moved_this_tick:
                u.fatigue = min(100.0, u.fatigue + f_move)
            elif u.order is None or u.entrenched:
                # 待机/防御：恢复疲劳
                u.fatigue = max(0.0, u.fatigue - f_rest)

    def _suppression_decay(self) -> None:
        """压制状态随时间消退。"""
        for u in self.units.values():
            if u.suppressed > 0:
                u.suppressed -= 1

    # ===== v0.9.7 九大战场因素 =====

    def _weather_effects(self) -> None:
        """6.天气影响增强：雨/雪/雾影响视野和移动，风暴影响炮兵。"""
        if not float(self.tuning.get("weather_effect_enabled", 1)):
            return
        # 天气效果在_dmg/_movement/sightings中读取self.weather应用
        # 这里处理持续天气的累积效果（如泥泞）
        pass

    def _update_command_control(self, events: list[dict]) -> None:
        """3.指挥范围与控制：单位离指挥官过远则降效，指挥官阵亡影响士气。"""
        if not float(self.tuning.get("command_enabled", 1)):
            for u in self.units.values():
                u.in_command = True
            return
        cmd_radius = int(self.tuning.get("command_radius", 6))
        # 找每方的指挥官单位
        commanders = {}
        for u in self.units.values():
            if u.alive and u.is_commander:
                commanders[u.side] = commanders.get(u.side, []) + [u]
        for u in self.units.values():
            if not u.alive or u.is_commander:
                u.in_command = True
                continue
            side_cmdrs = commanders.get(u.side, [])
            in_range = any(_d((u.x, u.y), (c.x, c.y)) <= cmd_radius for c in side_cmdrs)
            if in_range != u.in_command:
                u.in_command = in_range
                if not in_range:
                    events.append({"type": "command", "unit": u.id, "name": u.name,
                                   "side": u.side, "state": "out_of_range"})
            else:
                u.in_command = in_range

    def _update_synergy(self) -> None:
        """4.兵种协同：缓存每单位相邻友军的兵种，供_dmg读取。"""
        if not float(self.tuning.get("synergy_enabled", 1)):
            return
        alive = [u for u in self.units.values() if u.alive]
        for u in alive:
            u.nearby_arty = False
            u.nearby_inf = False
            u.nearby_armor = False
            for e in alive:
                if e.side != u.side or e.id == u.id:
                    continue
                if _d((u.x, u.y), (e.x, e.y)) <= 1:
                    if e.kind == "artillery": u.nearby_arty = True
                    elif e.kind == "infantry": u.nearby_inf = True
                    elif e.kind == "armor": u.nearby_armor = True

    def _update_supply_lines(self, events: list[dict]) -> None:
        """1.后勤补给线：计算从补给站到单位的路径，检测是否被敌军切断。"""
        if not float(self.tuning.get("supply_line_enabled", 1)):
            for u in self.units.values():
                u.supply_line_cut = False
            return
        cut_radius = int(self.tuning.get("supply_line_cut_radius", 2))
        for u in self.units.values():
            if not u.alive:
                continue
            # 找最近的己方补给站
            own_depots = [d for d in self.depots if d["owner"] == u.side]
            if not own_depots:
                u.supply_line_cut = True
                continue
            nearest = min(own_depots, key=lambda d: _d((u.x, u.y), (d["x"], d["y"])))
            # 简化：检查补给站到单位的直线上是否有敌军
            # （完整BFS路径检测代价高，用曼哈顿路径近似）
            cut = False
            enemies = [e for e in self.units.values()
                       if e.alive and self.at_war(u.side, e.side)]
            # 检查补给站周围是否被敌军围困
            for e in enemies:
                if _d((nearest["x"], nearest["y"]), (e.x, e.y)) <= cut_radius:
                    cut = True
                    break
            if cut != u.supply_line_cut:
                u.supply_line_cut = cut
                if cut:
                    events.append({"type": "supply_line", "unit": u.id, "name": u.name,
                                   "side": u.side, "state": "cut"})
                else:
                    events.append({"type": "supply_line", "unit": u.id, "name": u.name,
                                   "side": u.side, "state": "restored"})

    def _engineering(self, events: list[dict]) -> None:
        """5.工程与工事：单位待机时构筑工事，工兵更快，工事分等级。"""
        if not float(self.tuning.get("engineering_enabled", 1)):
            return
        ent_time = float(self.tuning.get("entrench_time", 3))
        eng_speed = float(self.tuning.get("engineer_speed", 1))
        for u in self.units.values():
            if not u.alive:
                continue
            # 只有待机/防御状态的单位才能构筑工事
            if u.order is not None or u.moved_this_tick:
                continue
            if u.entrenched and u.entrench_level >= 3:
                continue
            speed = eng_speed if u.kind == "engineer" else 1.0
            u.entrench_progress += speed
            if u.entrench_progress >= ent_time and not u.entrenched:
                u.entrenched = True
                u.entrench_level = 1
                u.entrench_progress = 0
                events.append({"type": "entrench", "unit": u.id, "name": u.name,
                               "side": u.side, "level": 1})
            elif u.entrenched and u.entrench_progress >= ent_time * 1.5:
                if u.entrench_level < 3:
                    u.entrench_level += 1
                    u.entrench_progress = 0
                    events.append({"type": "entrench", "unit": u.id, "name": u.name,
                                   "side": u.side, "level": u.entrench_level})

    def _deployment(self, events: list[dict]) -> None:
        """9.接敌行军与展开：行军队形机动快但遇敌弱，展开需时间。"""
        if not float(self.tuning.get("deployment_enabled", 1)):
            return
        dep_time = int(self.tuning.get("deployment_time", 1))
        for u in self.units.values():
            if not u.alive:
                continue
            # 有移动命令 → 行军队形
            if u.order and u.order.get("kind") == "move":
                if u.formation != "march":
                    u.formation = "march"
                    u.deploying = 0
            # 无命令或攻击命令 → 尝试展开为战斗队形
            elif u.formation == "march":
                u.deploying += 1
                if u.deploying >= dep_time:
                    u.formation = "combat"
                    u.deploying = 0
                    events.append({"type": "deployment", "unit": u.id, "name": u.name,
                                   "side": u.side, "state": "combat"})

    def _experience(self, events: list[dict]) -> None:
        """7.部队经验与训练：交火累积经验，升级为老兵/精锐，提升战力士气。"""
        if not float(self.tuning.get("experience_enabled", 1)):
            return
        gain = float(self.tuning.get("exp_combat_gain", 2.0))
        for u in self.units.values():
            if not u.alive:
                continue
            # 交火的单位获得经验
            if u.moved_this_tick or u.suppressed > 0:
                u.experience = min(100.0, u.experience + gain * 0.3)
            # 根据经验设置等级
            old_level = u.exp_level
            if u.experience >= 75:
                u.exp_level = "elite"
            elif u.experience >= 50:
                u.exp_level = "veteran"
            elif u.experience >= 25:
                u.exp_level = "regular"
            else:
                u.exp_level = "green"
            if u.exp_level != old_level:
                events.append({"type": "experience", "unit": u.id, "name": u.name,
                               "side": u.side, "level": u.exp_level})

    def _leader_casualty(self, unit: Unit, events: list[dict]) -> None:
        """8.指挥官特质：指挥官阵亡时附近友军士气下降、战力折扣。"""
        if not float(self.tuning.get("leader_enabled", 1)):
            return
        if not unit.is_commander:
            return
        morale_drop = float(self.tuning.get("command_break_morale", 15))
        for u in self.units.values():
            if u.alive and u.side == unit.side and u.id != unit.id:
                if _d((u.x, u.y), (unit.x, unit.y)) <= int(self.tuning.get("command_radius", 6)):
                    u.morale = max(0.0, u.morale - morale_drop)
                    events.append({"type": "leader_lost", "unit": u.id, "name": u.name,
                                   "side": u.side, "commander": unit.name})

    def _morale(self, events: list[dict]) -> None:
        """士气状态机：损失→士气下降→崩溃溃退→脱离接触后重组。

        steady（正常）→ shaken（受创动摇）→ breaking（崩溃溃退）→ reorg（重组恢复）
        士气崩溃的单位停止行动、失去战力，重组后以部分兵力回归。
        """
        if not float(self.tuning.get("morale_enabled", 1)):
            return
        shock = float(self.tuning.get("morale_shock", 0.35))
        break_thr = float(self.tuning.get("morale_break", 0.25))
        recover = float(self.tuning.get("morale_recover", 0.06))
        reorg_str = float(self.tuning.get("reorg_strength", 0.45))
        for u in self.units.values():
            if not u.alive:
                continue
            # 是否处于交战/受创中
            dmg_taken = u.strength_max - u.strength
            if u.morale_state == "steady":
                if dmg_taken > u.strength_max * 0.6 or u.morale < break_thr * 100:
                    u.morale_state = "shaken"
                    events.append({"type": "morale", "unit": u.id, "name": u.name,
                                   "state": "shaken", "side": u.side})
            elif u.morale_state == "shaken":
                # 连续受创或士气过低 → 崩溃
                if u.morale < break_thr * 100 or dmg_taken > u.strength_max * 0.85:
                    u.morale_state = "breaking"
                    u.order, u.path = None, []  # 停止一切行动
                    u.entrenched = False
                    events.append({"type": "morale", "unit": u.id, "name": u.name,
                                   "state": "breaking", "side": u.side})
                else:
                    # 脱离接触（无敌人相邻）则逐步恢复
                    u.morale = min(100.0, u.morale + recover)
            elif u.morale_state == "breaking":
                # 正在溃退：停止行动，数拍后重组
                u.order, u.path = None, []
                u.reorg_ticks += 1
                if u.reorg_ticks >= 3:
                    u.morale_state = "reorg"
                    u.reorg_ticks = 0
                    # 重组：恢复部分兵力
                    u.strength = max(10.0, u.strength_max * reorg_str)
                    u.morale = max(50.0, break_thr * 100 + 25)
                    u.fatigue = 0.0
                    events.append({"type": "morale", "unit": u.id, "name": u.name,
                                   "state": "reorg", "side": u.side})
            elif u.morale_state == "reorg":
                # 重组中：恢复士气，回到正常
                u.morale = min(100.0, u.morale + recover * 2)
                if u.morale >= 60:
                    u.morale_state = "steady"
                    events.append({"type": "morale", "unit": u.id, "name": u.name,
                                   "state": "steady", "side": u.side})

    def _air_interdiction(self, rng: random.Random, events: list[dict]) -> None:
        """空军遮断：打击已机动的敌军行军纵队。天气恶劣时基本瘫痪
        （1944-06-06 的风暴让德军侦察与空军同时失明）。"""
        air_scale = float(self.tuning.get("air_scale", 1.0))
        if air_scale <= 0:
            return
        w_air = WEATHER_AIR.get(self.weather, 1.0)
        if w_air <= 0:
            return
        prob = float(self.tuning.get("air_prob", 0.12)) * air_scale * w_air
        for u in list(self.units.values()):
            if not u.alive or not u.moved_this_tick:
                continue
            # 多方格局：取所有交战对方中最大的空中力量
            enemy_air = max((a for f, a in self.air_power.items()
                             if f != u.side and self.at_war(u.side, f)), default=0.0)
            if enemy_air <= 0 or rng.random() >= prob * enemy_air:
                continue
            dmg = float(self.tuning.get("air_dmg", 3.0)) * rng.uniform(0.7, 1.3)
            u.strength -= dmg
            events.append({"type": "air", "unit": u.id, "name": u.name,
                           "side": u.side, "dmg": round(dmg, 1),
                           "x": u.x, "y": u.y})

    def _dmg(self, rng: random.Random, attacker: Unit, defender: Unit,
             attackers: int = 1) -> float:
        if not attacker.alive or attacker.strength <= 0:
            return 0.0
        am = self.side_mod.get(attacker.side, {})
        dm = self.side_mod.get(defender.side, {})
        # 补给影响战力：s=0 时补给无影响（恒为满战力）；s=1 时补给归零战力减半
        scs = float(self.tuning.get("supply_combat_scale", 0.5))
        st = attacker.strength / 100
        # 士气与战损：兵力过低战力衰减（morale_scale 放大幅值，low_strength_penalty 定折扣）
        # 阵营"士气"改写成抗崩系数：士气越高越不因残兵而崩（进入 discount/spirit）
        spirit = max(0.2, float(am.get("spirit", 1.0)))
        if st < 0.4:
            st *= (1 - float(self.tuning.get("low_strength_penalty", 0.3))
                   * float(self.tuning.get("morale_scale", 1.0)) / spirit)
        base = (8.0 * attacker.atk * st * float(am.get("atk", 1.0))
                * (1 - scs + scs * attacker.supply / 100))
        # 疲劳：越疲劳打得越差
        if attacker.fatigue > 0:
            base *= 1.0 - float(self.tuning.get("fatigue_penalty", 0.004)) * attacker.fatigue
        # 被炮火压制：软杀伤——战力与行动力双重下降
        if attacker.suppressed > 0:
            base *= 1.0 - float(self.tuning.get("suppression_penalty", 0.35))
        # 士气状态修正：动摇/崩溃的单位战力锐减
        if attacker.morale_state == "shaken":
            base *= 0.7
        elif attacker.morale_state in ("breaking", "reorg"):
            base *= 0.2
        # 3.指挥范围：超出指挥范围战力折扣
        if float(self.tuning.get("command_enabled", 1)) and not attacker.in_command:
            base *= 1.0 - float(self.tuning.get("command_out_of_range_penalty", 0.25))
        # 4.兵种协同：步炮/装步协同加成
        if float(self.tuning.get("synergy_enabled", 1)):
            if attacker.kind == "infantry" and attacker.nearby_arty:
                base *= 1.0 + float(self.tuning.get("inf_arty_synergy", 0.2))
            if attacker.kind == "armor" and attacker.nearby_inf:
                base *= 1.0 + float(self.tuning.get("armor_inf_synergy", 0.25))
            # 兵种克制：步兵对装甲加成
            if attacker.kind == "infantry" and defender.kind == "armor":
                base *= 1.0 + float(self.tuning.get("inf_anti_armor", 0.3))
        # 7.经验：老兵/精锐战力加成
        if float(self.tuning.get("experience_enabled", 1)):
            if attacker.exp_level == "veteran":
                base *= 1.0 + float(self.tuning.get("exp_veteran_bonus", 0.15))
            elif attacker.exp_level == "elite":
                base *= 1.0 + float(self.tuning.get("exp_elite_bonus", 0.3))
        # 8.指挥官特质：攻击型指挥官加成
        if float(self.tuning.get("leader_enabled", 1)) and attacker.is_commander:
            if attacker.leader_style == "aggressive":
                base *= 1.0 + float(self.tuning.get("leader_attack_bonus", 0.1))
        # 9.队形：行军队形中遇敌战力折扣
        if float(self.tuning.get("deployment_enabled", 1)) and attacker.formation == "march":
            base *= 1.0 - float(self.tuning.get("march_combat_penalty", 0.4))
        # 1.弹药：弹药不足战力折扣
        if float(self.tuning.get("supply_line_enabled", 1)) and attacker.ammo < 20:
            base *= 1.0 - float(self.tuning.get("ammo_combat_penalty", 0.5))
        # 昼夜修正：夜间接战受限
        if self.period == "night":
            base *= float(self.tuning.get("night_melee", 0.8))
        elif self.period == "dusk":
            base *= 0.9
        # 侧翼夹击：多个单位围攻同一目标时，每多一个攻击者叠加加成
        if attackers > 1:
            base *= 1 + float(self.tuning.get("flank_bonus", 0.5)) * (attackers - 1)
        # 追击：对已残损目标按战损比例追加伤害（overrun_scale=0 即关闭）
        if defender.strength < 100:
            base *= 1 + float(self.tuning.get("overrun_scale", 0.25)) * (1 - defender.strength / 100)
        terr_def = TERRAIN_DEF.get(self.terrain(defender.x, defender.y), 0.0)
        guard = 1 + terr_def * float(self.tuning.get("terrain_def_scale", 1.0))
        if defender.entrenched:
            guard += float(self.tuning.get("entrench_bonus", 0.4))
            # 5.工事等级：每级额外防御
            if float(self.tuning.get("engineering_enabled", 1)):
                guard += defender.entrench_level * float(self.tuning.get("entrench_level_bonus", 0.2))
        # 8.指挥官特质：防御型指挥官加成
        if float(self.tuning.get("leader_enabled", 1)) and defender.is_commander:
            if defender.leader_style == "cautious":
                guard *= 1.0 + float(self.tuning.get("leader_defense_bonus", 0.1))
        # 7.经验：防御方经验加成
        if float(self.tuning.get("experience_enabled", 1)) and defender.exp_level in ("veteran", "elite"):
            guard *= 1.0 + float(self.tuning.get("exp_veteran_bonus", 0.15)) * 0.5
        # 方向性侧翼：从目标"背后/侧向"进攻，防御方的阵地优势失效
        if defender.facing and (defender.x - attacker.x, defender.y - attacker.y) != (0, 0):
            # 攻击方到防御方方向 与 防御方朝向 的相反关系 → 背后攻击
            atk_dir = (defender.x - attacker.x, defender.y - attacker.y)
            # 若攻击方向与防御方朝向相反（同向相减），点积为负 → 背后
            dot = atk_dir[0] * defender.facing[0] + atk_dir[1] * defender.facing[1]
            if dot < 0:
                guard *= (1 - float(self.tuning.get("flank_dir_bonus", 0.3)))
        # 防御方被压制：防御也下降
        if defender.suppressed > 0:
            guard *= (1 - float(self.tuning.get("suppression_penalty", 0.35)) * 0.6)
        guard *= defender.dfn
        guard *= max(0.2, float(dm.get("def", 1.0)))   # 阵营"装甲防护"
        return base * float(self.tuning.get("combat_scale", 1.0)) / guard * rng.uniform(0.75, 1.25)

    def _melee(self, rng: random.Random, events: list[dict]) -> None:
        alive = [u for u in self.units.values() if u.alive]
        contact: dict[str, dict] = {}
        # 先统计每单位本轮的围攻者数量（侧翼夹击按围攻人数加成）
        attackers: dict[str, int] = {}
        for u in alive:
            for e in alive:
                if (e.side == u.side or not self.at_war(u.side, e.side)
                        or _d((u.x, u.y), (e.x, e.y)) > 1):
                    continue
                attackers[u.id] = attackers.get(u.id, 0) + 1
                attackers[e.id] = attackers.get(e.id, 0) + 1
        done: set[tuple[str, str]] = set()
        for u in alive:
            for e in alive:
                if (e.side == u.side or not self.at_war(u.side, e.side)
                        or _d((u.x, u.y), (e.x, e.y)) > 1):
                    continue
                key = tuple(sorted((u.id, e.id)))  # type: ignore[arg-type]
                if key in done:
                    continue
                done.add(key)  # type: ignore[arg-type]
                du = self._dmg(rng, e, u, attackers.get(e.id, 1))
                de = self._dmg(rng, u, e, attackers.get(u.id, 1))
                u.strength -= du
                e.strength -= de
                # 交火累积疲劳
                u.fatigue = min(100.0, u.fatigue + float(self.tuning.get("fatigue_combat", 1.2)))
                e.fatigue = min(100.0, e.fatigue + float(self.tuning.get("fatigue_combat", 1.2)))
                # 受创冲击士气：单拍大损失→士气骤降
                shock = float(self.tuning.get("morale_shock", 0.35))
                for victim, dmg in ((u, du), (e, de)):
                    if dmg > 0 and victim.strength_max > 0:
                        shock_ratio = dmg / victim.strength_max
                        if shock_ratio > shock:
                            victim.morale = max(0.0, victim.morale - 20)
                        elif shock_ratio > shock * 0.5:
                            victim.morale = max(0.0, victim.morale - 8)
                        victim.morale = max(0.0, victim.morale - 2)
                for victim, dmg, foe in ((u, du, e), (e, de, u)):
                    c = contact.setdefault(victim.id, {"taken": 0.0, "vs": []})
                    c["taken"] += dmg
                    c["vs"].append(foe.name)
        for uid, c in contact.items():
            events.append({"type": "combat", "unit": uid, "name": self.units[uid].name,
                           "taken": round(c["taken"], 1), "vs": c["vs"]})

    def _artillery(self, rng: random.Random, events: list[dict]) -> None:
        for arty in [u for u in self.units.values()
                     if u.alive and u.kind == "artillery"
                     and u.order and u.order["kind"] == "attack"]:
            tx, ty = arty.order["target"]
            if _d((arty.x, arty.y), (tx, ty)) > _arty_range(self, arty):
                continue  # 射程外：保持待令，由师部前移炮兵
            for t in [u for u in self.units.values()
                      if u.alive and self.at_war(arty.side, u.side)
                      and _d((u.x, u.y), (tx, ty)) <= 1]:
                ast = arty.strength / 100
                if ast < 0.4:  # 炮兵也有士气与战损
                    ast *= (1 - float(self.tuning.get("low_strength_penalty", 0.3))
                            * float(self.tuning.get("morale_scale", 1.0)))
                base = 6.0 * arty.atk * ast * (0.5 + 0.5 * arty.supply / 100)
                # 1.弹药：炮兵弹药不足伤害下降
                if float(self.tuning.get("supply_line_enabled", 1)) and arty.ammo < 20:
                    base *= 1.0 - float(self.tuning.get("ammo_combat_penalty", 0.5))
                # 6.天气：风暴炮兵精度下降
                if float(self.tuning.get("weather_effect_enabled", 1)) and self.weather == "storm":
                    base *= 1.0 - float(self.tuning.get("storm_arty_penalty", 0.3))
                # 7.经验：炮兵经验加成
                if float(self.tuning.get("experience_enabled", 1)) and arty.exp_level == "veteran":
                    base *= 1.0 + float(self.tuning.get("exp_veteran_bonus", 0.15))
                elif arty.exp_level == "elite":
                    base *= 1.0 + float(self.tuning.get("exp_elite_bonus", 0.3))
                # 炮兵射击消耗弹药
                if float(self.tuning.get("supply_line_enabled", 1)):
                    arty.ammo = max(0.0, arty.ammo - 3.0)
                terr_def = TERRAIN_DEF.get(self.terrain(t.x, t.y), 0.0)
                guard = (1 + terr_def * float(self.tuning.get("terrain_def_scale", 1.0))
                         + (float(self.tuning.get("entrench_bonus", 0.4)) if t.entrenched else 0.0))
                guard *= t.dfn
                dmg = (base * 0.9 * float(self.tuning.get("arty_scale", 1.0))
                       / guard * rng.uniform(0.75, 1.25))
                t.strength -= dmg
                # 炮火压制（软杀伤）：被炮击后目标短期战力/机动下降
                if float(self.tuning.get("suppression_enabled", 1)):
                    t.suppressed = int(self.tuning.get("suppression_ticks", 3))
                # 炮击冲击士气
                if t.strength_max > 0 and dmg > t.strength_max * float(
                        self.tuning.get("morale_shock", 0.35)) * 0.6:
                    t.morale = max(0.0, t.morale - 6)
                events.append({"type": "fire", "unit": arty.id, "name": arty.name,
                               "target": t.id, "target_name": t.name,
                               "dmg": round(dmg, 1), "x": tx, "y": ty})

    def _supply(self) -> None:
        """补给：只有己方控制的补给站提供前送——被夺占的补给站反哺敌军。
        v0.9.7：分离弹药/燃料/食品，补给线被切断时停止前送。"""
        radius = float(self.tuning.get("depot_radius", 7))
        sl_enabled = float(self.tuning.get("supply_line_enabled", 1))
        for u in self.units.values():
            if not u.alive:
                continue
            near = min((_d((u.x, u.y), (d["x"], d["y"])) for d in self.depots
                        if d["owner"] == u.side), default=999)
            in_range = near <= radius
            # 补给线被切断时，即使在补给站范围内也无法获得补给
            if sl_enabled and u.supply_line_cut:
                in_range = False
            if in_range:
                u.supply = min(100.0, u.supply + float(self.tuning.get("supply_regen", 5.0)))
                if sl_enabled:
                    u.ammo = min(100.0, u.ammo + float(self.tuning.get("supply_regen", 5.0)) * 1.5)
                    u.fuel = min(100.0, u.fuel + float(self.tuning.get("supply_regen", 5.0)))
                    u.rations = min(100.0, u.rations + float(self.tuning.get("supply_regen", 5.0)) * 0.5)
            else:
                u.supply = max(0.0, u.supply - float(self.tuning.get("supply_drain", 3.0)))
                if sl_enabled:
                    # 弹药消耗：战斗时更多（在_melee中额外消耗）
                    u.ammo = max(0.0, u.ammo - float(self.tuning.get("ammo_drain", 2.0)))
                    # 燃料消耗：机动时更多（在_movement中额外消耗）
                    u.fuel = max(0.0, u.fuel - float(self.tuning.get("fuel_drain", 1.5)) * (0.5 if u.kind != "armor" else 1.0))
                    u.rations = max(0.0, u.rations - 0.5)
                if u.supply <= 0:
                    u.strength -= 1  # 断补给缓慢失血，不打断节奏
                if sl_enabled and u.rations <= 0:
                    u.morale = max(0.0, u.morale - 1)  # 断粮士气下降

    def _depots(self, events: list[dict]) -> None:
        """补给站争夺：交战对方进抵站点 1 格即夺占——后勤线是战役的动脉。"""
        for d in self.depots:
            for u in self.units.values():
                if (u.alive and self.at_war(u.side, d["owner"])
                        and _d((u.x, u.y), (d["x"], d["y"])) <= 1):
                    old = d["owner"]
                    d["owner"] = u.side
                    events.append({"type": "depot", "side": u.side, "from": old,
                                   "x": d["x"], "y": d["y"],
                                   "name": f"补给站({d['x']},{d['y']})"})
                    break

    def _objectives(self, events: list[dict]) -> None:
        """战役目标控制权：单位进抵目标 2 格即确立控制，撤离后保持现状。"""
        for o in self.objectives:
            holder = None
            for u in self.units.values():
                if u.alive and _d((u.x, u.y), (o["x"], o["y"])) <= 2:
                    holder = u.side
                    break
            if holder and holder != o["controller"]:
                o["controller"] = holder
                events.append({"type": "objective", "side": holder,
                               "name": o["name"], "x": o["x"], "y": o["y"],
                               "value": o.get("value", 1)})

    # ---- 侦察（阵营间唯一间接通道）----
    def sightings(self, side: str, rng: random.Random, tick: int) -> list[dict]:
        """返回 side 观察到的敌情（带 ±N 坐标误差）。只在己方单位侦察半径内可见。
        v0.9.7：伪装单位更难被发现，雾天视野下降，情报带时间戳供过期判断。"""
        err = int(self.tuning.get("intel_error", 1))
        rs = float(self.tuning.get("recon_scale", 1.0))
        fog_enabled = float(self.tuning.get("fog_enabled", 1))
        # 夜间侦察半径衰减
        if self.period == "night":
            rs *= float(self.tuning.get("night_recon", 0.6))
        elif self.period == "dusk":
            rs *= 0.85
        # 6.天气：雾天视野下降
        if float(self.tuning.get("weather_effect_enabled", 1)) and self.weather == "fog":
            rs *= 1.0 - float(self.tuning.get("fog_sight_penalty", 0.4))
        elif self.weather == "rain":
            rs *= 0.8
        out = []
        own = [u for u in self.units.values() if u.alive and u.side == side]
        for e in [u for u in self.units.values()
                  if u.alive and self.at_war(side, u.side)]:
            for o in own:
                radius = o.recon * rs + (2 if self.terrain(o.x, o.y) == "h" else 0)
                # 2.伪装：伪装单位需要更近才能被发现
                if fog_enabled and e.camouflaged:
                    radius *= 1.0 - float(self.tuning.get("camouflage_bonus", 0.5))
                if _d((o.x, o.y), (e.x, e.y)) <= radius:
                    # 伪装单位有概率不被发现
                    if fog_enabled and e.camouflaged and rng.random() < 0.4:
                        continue
                    jx = min(self.w - 1, max(0, e.x + rng.randint(-err, err)))
                    jy = min(self.h - 1, max(0, e.y + rng.randint(-err, err)))
                    out.append({"unit_id": e.id, "kind": e.kind, "name": e.name,
                                "x": jx, "y": jy, "tick": tick,
                                "camouflaged": e.camouflaged})
                    break
        return out

    # ---- 视图 ----
    def unit_view(self, u: Unit) -> dict:
        return {"id": u.id, "side": u.side, "name": u.name, "kind": u.kind,
                "x": u.x, "y": u.y, "strength": round(u.strength),
                "strength_max": round(u.strength_max),
                "supply": round(u.supply), "entrenched": u.entrenched,
                "alive": u.alive, "order": (u.order or {}).get("kind"),
                # 战役特征增强（v6）
                "fatigue": round(u.fatigue, 1),
                "morale": round(u.morale, 1),
                "morale_state": u.morale_state,
                "suppressed": u.suppressed,
                "facing": list(u.facing) if u.facing else None,
                "period": self.period,
                # v0.9.7 九大战场因素
                "ammo": round(u.ammo),
                "fuel": round(u.fuel),
                "rations": round(u.rations),
                "supply_line_cut": u.supply_line_cut,
                "camouflaged": u.camouflaged,
                "is_commander": u.is_commander,
                "in_command": u.in_command,
                "entrench_level": u.entrench_level,
                "experience": round(u.experience),
                "exp_level": u.exp_level,
                "leader_style": u.leader_style,
                "formation": u.formation,
                "weather": self.weather}

    def jamming(self) -> float:
        """当前电子战/通信干扰强度（0~0.6）。供 bus 层叠加到消息丢失率。"""
        return max(0.0, min(0.2, float(self.tuning.get("ew_jamming", 0.0))))

    def side_units_view(self, side: str) -> list[dict]:
        return [self.unit_view(u) for u in self.units.values()
                if u.side == side and u.alive]

    def all_units_view(self) -> list[dict]:
        return [self.unit_view(u) for u in self.units.values() if u.alive]
