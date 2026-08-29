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
    # 后勤
    "supply_regen": 5.0,        # 补给站半径内每拍回复
    "supply_drain": 3.0,        # 补给站半径外每拍消耗
    "depot_radius": 7,          # 补给站作用半径（曼哈顿格）
    # 侦察
    "recon_scale": 1.0,         # 侦察半径倍率
    "intel_error": 1,           # 敌情坐标误差（±格）
    # 机动
    "move_scale": 1.0,          # 单位移速倍率
    # 智能体节奏（rule 策略经共享字典读取；LLM 模式下影响唤醒周期）
    "report_interval": 8,       # 例行报告间隔（拍）
    "withdraw_threshold": 40,   # 兵力低于此值触发告警并转入据守
    "contact_fwd_interval": 4,  # 接触战况上报的最小间隔（拍）
    # 空军遮断
    "air_scale": 1.0,           # 遮断强度倍率（0 = 关闭空军）
    "air_dmg": 3.0,             # 单次遮断打击基准伤害
    "air_prob": 0.12,           # 对每个已机动敌单位的遮断命中概率基数
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
    supply: float = 100.0
    order: dict | None = None          # {"kind": move/attack, "target": [x,y]}
    path: list = field(default_factory=list)
    mp: float = 0.0
    entrenched: bool = False
    alive: bool = True
    moved_this_tick: bool = False       # 空军遮断只打击已机动的目标（行军纵队）

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

    # ---- 构建 ----
    def add_unit(self, uid: str, side: str, name: str, kind: str, x: int, y: int) -> None:
        self.units[uid] = Unit(id=uid, side=side, name=name, kind=kind, x=x, y=y)

    def set_depot(self, side: str, x: int, y: int) -> None:
        self.depots.append({"x": x, "y": y, "owner": side})

    def set_objectives(self, items: list[dict]) -> None:
        for o in items:
            self.objectives.append({**o, "controller": None})

    def set_weather(self, schedule: list[tuple[int, str]]) -> None:
        self.weather_schedule = sorted(schedule)
        self.weather = self.weather_schedule[0][1]

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
        events: list[dict] = []
        for u in self.units.values():
            u.moved_this_tick = False
        self._movement(events)
        self._air_interdiction(rng, events)
        self._melee(rng, events)
        self._artillery(rng, events)
        self._supply()
        self._depots(events)
        self._objectives(events)
        for u in self.units.values():
            if u.alive and u.strength <= 0:
                u.alive = False
                events.append({"type": "destroyed", "unit": u.id, "side": u.side,
                               "name": u.name, "x": u.x, "y": u.y})
        return events

    def _movement(self, events: list[dict]) -> None:
        for unit in sorted(self.units.values(), key=lambda u: u.id):
            if not unit.alive or unit.entrenched or not unit.order:
                continue
            # 炮兵进入射击阵地后停车保持火力，不向目标贴脸
            if (unit.kind == "artillery" and unit.order.get("kind") == "attack"
                    and _d((unit.x, unit.y), tuple(unit.order["target"])) <= unit.rng):
                unit.path = []
                continue
            unit.mp += unit.speed * self.tuning["move_scale"]
            while unit.order and unit.path:
                nx, ny = unit.path[0]
                occ = self.unit_at(nx, ny)
                # 友军占位则停车（渡场拥堵）；敌军占位则停下交火
                if occ is not None:
                    break
                if not self.passable(nx, ny):
                    break
                cost = ENTER_COST[self.terrain(nx, ny)]
                if unit.mp < cost:
                    break
                unit.mp -= cost
                unit.x, unit.y = nx, ny
                unit.path.pop(0)
                unit.moved_this_tick = True
            if unit.order and [unit.x, unit.y] == unit.order["target"]:
                unit.order, unit.path = None, []
                events.append({"type": "reached", "unit": unit.id,
                               "name": unit.name, "x": unit.x, "y": unit.y})

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

    def _dmg(self, rng: random.Random, attacker: Unit, defender: Unit) -> float:
        if not attacker.alive or attacker.strength <= 0:
            return 0.0
        base = 8.0 * attacker.atk * (attacker.strength / 100) * (0.5 + 0.5 * attacker.supply / 100)
        terr_def = TERRAIN_DEF.get(self.terrain(defender.x, defender.y), 0.0)
        guard = 1 + terr_def * float(self.tuning.get("terrain_def_scale", 1.0))
        if defender.entrenched:
            guard += float(self.tuning.get("entrench_bonus", 0.4))
        guard *= defender.dfn
        return base * float(self.tuning.get("combat_scale", 1.0)) / guard * rng.uniform(0.75, 1.25)

    def _melee(self, rng: random.Random, events: list[dict]) -> None:
        alive = [u for u in self.units.values() if u.alive]
        contact: dict[str, dict] = {}
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
                du, de = self._dmg(rng, e, u), self._dmg(rng, u, e)
                u.strength -= du
                e.strength -= de
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
            if _d((arty.x, arty.y), (tx, ty)) > arty.rng:
                continue  # 射程外：保持待令，由师部前移炮兵
            for t in [u for u in self.units.values()
                      if u.alive and self.at_war(arty.side, u.side)
                      and _d((u.x, u.y), (tx, ty)) <= 1]:
                base = 6.0 * arty.atk * (arty.strength / 100) * (0.5 + 0.5 * arty.supply / 100)
                terr_def = TERRAIN_DEF.get(self.terrain(t.x, t.y), 0.0)
                guard = (1 + terr_def * float(self.tuning.get("terrain_def_scale", 1.0))
                         + (float(self.tuning.get("entrench_bonus", 0.4)) if t.entrenched else 0.0))
                guard *= t.dfn
                dmg = (base * 0.9 * float(self.tuning.get("arty_scale", 1.0))
                       / guard * rng.uniform(0.75, 1.25))
                t.strength -= dmg
                events.append({"type": "fire", "unit": arty.id, "name": arty.name,
                               "target": t.id, "target_name": t.name,
                               "dmg": round(dmg, 1), "x": tx, "y": ty})

    def _supply(self) -> None:
        """补给：只有己方控制的补给站提供前送——被夺占的补给站反哺敌军。"""
        radius = float(self.tuning.get("depot_radius", 7))
        for u in self.units.values():
            if not u.alive:
                continue
            near = min((_d((u.x, u.y), (d["x"], d["y"])) for d in self.depots
                        if d["owner"] == u.side), default=999)
            if near <= radius:
                u.supply = min(100.0, u.supply + float(self.tuning.get("supply_regen", 5.0)))
            else:
                u.supply = max(0.0, u.supply - float(self.tuning.get("supply_drain", 3.0)))
                if u.supply <= 0:
                    u.strength -= 1  # 断补给缓慢失血，不打断节奏

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
        """返回 side 观察到的敌情（带 ±N 坐标误差）。只在己方单位侦察半径内可见。"""
        err = int(self.tuning.get("intel_error", 1))
        rs = float(self.tuning.get("recon_scale", 1.0))
        out = []
        own = [u for u in self.units.values() if u.alive and u.side == side]
        for e in [u for u in self.units.values()
                  if u.alive and self.at_war(side, u.side)]:
            for o in own:
                radius = o.recon * rs + (2 if self.terrain(o.x, o.y) == "h" else 0)
                if _d((o.x, o.y), (e.x, e.y)) <= radius:
                    jx = min(self.w - 1, max(0, e.x + rng.randint(-err, err)))
                    jy = min(self.h - 1, max(0, e.y + rng.randint(-err, err)))
                    out.append({"unit_id": e.id, "kind": e.kind, "name": e.name,
                                "x": jx, "y": jy, "tick": tick})
                    break
        return out

    # ---- 视图 ----
    def unit_view(self, u: Unit) -> dict:
        return {"id": u.id, "side": u.side, "name": u.name, "kind": u.kind,
                "x": u.x, "y": u.y, "strength": round(u.strength),
                "supply": round(u.supply), "entrenched": u.entrenched,
                "alive": u.alive, "order": (u.order or {}).get("kind")}

    def side_units_view(self, side: str) -> list[dict]:
        return [self.unit_view(u) for u in self.units.values()
                if u.side == side and u.alive]

    def all_units_view(self) -> list[dict]:
        return [self.unit_view(u) for u in self.units.values() if u.alive]
