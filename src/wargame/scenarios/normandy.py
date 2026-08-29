"""场景：诺曼底登陆 1944（OVERLORD · D-DAY）——多方阵营完整版。

三方格局（钢铁雄心式）：
- usa 美第5军（奥马哈/犹他/82空降/第2装甲师）
- uk  英加第1军（宝剑/朱诺/黄金/英6空降）
- ger 德第7集团军（352步兵师 + 21装甲师）

盟军两军互不交战（WAR_PAIRS 只对德宣战）——引擎层的"交战关系"
让多方格局成立：接壤的同盟不交火，对德则全面开战。

地理要素（44×30，西=英吉利海峡）：五滩、奥恩/迪沃/维尔/瑟勒四河、
科唐坦沼泽、铁路公路网、八座城市目标。
天气脚本：0-7 风暴（史实）→ 阴 → 晴；空军遮断 盟军1.0/0.7 vs 德军0.35。
增援批次：101空降(T12)/英51师(T18)/12SS(T15)/装甲教导师(T22)。
"""

from __future__ import annotations

from ..engine.world import World

SCENARIO_NAME = "诺曼底登陆 1944 · OVERLORD"

FACTIONS = [
    {"id": "usa", "name": "美军"},
    {"id": "uk", "name": "英加军"},
    {"id": "ger", "name": "德军"},
]
WAR_PAIRS = [["usa", "ger"], ["uk", "ger"]]  # 盟军内部不开战

CAMP_NAMES = {"usa": "美军", "uk": "英加军", "ger": "德军"}

W, H = 44, 30

DEFAULT_INTENTS = {
    "usa": "实施霸王行动美军事段：奥马哈、犹他突击上陆，夺卡朗唐打通科唐坦半岛，"
           "尽早打开瑟堡港。舰炮与空中支援已就位，注意沼泽迟滞装甲。",
    "uk": "实施霸王行动英加军段：宝剑、朱诺、黄金上陆，夺巴约，"
          "沿卡昂轴线突击；英6空降师确保奥恩河桥梁东翼安全。",
    "ger": "依托大西洋壁垒坚守滩头要点，迟滞敌军于水线；装甲预备队对宝剑—朱诺"
           "之间实施反突击，将登陆之敌赶下海。利用铁路向卡昂—法莱斯调集装甲兵力。",
}

RECON_TARGET = {"usa": [10, 19], "uk": [12, 9], "ger": [8, 4]}

AIR_POWER = {"usa": 1.0, "uk": 0.7, "ger": 0.35}
WEATHER = [(0, "storm"), (8, "overcast"), (16, "clear")]

OBJECTIVES = [
    {"name": "瑟堡", "x": 6, "y": 1, "value": 3},
    {"name": "卡朗唐", "x": 10, "y": 20, "value": 2},
    {"name": "巴约", "x": 15, "y": 13, "value": 2},
    {"name": "卡昂", "x": 24, "y": 5, "value": 3},
    {"name": "圣洛", "x": 20, "y": 22, "value": 2},
    {"name": "法莱斯", "x": 33, "y": 7, "value": 2},
]

REINFORCEMENTS = [
    {"tick": 12, "side": "usa", "id": "usa-u-b5", "name": "美第101空降师（后续梯队）",
     "kind": "infantry", "x": 6, "y": 23, "pos": "usa:div1"},
    {"tick": 18, "side": "uk", "id": "uk-u-b5", "name": "英第51高地师",
     "kind": "infantry", "x": 5, "y": 4, "pos": "uk:div2"},
    {"tick": 15, "side": "ger", "id": "ger-u-b5", "name": "第12SS装甲师",
     "kind": "armor", "x": 33, "y": 8, "pos": "ger:div2"},
    {"tick": 22, "side": "ger", "id": "ger-u-b6", "name": "装甲教导师",
     "kind": "armor", "x": 20, "y": 24, "pos": "ger:div1"},
]

