from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """Stable adapter contract for provider-backed LLM calls."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: list[dict[str, str]],
        model_name: Optional[str] = None,
        temperature: float = 1.0,
    ) -> str:
        """Return a text completion for the prompt."""
