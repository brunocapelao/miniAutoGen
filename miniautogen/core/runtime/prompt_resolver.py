"""Prompt cascade resolver — InteractionStrategy -> YAML templates -> defaults.

Implements the three-level cascade resolution for prompt construction
as defined in the AgentRuntime agnostic design spec.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from miniautogen.core.contracts.interaction import InteractionStrategy

_logger = logging.getLogger(__name__)


class _SafeDict(dict):
    """Dict that returns the key placeholder for missing keys.

    Used with str.format_map() to safely substitute only known variables,
    leaving unknown {placeholders} intact.
    """

    def __missing__(self, key: str) -> str:
        _logger.debug(
            "YAML prompt template references unknown variable: {%s}", key
        )
        return "{" + key + "}"


async def resolve_prompt(
    *,
    action: str,
    context: dict[str, Any],
    strategy: InteractionStrategy | None,
    flow_prompts: dict[str, str],
    default_prompt: str,
) -> str:
    """Resolve prompt using cascade: strategy -> YAML template -> default.

    Args:
        action: The coordination action (contribute, review, consolidate, etc.)
        context: Action-specific context variables for template substitution.
        strategy: Optional InteractionStrategy (highest priority).
        flow_prompts: YAML prompt templates keyed by action name.
        default_prompt: Built-in default prompt (lowest priority fallback).

    Returns:
        The resolved prompt string.
    """
    # Level 1: InteractionStrategy (Python)
    if strategy is not None:
        return await strategy.build_prompt(action, context)

    # Level 2: YAML prompt templates
    if action in flow_prompts:
        template = flow_prompts[action]
        # Sanitize non-string values to prevent attribute traversal
        safe_context = {
            k: str(v) if not isinstance(v, str) else v
            for k, v in context.items()
        }
        # Safe substitution — unknown vars remain as {placeholder}
        return template.format_map(_SafeDict(safe_context))

    # Level 3: Built-in default
    return default_prompt
