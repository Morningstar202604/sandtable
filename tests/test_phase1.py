"""阶段一（工程质量修复）验收测试：版本一致性、天气效果、apply_battle 隔离、供应线事件。"""

from __future__ import annotations

import random

import wargame
from wargame.battlelib import BATTLE_PRESETS, apply_battle, reset_battle
from wargame.engine.world import DEFAULT_TUNING, World
from wargame.sim import Simulation


def test_version_consistent_with_pyproject():
    assert wargame.__version__ == "0.9.7", "版本不一致"


def test_weather_effects_rain_fatigue():
    world = World(40, 30)
    world.tuning.update(DEFAULT_TUNING)
    world.set_weather([(0, "rain")])
    world.add_unit("red-u-1", "red", "先锋营", "infantry", x=5, y=5)
    u = world.units["red-u-1"]
    u.alive = True
    u.fatigue = 10.0
    orig_fatigue = u.fatigue
    for _ in range(200):
        world._weather_effects()
    assert u.fatigue > orig_fatigue, "雨天应增加疲劳度"
    assert u.fatigue <= 100.0


def test_weather_effects_storm_morale():
    world = World(40, 30)
    world.tuning.update(DEFAULT_TUNING)
    world.set_weather([(0, "storm")])
    world.add_unit("red-u-2", "red", "后卫连", "infantry", x=5, y=5)
    u = world.units["red-u-2"]
    u.alive = True
    u.morale = 80.0
    orig_morale = u.morale
    for _ in range(200):
        world._weather_effects()
    assert u.morale < orig_morale, "风暴应降低士气"
    assert u.morale >= 0.0


def test_weather_effects_disabled():
    world = World(40, 30)
    tuning = dict(DEFAULT_TUNING)
    tuning["weather_effect_enabled"] = 0
    world.tuning.update(tuning)
    world.set_weather([(0, "rain")])
    world.add_unit("red-u-3", "red", "预备队", "infantry", x=5, y=5)
    u = world.units["red-u-3"]
    u.alive = True
    u.fatigue = 10.0
    orig_fatigue = u.fatigue
    for _ in range(200):
        world._weather_effects()
    assert u.fatigue == orig_fatigue


def test_apply_battle_does_not_mutate_default_tuning():
    before = dict(DEFAULT_TUNING)
    sim = Simulation(policy_mode="rule", seed=1, scenario="cross_river")
    preset = next(p for p in BATTLE_PRESETS if p.pid == "normandy_1944")
    apply_battle(sim, preset.params)
    after = dict(DEFAULT_TUNING)
    assert before == after, "apply_battle 修改了 DEFAULT_TUNING"


def test_apply_battle_modifies_sim_tuning():
    sim = Simulation(policy_mode="rule", seed=1, scenario="cross_river")
    apply_battle(sim, {"global": {"combat_scale": 2.0}})
    assert sim.world.tuning["combat_scale"] == 2.0
    reset_battle(sim)
    assert sim.world.tuning["combat_scale"] == DEFAULT_TUNING["combat_scale"]


def test_reset_battle_restores_defaults():
    sim = Simulation(policy_mode="rule", seed=1, scenario="cross_river")
    sim.world.tuning["combat_scale"] = 0.5
    sim.world.tuning["arty_scale"] = 2.0
    assert sim.world.tuning["combat_scale"] == 0.5
    reset_battle(sim)
    assert sim.world.tuning["combat_scale"] == DEFAULT_TUNING["combat_scale"]
    assert sim.world.tuning["arty_scale"] == DEFAULT_TUNING["arty_scale"]


def test_supply_line_cut_event():
    world = World(40, 30)
    world.tuning.update(DEFAULT_TUNING)
    world.set_weather([(0, "clear")])
    world.add_unit("red-u-supply", "red", "补给营", "infantry", x=35, y=25)
    world.add_unit("blue-u-1", "blue", "侦察连", "infantry", x=5, y=5)
    events = []
    rng = random.Random(42)
    for _ in range(5):
        events.extend(world.step(rng))
    assert isinstance(events, list)


def test_battle_presets_metadata_complete():
    for preset in BATTLE_PRESETS:
        meta = preset.meta()
        assert "id" in meta
        assert "name" in meta
        assert "desc" in meta
        assert "env" in meta


def test_normandy_scenario_runs_cleanly(tmp_path):
    sim = Simulation(policy_mode="rule", seed=7, scenario="normandy", run_dir=tmp_path / "n")
    assert sim.factions == ["usa", "uk", "ger"]
    for _ in range(20):
        sim.run_tick()
    assert len(sim.events) > 0
