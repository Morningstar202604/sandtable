"""冒烟测试：整场推演可跑通、指挥链贯通、阵营隔离有效、世界可复现。"""

from __future__ import annotations

import pytest

from wargame.bus import Bus
from wargame.org import Registry, build_camp_org
from wargame.schemas import Message, MsgKind
from wargame.sim import Simulation


def _run(policy_mode: str, ticks: int, seed: int, tmp_path) -> Simulation:
    sim = Simulation(policy_mode=policy_mode, seed=seed,
                     run_dir=tmp_path / f"run-{seed}")
    for _ in range(ticks):
        sim.run_tick()
    return sim


def test_command_chain_flows_down_and_up(tmp_path):
    """军长意图 → 师命令 → 团执行；团/师报告 → 军长。"""
    sim = _run("rule", 40, 7, tmp_path)
    orders_to_regs = [
        e for e in sim.events
        if e["type"] == "msg" and e["kind"] == "order"
        and ("div1-b" in e["recipient"] or "div2-b" in e["recipient"])
    ]
    assert orders_to_regs, "没有任何命令下达到团级"
    reports_to_army = [
        e for e in sim.events
        if e["type"] == "msg" and e["kind"] in ("sitrep", "escalation", "request")
        and e["recipient"].endswith(":army")
    ]
    assert reports_to_army, "军长没有收到任何上行反馈"
    actions = [e for e in sim.events if e["type"] == "action" and e["camp"] == "red"]
    assert actions, "红方没有任何部队动作"


def test_combat_and_intel_occur(tmp_path):
    sim = _run("rule", 45, 7, tmp_path)
    assert any(e["type"] in ("combat", "fire") for e in sim.events), "全程未发生交战"
    for side in ("red", "blue"):
        assert any(e["type"] == "intel" and e["camp"] == side for e in sim.events), \
            f"{side} 没有产生任何侦察情报"


def test_camp_isolation_hard_block():
    """跨阵营消息在总线层被直接拒绝——隔离是结构约束，不靠自觉。"""
    registry = Registry(build_camp_org("red") + build_camp_org("blue"))
    red_bus = Bus("red", registry)
    with pytest.raises(ValueError):
        red_bus.send(Message.create(0, "red:army", "blue:div1", MsgKind.SITREP, "试探"))
    red_bus.send(Message.create(0, "red:army", "red:cos", MsgKind.REQUEST, "方案"))
    assert red_bus.pending() == 1


def test_world_determinism_same_seed(tmp_path):
    """同种子两场推演，世界终态一致（LLM 不参与世界结算）。"""
    a = _run("rule", 25, 11, tmp_path)
    b = _run("rule", 25, 11, tmp_path)
    pos_a = sorted((u.id, u.x, u.y, round(u.strength)) for u in a.world.units.values())
    pos_b = sorted((u.id, u.x, u.y, round(u.strength)) for u in b.world.units.values())
    assert pos_a == pos_b


def test_metrics(tmp_path):
    """复盘指标：命令下行有确认、反馈量非零、兵力统计为正。"""
    sim = _run("rule", 25, 7, tmp_path)
    m = sim.compute_metrics()
    assert set(m["camps"]) == {"red", "blue"}
    for side, c in m["camps"].items():
        assert c["orders"] > 0, f"{side} 没有命令下行"
        assert c["ack_rate"] is not None and c["ack_rate"] > 0, \
            f"{side} 的命令从未被确认"
        assert c["sitreps"] > 0, f"{side} 没有任何态势报告"
        assert c["strength"] > 0, f"{side} 兵力统计异常"


def test_intel_store_never_contains_own_side(tmp_path):
    """情报库里只应有敌方轮廓——阵营内视角完整性。"""
    sim = _run("rule", 15, 7, tmp_path)
    for side, camp in sim.camps.items():
        for entry in camp.intel.view():
            assert not entry["unit_id"].startswith(f"{side}-"), \
                f"{side} 情报库混入了己方单位"


def test_normandy_scenario(tmp_path):
    """诺曼底多方大场景：三方阵营/大地图/天气脚本/增援/目标控制。"""
    sim = Simulation(policy_mode="rule", seed=7, scenario="normandy",
                     run_dir=tmp_path / "n")
    assert sim.factions == ["usa", "uk", "ger"]
    # 交战关系：盟军内部不开战，对德全面开战
    assert not sim.world.at_war("usa", "uk")
    assert sim.world.at_war("usa", "ger") and sim.world.at_war("uk", "ger")
    # 大地图与开局风暴（史实：D-Day 风暴瘫痪空中力量）
    assert (sim.world.w, sim.world.h) == (44, 30)
    assert sim.world.weather == "storm"
    for _ in range(40):
        sim.run_tick()
    assert sim.world.weather == "clear", "天气脚本未按 T16 转晴"
    # 场景化编制命名与性格配置注入
    assert "美第5军" in sim.registry.get("usa:army").title
    assert sim.registry.get("usa:army").side_name == "美军"
    assert sim.registry.get("usa:div1-b1").config.get("withdraw_threshold") == 30
    # 增援批次入场（101 空降 T12 / 12SS T15）
    assert "usa-u-b5" in sim.world.units and "ger-u-b5" in sim.world.units
    # 滩头交战与目标控制
    assert any(e["type"] in ("combat", "fire") for e in sim.events), "诺曼底全程未交战"
    assert any(o["controller"] for o in sim.world.objectives), "40 拍内无任何目标被控制"
    assert any(e["type"] == "msg" and e["kind"] == "order" and "div" in e["recipient"]
               for e in sim.events), "没有命令下达到师团级"
    m = sim.compute_metrics()
    assert set(m["camps"]) == {"usa", "uk", "ger"}
    assert sum(m["score"].values()) > 0, "目标得分未累计"


def test_dynamic_scenario_builder(tmp_path):
    """AI 场景导入：spec → 动态场景 → 可推演。"""
    from wargame.scenarios.dynamic import make_dynamic_scenario
    from wargame.scenarios import SCENARIOS
    spec = {
        "name": "测试三方混战",
        "width": 30, "height": 22,
        "factions": [
            {"id": "alpha", "name": "阿尔法", "intent": "夺占中心城",
             "style": "激进", "units": [{"name": "先锋营", "kind": "armor", "x": 3, "y": 5}]},
            {"id": "beta", "name": "贝塔", "intent": "死守中心城",
             "units": [{"name": "守备团", "kind": "infantry", "x": 15, "y": 11}]},
            {"id": "gamma", "name": "伽马", "units": []},
        ],
        "objectives": [{"name": "中心城", "x": 15, "y": 11, "value": 3}],
    }
    ns = make_dynamic_scenario(spec)
    sid = "test_dynamic_scene"
    SCENARIOS[sid] = ns
    try:
        sim = Simulation(policy_mode="rule", seed=3, scenario=sid,
                         run_dir=tmp_path / "d")
        assert sim.factions == ["alpha", "beta", "gamma"]
        for _ in range(10):
            sim.run_tick()
        assert any(e["type"] == "msg" for e in sim.events)
        assert sim.world.at_war("alpha", "beta") and sim.world.at_war("alpha", "gamma")
    finally:
        SCENARIOS.pop(sid, None)
