from gemini_cli_gateway.models import ChatMessage


def build_prompt(messages: list[ChatMessage]) -> str:
    blocks: list[str] = []
    for message in messages:
        blocks.append(f"{message.role.upper()}\n{message.content}")
    return "\n\n".join(blocks)
