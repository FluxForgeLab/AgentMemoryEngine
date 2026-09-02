from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.config import Settings
from app.observability.trace import emit, span

_PROVIDER_DEFAULTS = {
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "kimi": ("https://api.moonshot.cn/v1", "moonshot-v1-32k"),
}


class ChatLLM(Protocol):
    provider: str
    model: str

    async def complete(self, messages: list[dict[str, str]]) -> "ChatResult":
        ...


class ChatLLMError(RuntimeError):
    pass


@dataclass
class ChatResult:
    text: str
    elapsed_ms: float
    usage: dict[str, Any] | None = None
    finish_reason: str | None = None


def uses_fixed_sampling(model: str) -> bool:
    name = (model or "").strip().lower()
    return name.startswith("kimi-k") or name in {
        "k3",
        "kimi-for-coding",
        "kimi-for-coding-highspeed",
    }


def build_chat_request_body(
    *,
    model: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    body: dict[str, Any] = {"model": model, "messages": messages}
    if not uses_fixed_sampling(model):
        body["temperature"] = 0.3
    return body


def http_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return (response.text or "")[:800]
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = error.get("message") or error.get("msg")
        if message:
            return str(message)[:800]
    if isinstance(error, str) and error.strip():
        return error.strip()[:800]
    return str(payload)[:800]


def build_chat_messages(
    *,
    task: str,
    memory_context: str,
    use_memory: bool,
) -> list[dict[str, str]]:
    if use_memory and memory_context.strip():
        memory_block = memory_context.strip()
    else:
        memory_block = "（本回合未注入记忆）"

    system = (
        "你是带可选长期记忆的助手。记忆可能过时或不完整；无关则忽略。\n\n"
        f"{memory_block}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": task},
    ]


class OpenAICompatChatLLM:
    def __init__(self, *, provider: str, api_key: str, base_url: str, model: str):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete(self, messages: list[dict[str, str]]) -> ChatResult:
        url = f"{self.base_url}/chat/completions"
        started = time.perf_counter()
        with span("llm.complete"):
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=build_chat_request_body(model=self.model, messages=messages),
                )
                if response.is_error:
                    detail = http_error_detail(response)
                    emit(
                        "llm.http_error",
                        provider=self.provider,
                        model=self.model,
                        status=response.status_code,
                        error=detail,
                    )
                    raise ChatLLMError(
                        f"{response.status_code} {self.provider}/{self.model}: {detail}"
                    )
                body = response.json()

        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        choice = (body.get("choices") or [{}])[0]
        text = ((choice.get("message") or {}).get("content")) or ""
        result = ChatResult(
            text=text,
            elapsed_ms=elapsed_ms,
            usage=body.get("usage"),
            finish_reason=choice.get("finish_reason"),
        )
        emit(
            "llm.transport",
            provider=self.provider,
            model=self.model,
            elapsed_ms=elapsed_ms,
            finish_reason=result.finish_reason,
            usage=result.usage,
        )
        return result


def build_chat_llm(settings: Settings) -> OpenAICompatChatLLM:
    provider = (settings.llm_provider or "deepseek").strip().lower()
    if provider not in _PROVIDER_DEFAULTS:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    default_base, default_model = _PROVIDER_DEFAULTS[provider]
    api_key = settings.llm_api_key.strip()
    if not api_key:
        raise ValueError("LLM_API_KEY is required for the CLI")

    return OpenAICompatChatLLM(
        provider=provider,
        api_key=api_key,
        base_url=(settings.llm_base_url or default_base).strip(),
        model=(settings.llm_model or default_model).strip(),
    )
