"""极简 LLM 客户端：OpenAI 兼容 chat completions 直连。

用 httpx 直调而不是 SDK——兼容 OpenAI/DeepSeek/通义/本地 Ollama 等
所有 OpenAI 兼容端点，一条代码路径，不锁厂商。
"""

from __future__ import annotations

import json
import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model
        self.temperature = 0.3
        self.max_tokens = 1600  # 推理型模型思维链也计入输出预算，给足余量
        self._calls = 0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def reconfigure(self, api_key: str | None = None, base_url: str | None = None,
                    model: str | None = None, temperature: float | None = None,
                    max_tokens: int | None = None) -> None:
        """运行时改配置（Web 设置面板用）。原地更新，持有本客户端引用的策略无需重建。"""
        if api_key:
            self.api_key = api_key
        if base_url:
            self.base_url = base_url.rstrip("/")
        if model:
            self.model = model
        if temperature is not None:
            self.temperature = max(0.0, min(1.0, float(temperature)))
        if max_tokens is not None:
            self.max_tokens = max(100, min(4000, int(max_tokens)))

    def reset_budget(self) -> None:
        self._calls = 0

    def chat(self, system: str, user: str) -> str:
        """单轮对话。带一次重试；超预算抛 RuntimeError 由上层降级为规则策略。"""
        if not self.available:
            raise RuntimeError("LLM 未配置")
        if self._calls >= settings.max_llm_calls_per_tick:
            raise RuntimeError("LLM 调用预算耗尽")
        self._calls += 1
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_err: Exception | None = None
        for _ in range(2):
            try:
                resp = httpx.post(
                    f"{self.base_url}/chat/completions",
                    json=payload, headers=headers, timeout=90,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"] or ""
            except Exception as e:  # noqa: BLE001  网络类异常统一重试一次后上抛
                last_err = e
        raise RuntimeError(f"LLM 请求失败: {last_err}")

    @staticmethod
    def extract_json(text: str) -> dict:
        """从模型输出中稳健提取 JSON 对象（容忍代码围栏与前后噪声）。

        推理型模型常见两个坑：先输出思维链再给结论、先复述 schema
        示例再给真实答案。因此扫描全部花括号配对片段，返回**最后**
        一个能 json.loads 成功的对象。
        """
        text = text.strip()
        segments = [text]
        if "```" in text:
            segments.extend(seg.strip().removeprefix("json").strip()
                            for seg in text.split("```"))
        last: dict | None = None
        for seg in segments:
            depth = 0
            start = None
            for i, ch in enumerate(seg):
                if ch == "{":
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == "}" and depth > 0:
                    depth -= 1
                    if depth == 0 and start is not None:
                        try:
                            last = json.loads(seg[start:i + 1])
                        except json.JSONDecodeError:
                            pass  # 该片段非法，继续扫
                        start = None
        if last is None:
            raise ValueError("输出中没有可解析的 JSON")
        return last


llm_client = LLMClient()
