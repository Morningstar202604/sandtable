"""Phase 5: LLM 路径优化验收测试。"""
from __future__ import annotations

import pytest

from wargame.llm import LLMClient

# ── extract_json 增强测试 ──────────────────────────────────────

class TestExtractJSON:
    """验证 extract_json 对各类常见输出的鲁棒性。"""

    def test_clean_json(self):
        """标准 JSON 直接解析。"""
        text = '{"thoughts":"进攻","messages":[],"world_actions":[]}'
        assert LLMClient.extract_json(text) == {
            "thoughts": "进攻", "messages": [], "world_actions": []
        }

    def test_markdown_fence(self):
        """模型输出带 ```json ... ``` 代码围栏。"""
        text = '```json\n{"thoughts":"推进","messages":[],"world_actions":[]}\n```'
        result = LLMClient.extract_json(text)
        assert result["thoughts"] == "推进"

    def test_thinking_tag_prefix(self):
        """推理模型先输出 <thinking> 再给 JSON。"""
        text = (
            '<thinking>\n根据态势分析，敌方在左侧集结，应加强右侧防御。\n</thinking>\n'
            '{"thoughts":"加强右翼","messages":[],"world_actions":[]}'
        )
        result = LLMClient.extract_json(text)
        assert result["thoughts"] == "加强右翼"

    def test_schema_restatement_then_json(self):
        """模型先复述 schema 再给真实输出。"""
        text = (
            '根据你的要求，我需要输出如下格式：\n'
            '{"thoughts": "...", "messages": [...], "world_actions": [...]}\n'
            '实际决策：\n{"thoughts":"敌主力左移，建议向右机动","messages":[],"world_actions":[]}'
        )
        result = LLMClient.extract_json(text)
        assert result["thoughts"] == "敌主力左移，建议向右机动"

    def test_truncated_json_recovered(self):
        """模型思维链导致 JSON 被截断，修复后仍能找到合法部分。"""
        text = (
            '让我分析一下...\n'
            '首先看敌情：敌军正在左翼移动，我需要...'
            '{"thoughts":"左翼受压，请求支援","messages":[{"to":"hq","kind":"request"}],"world_actions":[]}'
            '\n（分析完毕）'
        )
        result = LLMClient.extract_json(text)
        assert result["thoughts"] == "左翼受压，请求支援"
        assert len(result["messages"]) == 1

    def test_no_valid_json_raises(self):
        """完全没有 JSON 时抛出 ValueError。"""
        with pytest.raises(ValueError, match="可解析"):
            LLMClient.extract_json("这是一段纯文本，没有任何 JSON。")

    def test_nested_json_in_thinking(self):
        """thinking 块内含假 JSON，应忽略并找到真正的 JSON。"""
        text = (
            '<thinking>例如一个示例 JSON：{"fake": true}</thinking>\n'
            '{"thoughts":"真正决策","messages":[],"world_actions":[]}'
        )
        result = LLMClient.extract_json(text)
        assert result.get("fake") is None
        assert result["thoughts"] == "真正决策"

    def test_multiple_candidates_returns_last_valid(self):
        """多个合法 JSON 片段，返回最后一个。"""
        text = (
            '{"thoughts":"旧决策","messages":[],"world_actions":[]}'
            '中间说明文字\n'
            '{"thoughts":"新决策","messages":[],"world_actions":[]}'
        )
        result = LLMClient.extract_json(text)
        assert result["thoughts"] == "新决策"

    def test_array_not_dict_ignored(self):
        """JSON 数组不是有效候选，应继续寻找字典。"""
        text = '[1,2,3] 一些文字 {"thoughts":"找到了","messages":[],"world_actions":[]}'
        result = LLMClient.extract_json(text)
        assert result["thoughts"] == "找到了"


# ── LLMClient 实例测试（不涉及网络）─────────────────────────────

class TestLLMClient:
    """LLMClient 基本行为（不依赖实际网络）。"""

    def test_unconfigured_raises(self):
        """未配置 API Key 时 chat 抛 RuntimeError。"""
        client = LLMClient()
        # 临时清空 key
        orig_key = client.api_key
        client.api_key = ""
        try:
            with pytest.raises(RuntimeError, match="LLM 未配置"):
                client.chat("sys", "usr")
        finally:
            client.api_key = orig_key

    def test_extract_json_roundtrip(self):
        """复杂嵌套 JSON 也能正确提取。"""
        text = '{"thoughts":"机动","messages":[{"to":"u1","kind":"order","subject":"左翼穿插","body":"从左翼穿插敌阵地","priority":0}],"world_actions":[{"kind":"move","unit":"u1","target":[5,3]}]}'
        result = LLMClient.extract_json(text)
        assert result["messages"][0]["kind"] == "order"
        assert result["world_actions"][0]["target"] == [5, 3]
