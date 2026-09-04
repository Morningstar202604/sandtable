"""JSONL 回放加载与复盘报告：从 runs/<run>/events.jsonl 离线重建推演复盘。

推演中所有事件已逐拍落盘为 JSONL（见 Simulation._emit），推演结束后可
用本模块离线复盘：重建事件流、统计指挥链健康度、生成 Markdown 复盘报告。
在线讲评（导演部讲评 → 导出复盘报告）同样复用本模块，保证线上线下口径一致。
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

WEATHER_CN = {"clear": "晴", "overcast": "阴", "rain": "雨",
              "storm": "暴风雪", "snowstorm": "暴风雪"}


def load_jsonl(path: str | Path) -> dict:
    """读取一次推演落盘的 events.jsonl，重建复盘数据字典。

    跳过损坏行（例如某拍落盘中断残留的半行），保证离线复盘不被坏行中断。
    """
    path = Path(path)
    events: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return build_replay_data(events, meta={"path": str(path)})


def build_replay_data(events: list[dict], meta: dict | None = None) -> dict:
    """从事件流重建复盘数据（load_jsonl 与在线讲评共用同一口径）。"""
    events = list(events)
    max_tick = max((e.get("t", 0) for e in events), default=0)
    sides = sorted({e.get("camp") for e in events if e.get("camp")})
    event_counts: dict[str, int] = {}
    for e in events:
        event_counts[e["type"]] = event_counts.get(e["type"], 0) + 1
    weather_changes = [
        {"t": e.get("t"), "weather": e.get("weather"),
         "name": WEATHER_CN.get(e.get("weather"), e.get("weather"))}
        for e in events if e["type"] == "weather"]
    series = [
        {"tick": e.get("tick", e.get("t")),
         "weather_name": e.get("weather_name"),
         "unit_counts": e.get("unit_counts") or {},
         "objectives": e.get("objectives") or []}
        for e in events if e["type"] == "briefing_pulse"]
    campaign_events = [
        e for e in events
        if e["type"] in ("combat", "destroyed", "reinforce",
                         "weather", "llm_fallback")]
    return {
        "meta": dict(meta or {}),
        "events": events,
        "max_tick": max_tick,
        "sides": sides,
        "event_counts": event_counts,
        "weather_changes": weather_changes,
        "series": series,
        "campaign_events": campaign_events,
        "command_stats": {s: _command_stats(events, s) for s in sides},
    }


def _command_stats(events: list[dict], side: str) -> dict:
    """按参演方统计指挥链健康度（与 Simulation.compute_metrics 同口径）。"""
    msgs = [e for e in events if e.get("type") == "msg" and e.get("camp") == side]
    kinds: dict[str, int] = {}
    for m in msgs:
        kinds[m["kind"]] = kinds.get(m["kind"], 0) + 1
    orders = [m for m in msgs if m["kind"] == "order"]
    acks = [m for m in msgs if m["kind"] == "ack"]
    acked, latencies = 0, []
    for o in orders:
        matches = [a for a in acks
                   if a["sender"] == o["recipient"]
                   and a["recipient"] == o["sender"] and a["t"] >= o["t"]]
        if matches:
            acked += 1
            latencies.append(min(a["t"] for a in matches) - o["t"])
    return {
        "orders": len(orders),
        "ack_rate": round(acked / len(orders), 2) if orders else None,
        "ack_latency": round(statistics.mean(latencies), 1) if latencies else None,
        "sitreps": kinds.get("sitrep", 0),
        "requests": kinds.get("request", 0),
        "escalations": kinds.get("escalation", 0),
        "intel": kinds.get("intel", 0),
        "decisions": sum(1 for e in events
                         if e.get("type") == "agent" and e.get("camp") == side),
        "msg_lost": sum(1 for e in events
                        if e.get("type") == "msg_lost" and e.get("camp") == side),
        "isolation_blocked": sum(1 for e in events
                                 if e.get("type") == "isolation_blocked"
                                 and e.get("camp") == side),
        "llm_fallback": sum(1 for e in events
                            if e.get("type") == "llm_fallback"
                            and e.get("camp") == side),
    }


def build_report(data: dict, title: str | None = None) -> str:
    """生成 Markdown 复盘报告（关键事件 + 决策摘要 + 指标统计）。"""
    meta = data.get("meta", {})
    name = title or meta.get("title") or "沙盘推演复盘"
    max_tick = data.get("max_tick", 0)
    ec = data.get("event_counts", {})
    lines: list[str] = []
    lines.append(f"# {name}")
    lines.append("")
    lines.append(f"> 数据源：`{meta.get('path', '在线推演')}` · 推演至 **T{max_tick}**"
             f" · 事件 **{sum(ec.values())}** 条"
             + (f" · 策略 `{meta.get('policy')}` · 种子 `{meta.get('seed')}`"
                if meta.get("policy") else ""))
    lines.append("")

    lines.append("## 一、战况总览")
    lines.append("")
    bits = [f"推演 **T{max_tick}**", f"事件 **{sum(ec.values())}** 条",
            f"交火 **{ec.get('combat', 0)}** 次",
            f"单位被毁 **{ec.get('destroyed', 0)}** 个",
            f"增援 **{ec.get('reinforce', 0)}** 批",
            f"LLM 降级 **{ec.get('llm_fallback', 0)}** 次",
            f"情报 **{ec.get('intel', 0)}** 条"]
    lines.append("　".join(bits))
    lines.append("")
    wc = data.get("weather_changes", [])
    if wc:
        lines.append("**天气变化**：" + " → ".join(f"T{w['t']} {w['name']}" for w in wc))
        lines.append("")

    lines.append("## 二、指挥链健康度")
    lines.append("")
    stats = data.get("command_stats", {})
    if stats:
        lines.append("| 参演方 | 命令下行 | 确认率 | 确认延迟 | 态势报告 | 请示 |"
                 " 告警 | 情报 | 电文中断 | LLM降级 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for side, c in stats.items():
            ack = f"{round(c['ack_rate'] * 100)}%" if c["ack_rate"] is not None else "—"
            lat = f"{c['ack_latency']}拍" if c["ack_latency"] is not None else "—"
            lines.append(f"| {side} | {c['orders']} | {ack} | {lat} | {c['sitreps']} |"
                     f" {c['requests']} | {c['escalations']} | {c['intel']} |"
                     f" {c['msg_lost']} | {c['llm_fallback']} |")
        lines.append("")
    else:
        lines.append("（无参演方数据）")
        lines.append("")

    lines.append("## 三、目标控制时序")
    lines.append("")
    series = data.get("series", [])
    obj_hist: dict[str, list[tuple[int, str | None]]] = {}
    for s in series:
        for o in s.get("objectives", []):
            nm = o.get("name")
            ctrl = o.get("controller")
            h = obj_hist.setdefault(nm, [])
            if not h or h[-1][1] != ctrl:
                h.append((s["tick"], ctrl))
    if obj_hist:
        for nm, hist in obj_hist.items():
            chain = " → ".join(("未控制" if ctrl is None else ctrl) + f"(T{t})"
                               for t, ctrl in hist)
            lines.append(f"- **{nm}**：{chain}")
        lines.append("")
    else:
        lines.append("（无目标控制数据）")
        lines.append("")

    lines.append("## 四、关键事件")
    lines.append("")
    ce = data.get("campaign_events", [])
    if ce:
        for e in ce[:60]:
            t = e.get("t", 0)
            if e["type"] == "combat":
                line = (f"- **T{t}** 交火：{e.get('name', '?')} "
                        f"(承受 {e.get('taken', '?')} / 对敌 {e.get('vs', '?')})")
            elif e["type"] == "destroyed":
                line = (f"- **T{t}** 摧毁：{e.get('camp', '?')} {e.get('name', '?')}"
                        f" @ ({e.get('x')},{e.get('y')})")
            elif e["type"] == "reinforce":
                line = f"- **T{t}** 增援到达：{e.get('camp', '?')} {e.get('name', '?')}"
            elif e["type"] == "weather":
                line = (f"- **T{t}** 天气变化："
                        f"{WEATHER_CN.get(e.get('weather'), e.get('weather'))}")
            else:
                line = (f"- **T{t}** LLM 降级：{e.get('pos', '?')}（"
                        f"{str(e.get('error', ''))[:60]}）")
            lines.append(line)
        lines.append("")
    else:
        lines.append("（无关键事件）")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*报告由 将台（WARGENERALS）自动生成 · 用于推演后的复盘讲评。*")
    lines.append("")
    return "\n".join(lines)