ORG_TITLES = {
    "usa": {
        "hq": "盟军最高统帅部（上级）",
        "army": "美第5军军长",
        "cos": "军参谋长", "intel": "情报参谋", "log": "后勤参谋",
        "div1": "美步兵登陆军", "div2": "美空降与装甲集群",
        "div1-b1": "美第29步兵师（奥马哈）", "div1-b2": "美第4步兵师（犹他）",
        "div2-b3": "美第82空降师", "div2-b4": "美第2装甲师",
        "front": "滩头观察哨",
    },
    "uk": {
        "hq": "盟军最高统帅部（上级）",
        "army": "英加第1军军长",
        "cos": "军参谋长", "intel": "情报参谋", "log": "后勤参谋",
        "div1": "英加登陆军", "div2": "英空降与后续集群",
        "div1-b1": "英第3步兵师（宝剑）", "div1-b2": "加第3步兵师（朱诺）",
        "div2-b3": "英第50师（黄金）", "div2-b4": "英第6空降师（飞马桥）",
        "front": "滩头观察哨",
    },
    "ger": {
        "hq": "国防军统帅部（上级）",
        "army": "第7集团军司令",
        "cos": "集团军参谋长", "intel": "情报参谋", "log": "补给参谋",
        "div1": "第352步兵师师长", "div2": "第21装甲师师长",
        "div1-b1": "第915掷弹兵团（奥马哈）", "div1-b2": "第916掷弹兵团（科唐坦）",
        "div2-b3": "第125装甲掷弹团", "div2-b4": "第192装甲掷弹团",
        "front": "岸防观察哨",
    },
}

ORG_CONFIG = {
    "usa": {
        "army": {"style": "美军军长：火力至上，不惜弹药，强调舰炮与空中协同"},
        "div1-b1": {"style": "奥马哈的意志：即使伤亡惨重，滩头也必须夺占，决不在水线后退",
                    "withdraw_threshold": 30},
        "div2-b3": {"style": "空降兵传统：深敌作战，自主果断，敢于以少胜多"},
    },
    "uk": {
        "army": {"style": "蒙哥马利式：谨慎缜密，按时刻表推进，重视后勤与后备队"},
        "div2-b4": {"style": "英6空降师：夺桥后坚决据守东翼，决不轻易放弃飞马桥",
                    "withdraw_threshold": 25},
    },
    "ger": {
        "army": {"style": "指挥层迟缓：装甲预备队动用需逐级请示统帅部；"
                          "倾向相信登陆只是牵制性佯攻", "withdraw_threshold": 55},
        "intel": {"style": "受大西洋壁垒宣传影响，倾向低估盟军登陆规模与方向"},
        "div1": {"style": "352师：东线老兵，射击纪律严明，擅长反斜面配置"},
        "div2": {"style": "第21装甲师：当日东段唯一投入反击的装甲预备队，坚决果断"},
        "div1-b2": {"style": "静态师：守土有责但机动力与火力孱弱", "withdraw_threshold": 55},
        "div2-b3": {"style": "装甲掷弹兵：狂热激进，崇尚立即反击"},
    },
}

