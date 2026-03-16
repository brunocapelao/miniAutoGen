from gemini_cli_gateway.models import ChatMessage
from gemini_cli_gateway.prompt_builder import build_prompt


def test_build_prompt_preserves_roles_in_order() -> None:
    prompt = build_prompt(
        [
            ChatMessage(role="system", content="Be concise."),
            ChatMessage(role="user", content="Explain the runtime."),
        ]
    )
    assert "SYSTEM\nBe concise." in prompt
    assert "USER\nExplain the runtime." in prompt



def test_build_prompt_preserves_quoted_and_multiline_content() -> None:
    prompt = build_prompt(
        [
            ChatMessage(role="system", content='Say "hello".'),
            ChatMessage(role="user", content="Line 1\nLine 2\nLine 3"),
        ]
    )
    assert 'SYSTEM\nSay "hello".' in prompt
    assert "USER\nLine 1\nLine 2\nLine 3" in prompt
