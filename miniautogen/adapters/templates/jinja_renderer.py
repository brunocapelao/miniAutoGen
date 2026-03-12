from typing import Any

from jinja2 import Environment, select_autoescape

from miniautogen.adapters.templates.protocol import TemplateRenderer


class JinjaTemplateRenderer(TemplateRenderer):
    """Jinja-backed template adapter with a reusable environment."""

    def __init__(self, environment: Environment | None = None):
        self.environment = environment or Environment(
            autoescape=select_autoescape(),
        )

    def render(self, template_str: str, variables: dict[str, Any]) -> str:
        template = self.environment.from_string(template_str)
        return template.render(variables)
