"""智能体层：职位即智能体，可插拔决策策略（规则 / LLM）。"""

from .base import Agent, SituationView, Task
from .llm_policy import LLMPolicy, PolicyError
from .rule_policy import RulePolicy

__all__ = ["Agent", "LLMPolicy", "PolicyError", "RulePolicy", "SituationView", "Task"]
