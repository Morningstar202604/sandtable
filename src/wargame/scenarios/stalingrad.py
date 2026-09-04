"""场景：斯大林格勒 1942-43（СТАГРАД · OPERAZIA URAN）——城市巷战完整战役。

苏德两军，逐屋争夺伏尔加河左岸工业带。
关键目标：马雅可夫斯基火车站（核心枢纽，价值3）与纺织厂、中央市场。
天气脚本：大雪（D1-5）→ 阴（D6-12）→ 晴朗（D13+）——对应史实冬季攻势。
增援批次：苏军第62集团军冬季兵员（T10）、德国第6集团军补给空投（T7）、
         朱可夫"天王星"预备队（T16）、保卢斯装甲营（T18）。
"""

from __future__ import annotations

from ..engine.world import World

SCENARIO_NAME = "斯大林格勒 1942-43 · СТАГРАД"

CODENAME = "天王星 URAN"
ERA = "二战 · 1942 年 8 月—1943 年 2 月"
THEATER = "斯大林格勒城区 · 伏尔加河左岸"
SCALE = "方面军级 · 苏第62集团军 vs 德第6集团军 · 30 个单位"
SCENARIO_DESC = ("人类战争史上最惨烈的城市消耗战。苏军逐屋逐楼死守伏尔加河西岸，"
                 "德军依托装甲与炮兵强攻城区核心枢纽。火车站、纺织厂、中央市场——"
                 "每一个街块都要用鲜血丈量。大雪、炮火、城市废墟，决定二战走向的战役在此展开。")

FACTIONS = [
    {"id": "sov", "name": "苏联红军"},
    {"id": "ger", "name": "德国国防军"},
]
WAR_PAIRS = [["sov", "ger"]]

CAMP_NAMES = {"sov": "苏军", "ger": "德军"}

W, H = 20, 14

DEFAULT_INTENTS = {
    "sov": "死守斯大林格勒城区！各部队依托建筑废墟与伏尔加河掩体坚决抵抗，"
           "绝不后退。等待朱可夫预备队发起天王星反击。",
    "ger": "突破伏尔加河防务，夺取马雅可夫斯基火车站与纺织厂。"
           "各师沿主街向河滩推进，以装甲营楔入敌纵深。",
}

RECON_TARGET = {"sov": [18, 7], "ger": [2, 7]}

AIR_POWER = {"sov": 0.6, "ger": 0.85}
WEATHER = [(0, "storm"), (8, "overcast"), (16, "clear")]

OBJECTIVES = [
    {"name": "马雅可夫斯基火车站", "x": 10, "y": 7, "value": 3},
    {"name": "纺织厂区", "x": 7, "y": 4, "value": 2},
    {"name": "中央市场", "x": 12, "y": 9, "value": 2},
    {"name": "巴甫洛夫大楼", "x": 14, "y": 6, "value": 2},
    {"name": "粮仓阵地", "x": 17, "y": 10, "value": 1},
    {"name": "造船厂前沿", "x": 18, "y": 3, "value": 1},
]

REINFORCEMENTS = [
    {"tick": 7, "side": "ger", "id": "ger-u-rf1", "name": "第6集团军空投补给队",
     "kind": "infantry", "x": 16, "y": 2, "pos": "ger:div2"},
    {"tick": 10, "side": "sov", "id": "sov-u-rf1", "name": "第62集团军冬季兵员",
     "kind": "infantry", "x": 18, "y": 10, "pos": "sov:div1"},
    {"tick": 12, "side": "ger", "id": "ger-u-rf2", "name": "第14装甲营增援",
     "kind": "armor", "x": 13, "y": 1, "pos": "ger:div1"},
    {"tick": 16, "side": "sov", "id": "sov-u-rf2", "name": "朱可夫天王星预备队",
     "kind": "armor", "x": 18, "y": 6, "pos": "sov:div2"},
    {"tick": 18, "side": "sov", "id": "sov-u-rf3", "name": "近卫第13步兵师",
     "kind": "infantry", "x": 18, "y": 12, "pos": "sov:div1"},
]

