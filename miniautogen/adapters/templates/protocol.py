from abc import ABC, abstractmethod
from typing import Any


class TemplateRenderer(ABC):
    """Contract for prompt and text template rendering adapters."""

    @abstractmethod
    def render(self, template_str: str, variables: dict[str, Any]) -> str:
        """Render the given template string with the provided variables."""
