from gemini_cli_gateway.models import ChatCompletionRequest


def test_chat_completion_request_accepts_minimal_payload() -> None:
    payload = ChatCompletionRequest(
        model="gemini-2.5-pro",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.2,
    )
    assert payload.model == "gemini-2.5-pro"
    assert payload.messages[0].content == "hello"
