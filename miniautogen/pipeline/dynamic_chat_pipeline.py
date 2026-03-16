from __future__ import annotations

from dataclasses import dataclass

from miniautogen.core.contracts.agentic_loop import ConversationPolicy


@dataclass
class DynamicChatPipeline:
    router_agent: str
    agent_registry: dict[str, object]
    policy: ConversationPolicy
