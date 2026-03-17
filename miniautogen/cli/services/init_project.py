"""Scaffold a new MiniAutoGen project."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "project"

# Map of template file -> output file (relative to project root)
_TEMPLATE_MAP: dict[str, str] = {
    "miniautogen.yaml.j2": "miniautogen.yaml",
    "agents/researcher.yaml.j2": "agents/researcher.yaml",
    "skills/example/SKILL.md.j2": "skills/example/SKILL.md",
    "skills/example/skill.yaml.j2": "skills/example/skill.yaml",
    "tools/web_search.yaml.j2": "tools/web_search.yaml",
    "memory/profiles.yaml.j2": "memory/profiles.yaml",
    "pipelines/main.py.j2": "pipelines/main.py",
    ".env.j2": ".env",
}

# Directories to create even if no template fills them
_EXTRA_DIRS: list[str] = ["mcp"]


async def scaffold_project(
    name: str,
    target_dir: Path,
    *,
    model: str = "gpt-4o-mini",
    provider: str = "litellm",
    include_examples: bool = True,
) -> Path:
    """Create a new MiniAutoGen project with canonical structure.

    Args:
        name: Project name.
        target_dir: Parent directory where project folder is created.
        model: Default LLM model.
        provider: Default LLM provider.
        include_examples: If False, skip example agent/skill/tool.

    Returns:
        Path to the created project directory.

    Raises:
        FileExistsError: If the project directory already exists.
    """
    project_dir = target_dir / name
    if project_dir.exists():
        msg = f"Directory already exists: {project_dir}"
        raise FileExistsError(msg)

    project_dir.mkdir(parents=True)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        keep_trailing_newline=True,
    )

    context = {
        "project_name": name,
        "model": model,
        "provider": provider,
    }

    templates_to_render = dict(_TEMPLATE_MAP)
    if not include_examples:
        # Remove example files but keep config and pipeline
        example_keys = [
            k
            for k in templates_to_render
            if "researcher" in k or "example" in k or "web_search" in k
        ]
        for k in example_keys:
            del templates_to_render[k]

    for template_name, output_name in templates_to_render.items():
        output_path = project_dir / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)

        template = env.get_template(template_name)
        content = template.render(**context)
        output_path.write_text(content)

    # Create extra directories
    for d in _EXTRA_DIRS:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    return project_dir
