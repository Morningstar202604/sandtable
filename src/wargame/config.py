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
        # 结构化输出开关：用原生工具调用(tools)替代手搓 JSON 提示词；
        # 关掉(WARGAME_LLM_TOOLS=0)则回退为 JSON 提示词路径。失败时自动回退，无需干预。
        self.llm_use_tools: bool = os.getenv("WARGAME_LLM_TOOLS", "1") != "0"
        # 单次 LLM 请求失败重试次数（网络类异常自动重试）
        self.llm_retry: int = int(os.getenv("WARGAME_LLM_RETRY", "2"))
        # 单次 LLM 请求超时秒数
        self.llm_timeout: float = float(os.getenv("WARGAME_LLM_TIMEOUT", "90"))
        # 采样参数：top_p 核采样、频率惩罚、存在惩罚（部分端点不支持则自动忽略）
        self.llm_top_p: float = float(os.getenv("WARGAME_LLM_TOP_P", "1"))
        self.llm_frequency_penalty: float = float(os.getenv("WARGAME_LLM_FREQ_PENALTY", "0"))
        self.llm_presence_penalty: float = float(os.getenv("WARGAME_LLM_PRESENCE_PENALTY", "0"))
        # LLM 失败是否自动降级为规则策略（关掉则失败即报错停在本拍，便于暴露问题）
        self.fallback_enabled: bool = os.getenv("WARGAME_LLM_FALLBACK", "1") != "0"

    @property
    def llm_available(self) -> bool:
        return bool(self.llm_api_key)


settings = Settings()
