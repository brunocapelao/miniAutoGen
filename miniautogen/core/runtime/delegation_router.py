"""Config-driven delegation router."""
from __future__ import annotations

from typing import Any

from miniautogen.core.runtime.agent_errors import (
    AgentSecurityError, DelegationDepthExceededError,
)


class ConfigDelegationRouter:
    """Routes delegation based on YAML config allowlists and depth limits."""

    def __init__(self, configs: dict[str, dict[str, Any]]) -> None:
        self._configs = configs
        self._agents: dict[str, Any] = {}
        self._active_chains: set[tuple[str, str]] = set()

    def register_agent(self, agent_id: str, agent: Any) -> None:
        self._agents[agent_id] = agent

    def can_delegate(self, from_agent: str, to_agent: str) -> bool:
        config = self._configs.get(from_agent)
        if config is None:
            return False
        return to_agent in config.get("can_delegate_to", [])

    async def delegate(
        self,
        from_agent: str,
        to_agent: str,
        input_data: Any,
        current_depth: int = 0,
    ) -> Any:
        if not self.can_delegate(from_agent, to_agent):
            msg = f"Delegation not allowed: {from_agent} -> {to_agent}"
            raise AgentSecurityError(msg)

        config = self._configs.get(from_agent, {})
        max_depth = config.get("max_depth", 1)
        if current_depth >= max_depth:
            msg = f"Agent '{from_agent}' exceeded max delegation depth {max_depth}"
            raise DelegationDepthExceededError(msg)

        chain = (from_agent, to_agent)
        if chain in self._active_chains:
            msg = f"Circular delegation detected: {from_agent} -> {to_agent}"
            raise DelegationDepthExceededError(msg)

        target = self._agents.get(to_agent)
        if target is None:
            msg = f"Delegation target '{to_agent}' not found"
            raise AgentSecurityError(msg)

        self._active_chains.add(chain)
        try:
            return await target.process(input_data)
        finally:
            self._active_chains.discard(chain)