PLANS = {
    "usa": [
        {"name": "美军事段：夺半岛、开瑟堡",
         "intent": "奥马哈、犹他上陆后向内陆发展，夺卡朗唐打通半岛，指向圣洛",
         "assignments": {
             "usa:div1": {"mission": "步兵军：夺奥马哈滩头纵深与卡朗唐",
                          "target": [7, 18], "next": [20, 22],
                          "reg_targets": {"usa:div1-b1": [7, 18], "usa:div1-b2": [10, 20]},
                          "fire_support": [7, 18]},
             "usa:div2": {"mission": "空降与装甲集群：82空降控扼卡朗唐以北，"
                                     "第2装甲师向伊西尼方向发展",
                          "target": [9, 16], "next": [15, 16],
                          "reg_targets": {"usa:div2-b3": [9, 19], "usa:div2-b4": [9, 16]},
                          "fire_support": [7, 18]},
         }},
    ],
    "uk": [
        {"name": "英加军段：巴约—卡昂轴线",
         "intent": "宝剑/朱诺/黄金上陆，夺巴约，向卡昂推进；东翼固守奥恩河桥",
         "assignments": {
             "uk:div1": {"mission": "登陆军：宝剑、朱诺展开，夺巴约",
                          "target": [8, 5], "next": [15, 13],
                          "reg_targets": {"uk:div1-b1": [8, 5], "uk:div1-b2": [8, 9]},
                          "fire_support": [9, 7]},
             "uk:div2": {"mission": "英50师向巴约汇合；英6空降死守飞马桥东翼",
                          "target": [8, 13], "next": [15, 13],
                          "reg_targets": {"uk:div2-b3": [8, 13], "uk:div2-b4": [28, 3]},
                          "fire_support": [9, 7]},
         }},
    ],
    "ger": [
        {"name": "装甲反突击·岸防坚守",
         "intent": "岸防兵固守滩头要点，第21装甲师向宝剑—朱诺之间反突击，将敌赶下海",
         "assignments": {
             "ger:div1": {"mission": "第352步兵师：坚守奥马哈、科唐坦正面，"
                                     "依托沼泽水网迟滞敌军",
                           "target": [7, 18], "entrench": True,
                           "reg_targets": {"ger:div1-b1": [7, 18], "ger:div1-b2": [7, 23]},
                           "fire_support": [5, 18]},
             "ger:div2": {"mission": "第21装甲师：主力向宝剑—朱诺之间反突击，"
                                     "一部为预备队控扼卡昂",
                           "target": [9, 7], "entrench": False,
                           "reg_targets": {"ger:div2-b3": [9, 7]},
                           "fire_support": [9, 7],
                           "reserve": "ger:div2-b4", "reserve_pos": [28, 10]},
         }},
    ],
}


class NormandyWorld(World):
    """诺曼底专属大地图（44×30）。"""

    def __init__(self) -> None:
        super().__init__(w=W, h=H)
        grid = [["."] * W for _ in range(H)]

        def put(cells: list[tuple[int, int]], ch: str) -> None:
            for x, y in cells:
                if 0 <= x < W and 0 <= y < H:
                    grid[y][x] = ch

        # 英吉利海峡
        for y in range(H):
            for x in range(4):
                grid[y][x] = "~"
        # 河流：奥恩 / 迪沃 / 维尔 / 瑟勒
        put([(27, y) for y in range(0, 9)], "~")
        put([(39, y) for y in range(3, 12)], "~")
        put([(12, y) for y in range(21, H)], "~")
        put([(19, y) for y in range(10, 15)], "~")
        put([(27, 4), (39, 7), (12, 24), (19, 12)], "B")
        # 沼泽：科唐坦水网
        put([(7, 21), (8, 20), (8, 22), (7, 23), (9, 23), (8, 24), (10, 24),
             (9, 25), (11, 25), (10, 26), (12, 23), (11, 21), (6, 22), (9, 27)], "m")
        # 铁路/公路网（机动走廊）
        put([(8, y) for y in range(3, 20)], "r")             # 瑟堡—卡朗唐纵线
        put([(x, 8) for x in range(25, 34)], "r")            # 卡昂—法莱斯横线
        put([(13, y) for y in range(21, 27)], "r")           # 卡朗唐—库唐斯线
        put([(16, 12), (17, 11), (18, 10), (19, 9), (20, 8),
             (21, 7), (22, 6), (23, 6)], "r")                # 巴约—卡昂公路
        # 城市目标
        put([(6, 1), (7, 1)], "C")       # 瑟堡
        put([(10, 20), (11, 20)], "C")   # 卡朗唐
        put([(9, 16), (10, 16)], "C")    # 伊西尼
        put([(15, 13), (16, 13)], "C")   # 巴约
        put([(24, 5), (25, 5)], "C")     # 卡昂
        put([(20, 22), (21, 22)], "C")   # 圣洛
        put([(15, 26), (16, 26)], "C")   # 库唐斯
        put([(33, 7), (34, 7)], "C")     # 法莱斯
        # 树篱与林地（bocage）
        put([(12, 11), (13, 11), (14, 12), (12, 12), (10, 12), (11, 13),
             (17, 16), (18, 17), (19, 16), (20, 18), (18, 19), (17, 18),
             (23, 10), (24, 11), (25, 9), (26, 10), (23, 12),
             (23, 22), (24, 23), (25, 21), (26, 24), (24, 25),
             (28, 18), (29, 19), (30, 17), (31, 20),
             (17, 2), (18, 3), (19, 2), (36, 18), (37, 19)], "f")
        # 丘陵要点
        put([(11, 17), (26, 7), (30, 3), (16, 9), (22, 26), (34, 3),
             (7, 27), (36, 14)], "h")
        self.grid = grid


