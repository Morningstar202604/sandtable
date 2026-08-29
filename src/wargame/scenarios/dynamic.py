"""AI 动态场景：把用户喂给 LLM 的资料变成可推演的场景。

make_dynamic_scenario(spec) 将 LLM 意图识别/分类的输出（ factions、
兵力、目标、意图、性格）打包成与静态场景模块同构的命名空间，
注册进 SCENARIOS 后即可在主界面选择推演。

限制：动态场景使用空白开阔地图（目标城市按坐标落成城镇格），
编制套用"集团军—两师—每师两团+炮兵"结构；战术方案为通用
"向目标推进"，可在推演中用意图注入接管。
"""

from __future__ import annotations

import re
from types import SimpleNamespace

from ..engine.world import World


def _safe_id(text: str, fallback: str) -> str:
    sid = re.sub(r"[^0-9a-zA-Z_]", "_", str(text)).strip("_").lower()
    return sid or fallback


def make_dynamic_scenario(spec: dict):
    """spec 字段（由 LLM 从资料中提取）：
    name, width, height,
    factions: [{id, name, intent, style, units: [{name, kind, x, y}]}],
    objectives: [{name, x, y, value}]
    """
    factions_in = spec.get("factions") or []
    factions = []
    for f in factions_in[:6]:  # 上限 6 方，防止失控
        fid = _safe_id(f.get("id") or f.get("name"), f"f{len(factions) + 1}")
        factions.append({"id": fid, "name": str(f.get("name") or fid),
                         "intent": str(f.get("intent", "")),
                         "style": str(f.get("style", "")),
                         "units": f.get("units") or []})
    if len(factions) < 2:
        raise ValueError("场景至少需要两个阵营")

    W = max(20, min(60, int(spec.get("width") or 30)))
    H = max(14, min(44, int(spec.get("height") or 22)))
    objectives = [{"name": str(o.get("name", f"目标{i + 1}")),
                   "x": int(o.get("x", W // 2)), "y": int(o.get("y", H // 2)),
                   "value": int(o.get("value", 1))}
                  for i, o in enumerate(spec.get("objectives") or [])][:12]
    center = (W // 2, H // 2)

    class DynamicWorld(World):
        def __init__(self) -> None:
            super().__init__(w=W, h=H)
            grid = [["."] * W for _ in range(H)]
            for o in objectives:
                for dx in (-1, 0):
                    x, y = o["x"] + dx, o["y"]
                    if 0 <= x < W and 0 <= y < H:
                        grid[y][x] = "C"
            # 空白开阔地形上稀疏布一些林地/丘陵，避免完全单调
            for i in range(0, W * H // 40):
                x, y = (i * 7) % W, (i * 13) % H
                if grid[y][x] == ".":
                    grid[y][x] = "f" if i % 3 else "h"
            self.grid = grid

    def build_world() -> World:
        w = DynamicWorld()
        kinds = ("infantry", "armor", "artillery", "recon")
        # 每方固定编制槽位：r1 侦察、a1/a2 炮兵、b1..b4 团——超出截断
        for fi, f in enumerate(factions):
            x0 = 2 + fi * (W - 4) // max(1, len(factions))  # 各方沿边缘展开
            slots = [("r1", "recon"), ("a1", "artillery"), ("a2", "artillery"),
                     ("b1", "infantry"), ("b2", "armor"),
                     ("b3", "infantry"), ("b4", "infantry")]
            custom = list(f["units"])[:7]
            for si, (slot, default_kind) in enumerate(slots):
                spec_u = custom[si] if si < len(custom) else {}
                kind = spec_u.get("kind", default_kind)
                kind = kind if kind in kinds else "infantry"
                x = int(spec_u.get("x", x0 + si % 3))
                y = int(spec_u.get("y", 2 + (si * 5 + fi * 3) % (H - 4)))
                x = max(1, min(W - 2, x))
                y = max(1, min(H - 2, y))
                w.add_unit(f"{f['id']}-u-{slot}", f["id"],
                           str(spec_u.get("name") or f"{f['name']}{slot}部"),
                           kind, x, y)
        for fi, f in enumerate(factions):
            # 各方补给站沿己方边缘布置
            w.set_depot(f["id"], max(1, min(W - 2, 2 + fi * (W - 4) // max(1, len(factions)))),
                        H - 2 - fi)
        return w

    org_titles = {f["id"]: {"army": f"{f['name']}集团军司令",
                            "div1": f"{f['name']}第1师师长",
                            "div2": f"{f['name']}第2师师长",
                            "div1-b1": f"{f['name']}第1团", "div1-b2": f"{f['name']}第2团",
                            "div2-b3": f"{f['name']}第3团", "div2-b4": f"{f['name']}第4团"}
                  for f in factions}
    org_config = {f["id"]: ({"army": {"style": f["style"]}} if f["style"] else {})
                  for f in factions}
    camp_names = {f["id"]: f["name"] for f in factions}

    def _default_plans() -> dict:
        # 通用方案：各团向最近目标推进（空白地图上的沙盘开局）
        plans = {}
        for f in factions:
            objs = objectives or [{"name": "中心", "x": center[0], "y": center[1], "value": 1}]
            tgt = [min(objs, key=lambda o: o["x"] + o["y"])["x"],
                   min(objs, key=lambda o: o["x"] + o["y"])["y"]]
            plans[f["id"]] = [{
                "name": "向目标推进",
                "intent": f.get("intent") or "夺取战役目标",
                "assignments": {
                    f"{f['id']}:div1": {"mission": "向既定目标推进", "target": tgt,
                                        "reg_targets": {f"{f['id']}:div1-b1": tgt}},
                    f"{f['id']}:div2": {"mission": "向既定目标推进", "target": tgt,
                                        "reg_targets": {f"{f['id']}:div2-b3": tgt}},
                },
            }]
        return plans

    return SimpleNamespace(
        SCENARIO_NAME=str(spec.get("name") or "AI 导入场景"),
        CAMP_NAMES=camp_names,
        FACTIONS=[{"id": f["id"], "name": f["name"]} for f in factions],
        DEFAULT_INTENTS={f["id"]: f["intent"] or "完成既定战役任务。" for f in factions},
        RECON_TARGET={f["id"]: [max(1, W // 4), max(1, H // 4)] for f in factions},
        PLANS=_default_plans(),
        ORG_TITLES=org_titles,
        ORG_CONFIG=org_config,
        AIR_POWER={f["id"]: 0.3 for f in factions},
        WEATHER=[(0, "clear")],
        OBJECTIVES=objectives,
        REINFORCEMENTS=[],
        build_world=build_world,
    )
