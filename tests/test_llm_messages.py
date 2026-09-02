from app.adapters.llm import (
    build_chat_messages,
    build_chat_request_body,
    http_error_detail,
    uses_fixed_sampling,
)


def test_messages_include_memory_when_enabled():
    messages = build_chat_messages(
        task="之前 Planner 为什么失败？",
        memory_context="Relevant historical memory:\n1. [reflection] 缺 Research",
        use_memory=True,
    )
    assert messages[0]["role"] == "system"
    assert "缺 Research" in messages[0]["content"]
    assert messages[1]["content"] == "之前 Planner 为什么失败？"


def test_messages_omit_memory_when_disabled():
    messages = build_chat_messages(
        task="1 + 1 等于多少",
        memory_context="should not appear",
        use_memory=False,
    )
    assert "should not appear" not in messages[0]["content"]
    assert "未注入记忆" in messages[0]["content"]


def test_kimi_k3_omits_temperature():
    assert uses_fixed_sampling("kimi-k3")
    body = build_chat_request_body(
        model="kimi-k3",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert "temperature" not in body
    assert body["model"] == "kimi-k3"


def test_deepseek_includes_temperature():
    body = build_chat_request_body(
        model="deepseek-chat",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert body["temperature"] == 0.3


def test_http_error_detail_reads_moonshot_message():
    class _Resp:
        def json(self):
            return {
                "error": {
                    "message": "invalid temperature: only 1 is allowed for this model"
                }
            }

        text = ""

    assert "invalid temperature" in http_error_detail(_Resp())  # type: ignore[arg-type]