ORG_TITLES = {
    "sov": {
        "hq": "西南方面军司令部",
        "army": "第62集团军司令",
        "cos": "参谋长", "intel": "情报科长", "log": "后勤主任",
        "div1": "第139步兵团团长", "div2": "第38摩托化步兵团团长",
        "div1-b1": "巴甫洛夫大楼守备队", "div1-b2": "纺织厂防御分队",
        "div2-b3": "中央市场守备队", "div2-b4": "火车站突击组",
        "front": "伏尔加河畔观察哨",
    },
    "ger": {
        "hq": "陆军总司令部（上级）",
        "army": "第6集团军司令",
        "cos": "集团军参谋长", "intel": "情报官", "log": "补给官",
        "div1": "第295步兵师师长", "div2": "第14装甲师师长",
        "div1-b1": "第512掷弹兵团", "div1-b2": "第514掷弹兵团",
        "div2-b3": "第8装甲营", "div2-b4": "第75装甲掷弹营",
        "front": "城区侦察营",
    },
}

ORG_CONFIG = {
    "sov": {
        "army": {"style": "崔可夫式：寸土必争，逐屋抵抗，把敌人拖入消耗战的泥潭"},
        "div1": {"style": "斯大林格勒传统：宁可战死不退半步，在废墟中建立火力网",
                 "withdraw_threshold": 15},
        "div2-b3": {"style": "市场保卫战：以火力交叉封锁街心，不给敌人喘息之机"},
        "div2-b4": {"style": "火车站突击组：以排为单位实施短促反击，夺回失地"},
        "front": {"style": "伏尔加哨兵：对河对岸敌情观察最为敏锐，及时通报炮火支援需求"},
    },
    "ger": {
        "army": {"style": "保卢斯式：重视后勤与装甲集中使用，但受制于统帅部不批准机动撤退"},
        "div1": {"style": "295步兵师：东线老兵，擅长城区攻坚，但装备损耗严重"},
        "div2": {"style": "14装甲师：闪电战传统，渴望机动作战而非巷战消耗"},
        "div2-b3": {"style": "8装甲营：在坦克掩护下突击，但城市地形限制了装甲优势"},
        "intel": {"style": "低估苏军防御韧性与预备队投入规模，倾向认为敌已接近崩溃"},
    },
}

PLANS = {
    "sov": [
        {"name": "伏尔加防线·逐屋抵抗",
         "intent": "依托城区建筑与伏尔加河岸构建纵深防御，以小型分队坚守各要点",
         "assignments": {
             "sov:div1": {"mission": "左翼防御：巴甫洛夫大楼与纺织厂是核心支点，死守不放",
                          "target": [14, 6], "entrench": True,
                          "reg_targets": {"sov:div1-b1": [14, 6], "sov:div1-b2": [7, 4]},
                          "fire_support": [14, 6]},
             "sov:div2": {"mission": "右翼与枢纽：中央市场与火车站是核心，逐屋争夺",
                          "target": [10, 7], "entrench": True,
                          "reg_targets": {"sov:div2-b3": [12, 9], "sov:div2-b4": [10, 7]},
                          "fire_support": [12, 9]},
         }},
    ],
    "ger": [
        {"name": "城区推进·分割包围",
         "intent": "沿北部工业区与南部街区分路推进，切断苏军东西联系后压缩至伏尔加河岸",
         "assignments": {
             "ger:div1": {"mission": "北翼步兵：沿主街向南推进，夺占纺织厂与火车站",
                          "target": [7, 4],
                          "reg_targets": {"ger:div1-b1": [7, 4], "ger:div1-b2": [12, 9]},
                          "fire_support": [7, 4]},
             "ger:div2": {"mission": "南翼装甲突击：楔入城区核心，夺占火车站后向河岸发展",
                          "target": [10, 7],
                          "reg_targets": {"ger:div2-b3": [10, 7], "ger:div2-b4": [14, 6]},
                          "fire_support": [10, 7],
                          "reserve": "ger:div2-b4", "reserve_pos": [13, 3]},
         }},
    ],
}