def build_world() -> World:
    w = NormandyWorld()
    w.set_depot("usa", 4, 14)    # 盟军滩头弹药补给点
    w.set_depot("uk", 4, 7)      # 英加军滩头补给点
    w.set_depot("ger", 24, 4)    # 卡昂补给站
    w.set_depot("ger", 20, 23)   # 圣洛补给站

    # ---- 美军（usa）：西段上陆 ----
    w.add_unit("usa-u-r1", "usa", "美军空降侦察队", "recon", 7, 15)
    w.add_unit("usa-u-a1", "usa", "舰炮支援群（奥马哈）", "artillery", 4, 20)
    w.add_unit("usa-u-a2", "usa", "舰炮支援群（犹他）", "artillery", 4, 24)
    w.add_unit("usa-u-b1", "usa", "美第29步兵师", "infantry", 5, 18)   # 奥马哈
    w.add_unit("usa-u-b2", "usa", "美第4步兵师", "infantry", 5, 24)    # 犹他
    w.add_unit("usa-u-b3", "usa", "美第82空降师", "infantry", 6, 21)   # 圣梅尔埃格利斯
    w.add_unit("usa-u-b4", "usa", "美第2装甲师", "armor", 4, 16)       # 后续梯队

    # ---- 英加军（uk）：东段上陆 ----
    w.add_unit("uk-u-r1", "uk", "英军侦察分队", "recon", 6, 4)
    w.add_unit("uk-u-a1", "uk", "舰炮支援群（宝剑）", "artillery", 4, 5)
    w.add_unit("uk-u-a2", "uk", "舰炮支援群（黄金）", "artillery", 4, 12)
    w.add_unit("uk-u-b1", "uk", "英第3步兵师", "infantry", 5, 5)       # 宝剑
    w.add_unit("uk-u-b2", "uk", "加第3步兵师", "infantry", 5, 9)       # 朱诺
    w.add_unit("uk-u-b3", "uk", "英第50师", "infantry", 5, 13)         # 黄金
    w.add_unit("uk-u-b4", "uk", "英第6空降师", "infantry", 29, 3)      # 奥恩河东

    # ---- 德军（ger）：岸防 + 装甲预备队 ----
    w.add_unit("ger-u-r1", "ger", "岸防观察哨", "recon", 8, 4)
    w.add_unit("ger-u-a1", "ger", "第352炮兵团", "artillery", 8, 19)
    w.add_unit("ger-u-a2", "ger", "第21装炮团", "artillery", 21, 3)
    w.add_unit("ger-u-b1", "ger", "第915掷弹兵团", "infantry", 7, 18)  # 奥马哈正面
    w.add_unit("ger-u-b2", "ger", "第916掷弹兵团", "infantry", 7, 23)  # 科唐坦
    w.add_unit("ger-u-b3", "ger", "第125装甲掷弹团", "armor", 22, 4)   # 卡昂近郊
    w.add_unit("ger-u-b4", "ger", "第192装甲掷弹团", "armor", 28, 9)   # 奥恩河东
    return w
