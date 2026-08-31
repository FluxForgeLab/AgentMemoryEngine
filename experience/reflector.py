from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Protocol

from .model import Reflection


class Reflector(Protocol):
    """Reflection Engine 的最小接口。"""

    def reflect(
        self,
        *,
        task: str,
        action: str,
        result: str,
        success: bool | None = None,
    ) -> Reflection:
        ...


class CallableReflector:
    """
    用任意 Python callable 作为 Reflector。

    很适合：
        - 单元测试
        - 接入已有 Agent/LLM Harness
        - 避免 ExperienceLoop 与具体模型 SDK 耦合
    """

    def __init__(self, fn: Callable[..., Reflection]) -> None:
        self._fn = fn

    def reflect(
        self,
        *,
        task: str,
        action: str,
        result: str,
        success: bool | None = None,
    ) -> Reflection:
        return self._fn(
            task=task,
            action=action,
            result=result,
            success=success,
        )


class LLMReflector:
    """
    与模型厂商无关的 Reflection 实现。

    text_generator 只需满足：
        prompt: str -> model_output: str

    因此 OpenAI、DeepSeek、本地模型、现有 Harness 都可以接进来。
    """

    def __init__(
        self,
        text_generator: Callable[[str], str],
        *,
        default_score: float = 0.5,
    ) -> None:
        if not 0.0 <= default_score <= 1.0:
            raise ValueError("default_score must be between 0 and 1")
        self._text_generator = text_generator
        self._default_score = default_score

    def reflect(
        self,
        *,
        task: str,
        action: str,
        result: str,
        success: bool | None = None,
    ) -> Reflection:
        prompt = self._build_prompt(
            task=task,
            action=action,
            result=result,
            success=success,
        )

        raw = self._text_generator(prompt)
        payload = self._parse_json(raw)

        lesson = str(payload.get("lesson", "")).strip()
        if not lesson:
            raise ValueError("reflector output is missing lesson")

        score = payload.get("score", self._default_score)
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = self._default_score
        score = max(0.0, min(score, 1.0))

        should_store = bool(payload.get("should_store", True))
        reasoning = payload.get("reasoning")
        if reasoning is not None:
            reasoning = str(reasoning).strip() or None

        return Reflection(
            lesson=lesson,
            score=score,
            should_store=should_store,
            reasoning=reasoning,
        )

    @staticmethod
    def _build_prompt(
        *,
        task: str,
        action: str,
        result: str,
        success: bool | None,
    ) -> str:
        success_text = "unknown" if success is None else str(success).lower()

        return f"""
You are the reflection component of an Agent Experience Loop.

Your job is NOT to summarize the trace. Extract only a reusable lesson that could improve future behavior.

Analyze three questions:
1. What happened?
2. Why did it happen?
3. What should the agent do differently or repeat next time?

Do not invent causes that are unsupported by the supplied trace. If the evidence is insufficient to form a reliable reusable lesson, set should_store=false and use a low score.

Return JSON only with this schema:
{{
  "lesson": "a concise, actionable, reusable lesson",
  "score": 0.0,
  "should_store": true,
  "reasoning": "brief explanation of why this lesson is justified"
}}

TASK:
{task}

ACTION:
{action}

RESULT:
{result}

SUCCESS:
{success_text}
""".strip()

    @staticmethod
    def _parse_json(text: str) -> dict:
        if not isinstance(text, str):
            raise TypeError("text_generator must return a string")

        text = text.strip()
        if not text:
            raise ValueError("empty reflector output")

        # 先尝试严格 JSON。
        try:
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError("reflector JSON must be an object")
            return value
        except json.JSONDecodeError:
            pass

        # 兼容模型偶尔返回 ```json ... ```。
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
        if fenced:
            value = json.loads(fenced.group(1))
            if isinstance(value, dict):
                return value

        # 最后尝试截取第一个 JSON object。
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            value = json.loads(text[start : end + 1])
            if isinstance(value, dict):
                return value

        raise ValueError("cannot parse reflector output as JSON")