class StalingradWorld(World):
    """斯大林格勒城区地图（20×14）。"""

    def __init__(self) -> None:
        super().__init__(w=W, h=H)
        grid = [["."] * W for _ in range(H)]

        def put(cells: list[tuple[int, int]], ch: str) -> None:
            for x, y in cells:
                if 0 <= x < W and 0 <= y < H:
                    grid[y][x] = ch

        # 伏尔加河（最右侧）
        for y in range(H):
            grid[y][19] = "~"
        # 桥梁过河点（两处）
        grid[4][18] = "B"
        grid[10][18] = "B"
        # 城区建筑群（废墟与坚固建筑）
        put([(x, y) for x in range(16, 19) for y in range(1, 13)], "C")  # 河东城区带
        put([(2, 6), (3, 6), (2, 7), (3, 7)], "C")    # 巴甫洛夫大楼
        put([(7, 3), (8, 3), (7, 4), (8, 4)], "C")    # 纺织厂
        put([(12, 8), (13, 8), (12, 9), (13, 9)], "C")  # 中央市场
        put([(10, 6), (11, 6), (10, 7), (11, 7)], "C")  # 马雅可夫斯基火车站
        put([(5, 10), (6, 10), (5, 11)], "C")         # 粮仓
        put([(17, 2), (18, 2)], "C")                   # 造船厂
        # 废墟街区（随机分布的残垣断壁）
        ruins = [
            (4, 2), (5, 2), (6, 2), (4, 3), (5, 3),
            (9, 3), (10, 3), (11, 3),
            (1, 5), (2, 5), (3, 5),
            (6, 5), (7, 5),
            (14, 5), (15, 5),
            (1, 8), (2, 8), (3, 8),
            (6, 8), (7, 8), (8, 8),
            (15, 8), (16, 8),
            (4, 10), (5, 10),
            (9, 10), (10, 10), (11, 10),
            (1, 12), (2, 12), (3, 12), (4, 12), (5, 12),
        ]
        for x, y in ruins:
            if grid[y][x] == ".":
                grid[y][x] = "f"  # 废墟 = 树林级掩体
        # 街道网（机动走廊）
        for x in range(W):
            if grid[7][x] == ".": grid[7][x] = "r"  # 中央大街
            if grid[4][x] == ".": grid[4][x] = "r"  # 北街
            if grid[10][x] == ".": grid[10][x] = "r"  # 南街
        for y in range(H):
            if grid[y][5] == ".": grid[y][5] = "r"  # 东向第5街
            if grid[y][10] == ".": grid[y][10] = "r"  # 东向第10街
            if grid[y][15] == ".": grid[y][15] = "r"  # 东向第15街
        # 废墟堆叠（更密集的城区）
        put([(6, 3), (7, 3), (9, 4), (10, 4), (14, 4), (15, 4),
             (6, 5), (9, 6), (14, 7), (15, 7), (16, 7),
             (6, 9), (7, 9), (9, 9), (14, 9), (15, 9),
             (6, 11), (7, 11), (9, 11), (14, 11), (15, 11)], "f")
        self.grid = grid


