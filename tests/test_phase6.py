"""Phase 6：回放与指标系统验收测试。"""
from __future__ import annotations

import json

from wargame import replay
from wargame.sim import Simulation


def _sample_events() -> list[dict]:
    return [
        {"seq": 1, "t": 1, "type": "msg", "camp": "red", "sender": "red:hq",
         "recipient": "red:army", "kind": "order", "subject": "进攻",
         "body": "推进", "priority": 0},
        {"seq": 2, "t": 2, "type": "msg", "camp": "red", "sender": "red:army",
         "recipient": "red:hq", "kind": "ack", "subject": "收到",
         "body": "", "priority": 0},
        {"seq": 3, "t": 5, "type": "briefing_pulse", "tick": 5,
         "weather": "clear", "weather_name": "晴",
         "unit_counts": {"red": 5},
         "objectives": [{"name": "北高地", "controller": "red", "value": 2}]},
        {"seq": 4, "t": 6, "type": "combat", "camp": "red", "unit": "u1",
         "name": "第一营", "taken": 12, "vs": 8},
        {"seq": 5, "t": 7, "type": "destroyed", "camp": "blue", "unit": "u2",
         "name": "第二连", "x": 3, "y": 4},
        {"seq": 6, "t": 8, "type": "reinforce", "camp": "red", "unit": "r1",
         "name": "预备队", "x": 5, "y": 5},
        {"seq": 7, "t": 9, "type": "weather", "weather": "rain", "name": "雨"},
        {"seq": 8, "t": 10, "type": "llm_fallback", "camp": "red",
         "pos": "red:army", "error": "timeout"},
        {"seq": 9, "t": 12, "type": "msg", "camp": "blue", "sender": "blue:hq",
         "recipient": "blue:army", "kind": "order", "subject": "撤退",
         "body": "", "priority": 0},
    ]


class TestReplayLoader:
    def test_load_jsonl_rebuilds_events(self, tmp_path):
        p = tmp_path / "events.jsonl"
        p.write_text("\n".join(json.dumps(e, ensure_ascii=False)
                               for e in _sample_events()), encoding="utf-8")
        r = replay.load_jsonl(p)
        assert len(r["events"]) == 9
        assert r["max_tick"] == 12

    def test_load_jsonl_skips_corrupt_lines(self, tmp_path):
        p = tmp_path / "events.jsonl"
        good = _sample_events()
        p.write_text("\n".join([json.dumps(good[0], ensure_ascii=False),
                                 "{broken", ""]), encoding="utf-8")
        r = replay.load_jsonl(p)
        assert len(r["events"]) == 1

    def test_command_stats_ack_rate(self):
        r = replay.build_replay_data(_sample_events())
        st = r["command_stats"]["red"]
        assert st["orders"] == 1
        assert st["ack_rate"] == 1.0
        assert st["ack_latency"] == 1.0

    def test_series_from_briefing_pulse(self):
        r = replay.build_replay_data(_sample_events())
        assert len(r["series"]) == 1
        assert r["series"][0]["objectives"][0]["controller"] == "red"

    def test_campaign_events_filtered(self):
        r = replay.build_replay_data(_sample_events())
        kinds = [e["type"] for e in r["campaign_events"]]
        assert "combat" in kinds and "destroyed" in kinds and "reinforce" in kinds
        assert "msg" not in kinds


class TestReport:
    def test_report_contains_key_sections(self):
        r = replay.build_replay_data(_sample_events())
        md = replay.build_report(r, title="测试复盘")
        assert "# 测试复盘" in md
        assert "## 一、战况总览" in md
        assert "## 二、指挥链健康度" in md
        assert "## 三、目标控制时序" in md
        assert "## 四、关键事件" in md
        assert "北高地" in md


class TestMetricsHistory:
    def test_sim_records_metrics_history(self):
        sim = Simulation(policy_mode="rule", seed=7, scenario="normandy")
        for _ in range(5):
            sim.run_tick()
        assert sim.metrics_history
        assert sim.metrics_history[-1]["tick"] == 5
        last = sim.metrics_history[-1]
        assert "strength" in last and "score" in last and "objectives" in last
        assert set(last["strength"]) <= set(sim.factions)

    def test_metrics_history_view_downsample(self):
        sim = Simulation(policy_mode="rule", seed=7, scenario="normandy")
        for _ in range(10):
            sim.run_tick()
        view = sim.metrics_history_view(max_points=5)
        assert len(view) == 5
        assert view[0]["tick"] == 1
        # 降采样如实生效：40 拍取 10 点
        view10 = sim.metrics_history_view(max_points=10)
        assert len(view10) == 10
        # 非正参数不崩溃，仍返回至少 2 点
        assert len(sim.metrics_history_view(max_points=0)) >= 2
        assert len(sim.metrics_history_view(max_points=-3)) >= 2
