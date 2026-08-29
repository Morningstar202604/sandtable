"""场景：渡河攻坚（RIVER CROSSING）。

虚构训练场景：河流把战场一分为二，两座桥是天然瓶颈。
组织的协同与摩擦（渡场拥堵、火力协调、报告延迟）都将在这条河上集中体现。
"""

from __future__ import annotations

from ..engine.world import World

SCENARIO_NAME = "渡河攻坚 · RIVER CROSSING"

CAMP_NAMES = {"red": "红军", "blue": "蓝军"}

DEFAULT_INTENTS = {
    "red": "集中主力从北桥渡河，夺占河东城镇；一部从南桥实施助攻牵制敌军。"
           "得手后向北发展进攻。",
    "blue": "依托东岸要点组织坚固防御，重点控制南北两处渡场，"
            "迟滞消耗进攻之敌，保存有生力量。",
}

RECON_TARGET = {"red": [10, 3], "blue": [8, 3]}

PLANS = {
    "red": [
        {"name": "北桥主攻",
         "intent": "集中主力自北桥渡河夺占河东城镇，一部南桥助攻牵制",
         "assignments": {
             "red:div1": {"mission": "主攻：自北桥（12,4）渡河，夺占河东城镇（18,7）",
                          "target": [12, 4], "next": [18, 7], "fire_support": [12, 4]},
             "red:div2": {"mission": "助攻：自南桥（12,11）渡河，牵制敌军并向城镇发展",
                          "target": [12, 11], "next": [18, 8], "fire_support": [12, 11]},
         }},
        {"name": "南桥主攻",
         "intent": "集中主力自南桥渡河夺占河东城镇，一部北桥助攻牵制",
         "assignments": {
             "red:div1": {"mission": "助攻：自北桥（12,4）渡河，牵制敌军",
                          "target": [12, 4], "next": [18, 7], "fire_support": [12, 4]},
             "red:div2": {"mission": "主攻：自南桥（12,11）渡河，夺占河东城镇（18,8）",
                          "target": [12, 11], "next": [18, 8], "fire_support": [12, 11]},
         }},
    ],
    "blue": [
        {"name": "河岸纵深防御",
         "intent": "依托东岸要点固守，火力控制两处渡场，迟滞消耗进攻之敌",
         "assignments": {
             "blue:div1": {"mission": "坚守北桥东岸要点，炮兵压制渡场",
                           "target": [13, 4], "entrench": True, "fire_support": [12, 4]},
             "blue:div2": {"mission": "坚守南桥东岸要点，第4团为预备队",
                           "target": [13, 11], "entrench": True,
                           "fire_support": [12, 11],
                           "reserve": "blue:div2-b4", "reserve_pos": [16, 10]},
         }},
    ],
}


def build_world() -> World:
    w = World()
    w.set_depot("red", 2, 8)
    w.set_depot("blue", 21, 8)
    # 红军（进攻方，西岸集结）：军侦察连 + 两个师（各配炮兵营）
    w.add_unit("red-u-r1", "red", "红军军侦察连", "recon", 7, 3)
    w.add_unit("red-u-a1", "red", "红军第1师炮兵营", "artillery", 4, 6)
    w.add_unit("red-u-a2", "red", "红军第2师炮兵营", "artillery", 4, 11)
    w.add_unit("red-u-b1", "red", "红军摩步第1团", "infantry", 5, 4)
    w.add_unit("red-u-b2", "red", "红军摩步第2团", "infantry", 5, 11)
    w.add_unit("red-u-b3", "red", "红军装甲第3团", "armor", 4, 8)
    w.add_unit("red-u-b4", "red", "红军装甲第4团", "armor", 3, 10)
    # 蓝军（防御方，东岸纵深）
    w.add_unit("blue-u-r1", "blue", "蓝军军侦察连", "recon", 16, 2)
    w.add_unit("blue-u-a1", "blue", "蓝军第1师炮兵营", "artillery", 16, 5)
    w.add_unit("blue-u-a2", "blue", "蓝军第2师炮兵营", "artillery", 16, 12)
    w.add_unit("blue-u-b1", "blue", "蓝军摩步第1团", "infantry", 14, 4)
    w.add_unit("blue-u-b2", "blue", "蓝军摩步第2团", "infantry", 14, 11)
    w.add_unit("blue-u-b3", "blue", "蓝军装甲第3团", "armor", 17, 7)
    w.add_unit("blue-u-b4", "blue", "蓝军装甲第4团", "armor", 19, 9)
    return w