def build_world() -> World:
    w = StalingradWorld()

    # 补给站
    w.set_depot("sov", 18, 1)   # 河东苏军补给点
    w.set_depot("sov", 18, 12)  # 伏尔加南岸补给
    w.set_depot("ger", 1, 1)    # 德军西岸起点
    w.set_depot("ger", 1, 12)   # 德军南翼补给

    # ---- 苏军（sov）：伏尔加河东岸 + 城区坚守 ----
    w.add_unit("sov-u-r1", "sov", "西南方面军侦察营", "recon", 2, 18)
    w.add_unit("sov-u-a1", "sov", "第62集团军重炮营", "artillery", 5, 18)
    w.add_unit("sov-u-b1", "sov", "第139步兵团", "infantry", 8, 18)
    w.add_unit("sov-u-b2", "sov", "第38摩托化步兵团", "infantry", 7, 18)
    w.add_unit("sov-u-b3", "sov", "巴甫洛夫大楼守备队", "infantry", 10, 17)
    w.add_unit("sov-u-b4", "sov", "纺织厂防御分队", "infantry", 7, 13)
    w.add_unit("sov-u-b5", "sov", "中央市场守备队", "infantry", 8, 10)
    w.add_unit("sov-u-b6", "sov", "火车站突击组", "infantry", 8, 10)
    w.add_unit("sov-u-b7", "sov", "粮仓守备队", "infantry", 5, 11)
    w.add_unit("sov-u-b8", "sov", "造船厂先遣队", "infantry", 3, 14)

    # ---- 德军（ger）：西岸进攻 ----
    w.add_unit("ger-u-r1", "ger", "第6集团军侦察营", "recon", 3, 2)
    w.add_unit("ger-u-a1", "ger", "第516炮兵团", "artillery", 6, 3)
    w.add_unit("ger-u-a2", "ger", "第659重型炮兵营", "artillery", 5, 11)
    w.add_unit("ger-u-b1", "ger", "第512掷弹兵团", "infantry", 6, 4)
    w.add_unit("ger-u-b2", "ger", "第514掷弹兵团", "infantry", 5, 10)
    w.add_unit("ger-u-b3", "ger", "第295步兵师主力", "infantry", 6, 7)
    w.add_unit("ger-u-b4", "ger", "第8装甲营", "armor", 8, 5)
    w.add_unit("ger-u-b5", "ger", "第75装甲掷弹营", "armor", 7, 9)
    w.add_unit("ger-u-b6", "ger", "第14装甲师师部", "armor", 6, 8)
    w.add_unit("ger-u-b7", "ger", "第16摩托化步兵团", "infantry", 5, 3)

    # 指挥官标记：苏军守备队指挥官（带指挥光环）
    for uid in ["sov-u-b3", "sov-u-b4", "sov-u-b5", "sov-u-b6"]:
        if uid in w.units:
            w.units[uid].is_commander = True
            w.units[uid].command_radius = 4
            w.units[uid].leader_style = "defensive"
            w.units[uid].leader_skill = 0.75
    w.units["sov-u-b3"].leader_style = "fanatical"  # 巴甫洛夫式死守

    # 德军指挥官偏激进
    for uid in ["ger-u-b3", "ger-u-b4", "ger-u-b5", "ger-u-b6"]:
        if uid in w.units:
            w.units[uid].is_commander = True
            w.units[uid].command_radius = 5
            w.units[uid].leader_style = "aggressive"
            w.units[uid].leader_skill = 0.65

    # 初始经验：苏军守备队为 veteran（史实精英），德军为 regular
    for uid in ["sov-u-r1", "sov-u-b3", "sov-u-b4"]:
        if uid in w.units:
            w.units[uid].experience = 65
            w.units[uid].exp_level = "veteran"
    for uid in ["ger-u-r1", "ger-u-b3", "ger-u-b4"]:
        if uid in w.units:
            w.units[uid].experience = 50
            w.units[uid].exp_level = "regular"

    # 苏军初始工事：核心守备队已构筑简易掩体
    for uid in ["sov-u-b3", "sov-u-b4", "sov-u-b5", "sov-u-b6", "sov-u-b7"]:
        if uid in w.units:
            w.units[uid].entrench_progress = 3.0
            w.units[uid].formation = "static"

    # 天气：雪暴→阴→晴（对应史实1942冬→1943初）
    w.set_weather([(0, "storm"), (8, "overcast"), (16, "clear")])

    return w
