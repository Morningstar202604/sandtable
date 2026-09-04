"""阶段二（战役简报系统）验收测试。"""
from __future__ import annotations

from wargame.battlelib import BATTLE_PRESETS
from wargame.sim import Simulation


def test_battle_preset_has_briefing_field():
    """所有 BattlePreset 实例都有 briefing 字段（可为空字符串）。"""
    for p in BATTLE_PRESETS:
        assert isinstance(p.briefing, str)


def test_normandy_has_briefing():
    """诺曼底场景必须有非空简报。"""
    p = next(bp for bp in BATTLE_PRESETS if bp.pid == "normandy_1944")
    assert p.briefing, "normandy_1944 briefing is empty"
    assert "战役背景" in p.briefing
    assert "兵力对比" in p.briefing


def test_stalingrad_has_briefing():
    """斯大林格勒场景必须有非空简报。"""
    p = next(bp for bp in BATTLE_PRESETS if bp.pid == "stalingrad_1942")
    assert p.briefing, "stalingrad_1942 briefing is empty"
    assert "战役背景" in p.briefing


def test_briefing_contains_key_sections():
    """简报应包含标准章节：战役背景、兵力对比、地形要点、天气预判、历史参考。"""
    p = next(bp for bp in BATTLE_PRESETS if bp.pid == "normandy_1944")
    for section in ["战役背景", "兵力对比", "地形要点", "天气预判", "历史参考"]:
        assert section in p.briefing, f"简报缺少章节: {section}"


def test_sim_get_briefing_returns_dict():
    """get_briefing() 返回字典，包含必要字段。"""
    sim = Simulation(policy_mode="rule", seed=1, scenario="cross_river")
    briefing = sim.get_briefing()
    assert isinstance(briefing, dict)
    assert "scenario_name" in briefing
    assert "codename" in briefing
    assert "briefing" in briefing
    assert "objectives" in briefing
    assert "weather" in briefing
    assert "factions" in briefing


def test_sim_get_briefing_normandy():
    """诺曼底场景的简报应包含预设的简报文本。"""
    sim = Simulation(policy_mode="rule", seed=1, scenario="normandy",
                     battle_config={"preset": "normandy_1944"})
    briefing = sim.get_briefing()
    assert "霸王" in briefing["briefing"] or "两栖" in briefing["briefing"]
    assert briefing["preset_id"] == "normandy_1944"


def test_sim_get_briefing_cross_river_no_preset():
    """没有预设的场景使用 SCENARIO_DESC 作为简报 fallback。"""
    sim = Simulation(policy_mode="rule", seed=1, scenario="cross_river")
    briefing = sim.get_briefing()
    # cross_river has no preset, so briefing falls back to SCENARIO_DESC
    assert briefing["briefing"] != ""


def test_briefing_pulse_event_emitted_every_5_ticks():
    """每 5 拍应生成一条 briefing_pulse 事件。"""
    sim = Simulation(policy_mode="rule", seed=42, scenario="cross_river")
    initial_count = sum(1 for e in sim.events if e.get("type") == "briefing_pulse")
    # Run ticks 5, 10, 15 (each should emit one)
    for _ in range(15):
        sim.run_tick()
    final_count = sum(1 for e in sim.events if e.get("type") == "briefing_pulse")
    assert final_count > initial_count, "应在推演中生成 briefing_pulse 事件"


def test_briefing_pulse_event_structure():
    """briefing_pulse 事件结构正确。"""
    sim = Simulation(policy_mode="rule", seed=7, scenario="cross_river")
    # Run until tick 5 to get first pulse
    for _ in range(5):
        sim.run_tick()
    pulses = [e for e in sim.events if e.get("type") == "briefing_pulse"]
    assert len(pulses) >= 1
    pulse = pulses[0]
    assert "tick" in pulse
    assert "weather" in pulse
    assert "objectives" in pulse
    assert "unit_counts" in pulse


def test_sim_briefing_objectives_format():
    """简报中的 objectives 字段结构正确。"""
    sim = Simulation(policy_mode="rule", seed=1, scenario="normandy",
                     battle_config={"preset": "normandy_1944"})
    briefing = sim.get_briefing()
    objs = briefing["objectives"]
    assert isinstance(objs, list)
    if objs:
        assert "name" in objs[0]
        assert "controller" in objs[0] or "controlled_by" in objs[0]
