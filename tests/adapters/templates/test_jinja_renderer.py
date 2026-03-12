from miniautogen.adapters.templates import JinjaTemplateRenderer


def test_jinja_template_renderer_renders_mapping() -> None:
    renderer = JinjaTemplateRenderer()

    result = renderer.render(
        "Hello {{ name }}. You have {{ count }} messages.",
        {"name": "MiniAutoGen", "count": 3},
    )

    assert result == "Hello MiniAutoGen. You have 3 messages."
