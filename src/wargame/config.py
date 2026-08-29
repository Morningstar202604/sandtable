"""运行配置：环境变量读取 + 极简 .env 加载。

不引入 python-dotenv 依赖——只需要 KEY=VALUE 的解析能力，10 行就够。
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    """加载工作目录下的 .env（不覆盖已存在的环境变量）。"""
    path = Path(".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


class Settings:
    """全局配置单例。LLM 三项任一缺失即整体降级为规则策略。"""

    def __init__(self) -> None:
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "")
        self.llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.seed: int = int(os.getenv("WARGAME_SEED", "7"))
        # 每 tick 允许的 LLM 调用上限，超出时该次决策退化为规则策略，防止 token 失控
        self.max_llm_calls_per_tick: int = int(os.getenv("WARGAME_MAX_LLM_CALLS", "40"))

    @property
    def llm_available(self) -> bool:
        return bool(self.llm_api_key)


settings = Settings()
