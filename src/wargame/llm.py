"""极简 LLM 客户端：OpenAI 兼容 chat completions 直连。

用 httpx 直调而不是 SDK——兼容 OpenAI/DeepSeek/通义/本地 Ollama 等
所有 OpenAI 兼容端点，一条代码路径，不锁厂商。
"""

from __future__ import annotations

import json
import logging
import random
import time

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
        self.top_p = settings.llm_top_p
        self.frequency_penalty = settings.llm_frequency_penalty
        self.presence_penalty = settings.llm_presence_penalty
        self._calls = 0
        # 决策级调用捕获：记录窗口内各次 LLM 请求的 prompt/响应/延迟，供调试中心回放。
        # 仿真单线程顺序决策，reset_capture()→chat()→drain_capture() 之间恰为单个智能体的一次决策。
        self._capture: list[dict] = []

    def reset_capture(self) -> None:
        self._capture = []

    def drain_capture(self) -> list[dict]:
        """取出并清空本次窗口内的全部 LLM 调用（若发生了）。"""
        c, self._capture = self._capture, []
        return c

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def reconfigure(self, api_key: str | None = None, base_url: str | None = None,
                    model: str | None = None, temperature: float | None = None,
                    max_tokens: int | None = None, top_p: float | None = None,
                    frequency_penalty: float | None = None,
                    presence_penalty: float | None = None) -> None:
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
        if top_p is not None:
            self.top_p = max(0.0, min(1.0, float(top_p)))
        if frequency_penalty is not None:
            self.frequency_penalty = max(-2.0, min(2.0, float(frequency_penalty)))
        if presence_penalty is not None:
            self.presence_penalty = max(-2.0, min(2.0, float(presence_penalty)))

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
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_err: Exception | None = None
        t0 = time.perf_counter()
        n_retries = max(1, settings.llm_retry)
        for attempt in range(n_retries):
            try:
                resp = httpx.post(
                    f"{self.base_url}/chat/completions",
                    json=payload, headers=headers, timeout=settings.llm_timeout,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"] or ""
                self._capture.append({
                    "system": system, "user": user, "response": content,
                    "latency_ms": round((time.perf_counter() - t0) * 1000),
                    "ok": True, "attempt": attempt + 1,
                })
                return content
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt < n_retries - 1:
                    delay = min(2 ** attempt * 0.1 + random.uniform(0, 0.05), 1.0)
                    time.sleep(delay)
        self._capture.append({
            "system": system, "user": user, "response": "",
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "ok": False, "error": str(last_err)[:200],
        })
        raise RuntimeError(f"LLM 请求失败: {last_err}")

    def chat_tools(self, system: str, user: str, tools: list[dict],
                   tool_choice: dict | str | None = None) -> dict:
        """结构化输出：让模型以原生工具调用(tools)产出决策。

        返回 {"text": 文本, "tool_calls": [{"name","arguments(dict)"}], "ok": bool}。
        走 OpenAI 兼容 tools 参数（OpenAI/DeepSeek/通义/Ollama 等端点均支持），
        这是各大 agent 框架内部的标准结构化输出路径——借标准机制，不再手搓 JSON。
        失败时抛 RuntimeError，由上层降级为规则策略或 JSON 提示词路径。
        """
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
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "tools": tools,
        }
        if tool_choice:
            payload["tool_choice"] = tool_choice
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_err: Exception | None = None
        t0 = time.perf_counter()
        n_retries = max(1, settings.llm_retry)
        for attempt in range(n_retries):
            try:
                resp = httpx.post(
                    f"{self.base_url}/chat/completions",
                    json=payload, headers=headers, timeout=settings.llm_timeout,
                )
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]
                calls = []
                for tc in msg.get("tool_calls") or []:
                    try:
                        args = json.loads(tc["function"].get("arguments") or "{}")
                    except (TypeError, ValueError):
                        args = {}
                    calls.append({"name": tc["function"]["name"], "arguments": args})
                rec = {
                    "system": system, "user": user,
                    "response": msg.get("content") or "",
                    "tool_calls": calls,
                    "latency_ms": round((time.perf_counter() - t0) * 1000),
                    "ok": True, "attempt": attempt + 1,
                }
                self._capture.append(rec)
                return {"text": rec["response"], "tool_calls": calls, "ok": True}
            except Exception as e:  # noqa: BLE001
                last_err = e
        self._capture.append({
            "system": system, "user": user, "response": "",
            "tool_calls": [], "latency_ms": round((time.perf_counter() - t0) * 1000),
            "ok": False, "error": str(last_err)[:200],
        })
        raise RuntimeError(f"LLM 请求失败: {last_err}")

    @staticmethod
    def extract_json(text: str) -> dict:
        """从模型输出中稳健提取 JSON 对象（容忍代码围栏与前后噪声）。

        推理型模型常见两个坑：先输出思维链再给结论、先复述 schema
        示例再给真实答案。因此扫描全部花括号配对片段，返回**最后**
        一个能 json.loads 成功的对象。

        增强：
        1. 自动剥离 OpenAI reasoning 标签 (<thinking>...</thinking>)
        2. 尝试截断到最后一个合法 JSON 闭合处
        3. 若主体是完整对象但尾部有尾逗号/噪声，裁剪后重试
        """
        import re as _re
        t = text.strip()
        # 剥离 reasoning / thinking 标签（某些推理模型的输出头）
        t = _re.sub(r"<thinking[^>]*>.*?</thinking>", "", t, flags=_re.DOTALL).strip()
        t = _re.sub(r"<thought[^>]*>.*?</thought>", "", t, flags=_re.DOTALL).strip()
        segments = [t]
        if "```" in t:
            segments.extend(seg.strip().removeprefix("json").strip()
                            for seg in t.split("```"))
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
                        candidate = seg[start:i + 1]
                        try:
                            obj = json.loads(candidate)
                            if isinstance(obj, dict):
                                # 不中断扫描：模型常先复述 schema 示例再给真实决策，
                                # 取最后一个合法对象才是实际答案
                                last = obj
                        except json.JSONDecodeError:
                            pass
                        start = None
            # 若循环结束仍未找到合法 dict（推理溢出截断），尝试修复
            if last is None:
                # 找最后一个完整的 } 位置
                for cut in range(len(seg) - 1, start or 0, -1):
                    if seg[cut] == "}":
                        fix = seg[start:cut + 1]
                        try:
                            obj = json.loads(fix)
                            if isinstance(obj, dict):
                                last = obj
                                break
                        except json.JSONDecodeError:
                            continue
        if last is None:
            raise ValueError("输出中没有可解析的 JSON")
        return last


llm_client = LLMClient()
