"""场景注册表：每个场景模块导出统一接口。

场景模块必须提供：
- SCENARIO_NAME: str                       显示名
- build_world() -> World                   地图与初始单位
- DEFAULT_INTENTS: dict[side, str]         开局注入的上级意图
- PLANS: dict[side, list[option]]          参谋方案选项（rule 模式直接采用）
- RECON_TARGET: dict[side, [x, y]]         侦察部署目标点
可选：
- CAMP_NAMES: dict[side, str]              阵营显示名（默认红军/蓝军）
- ORG_TITLES: dict[side, dict[key, str]]   职位名覆盖（历史编制命名）
"""

from __future__ import annotations

from . import cross_river, normandy

SCENARIOS: dict[str, object] = {
    "cross_river": cross_river,
    "normandy": normandy,
}
DEFAULT_SCENARIO = "cross_river"


def load_scenario(name: str):
    return SCENARIOS.get(name) or SCENARIOS[DEFAULT_SCENARIO]
