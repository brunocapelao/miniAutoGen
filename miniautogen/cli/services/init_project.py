"""Scaffold a new MiniAutoGen project."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_VALID_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")

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
    ".gitignore.j2": ".gitignore",
}

# Directories to create even if no template fills them
_EXTRA_DIRS: list[str] = ["mcp"]

# Nested directories to create (as subdirs within project)
_NESTED_DIRS: dict[str, list[str]] = {
    ".miniautogen/agents": [],
    ".miniautogen/shared": ["memory", "workspace"],
}

# Valid template names for the new template system
_VALID_TEMPLATES = ("quickstart", "minimal", "advanced")

# Root of all templates
_TEMPLATES_ROOT = Path(__file__).parent.parent / "templates"

# Root of examples directory
_EXAMPLES_DIR = Path(__file__).parent.parent.parent.parent / "examples"


def _discover_template_files(template_dir: Path) -> dict[str, str]:
    """Walk a template directory and build a map of .j2 files to output names.

    Returns a dict mapping template-relative paths (e.g. ``agents/assistant.yaml.j2``)
    to output-relative paths (e.g. ``agents/assistant.yaml``).
    """
    mapping: dict[str, str] = {}
    for path in sorted(template_dir.rglob("*.j2")):
        rel = path.relative_to(template_dir)
        # Strip .j2 suffix for the output name
        output_name = str(rel)[: -len(".j2")]
        mapping[str(rel)] = output_name
    return mapping


def scaffold_project(
    name: str,
    target_dir: Path,
    *,
    model: str = "gpt-4o-mini",
    provider: str = "openai",
    include_examples: bool = True,
    force: bool = False,
    template: str = "project",
    from_example: str | None = None,
) -> Path:
    """Create a new MiniAutoGen project with canonical structure.

    Args:
        name: Project name.
        target_dir: Parent directory where project folder is created.
        model: Default LLM model.
        provider: Default LLM provider.
        include_examples: If False, skip example agent/skill/tool
            (only for legacy ``project`` template).
        force: If True and directory exists, add only missing files
               without overwriting existing ones.
        template: Template variant to use. One of ``quickstart``,
            ``minimal``, or ``advanced``.
        from_example: If provided, copy files from
            ``examples/<from_example>/`` instead of using a template.

    Returns:
        Path to the created project directory.

    Raises:
        FileExistsError: If the project directory already exists
            and force is False.
        ValueError: If the project name, template, or example is invalid.
    """
    if not name or not _VALID_NAME.match(name):
        msg = (
            f"Invalid project name '{name}': must start with a letter "
            "and contain only letters, digits, hyphens, or underscores."
        )
        raise ValueError(msg)

    # Validate from_example
    if from_example is not None:
        return _scaffold_from_example(
            name, target_dir, from_example=from_example, force=force,
        )

    # Use new template system for quickstart/minimal/advanced
    if template in _VALID_TEMPLATES:
        return _scaffold_from_template(
            name, target_dir,
            template=template, model=model, provider=provider, force=force,
        )

    # Legacy "project" template (backward compatibility)
    return _scaffold_legacy(
        name, target_dir,
        model=model, provider=provider,
        include_examples=include_examples, force=force,
    )


def _scaffold_from_template(
    name: str,
    target_dir: Path,
    *,
    template: str,
    model: str,
    provider: str,
    force: bool,
) -> Path:
    """Scaffold a project from a named template directory."""
    template_dir = _TEMPLATES_ROOT / template
    if not template_dir.is_dir():
        msg = f"Template '{template}' not found at {template_dir}"
        raise ValueError(msg)

    project_dir = _prepare_project_dir(target_dir / name, force=force)
    created_new = not (target_dir / name).exists() or project_dir == target_dir / name

    try:
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            keep_trailing_newline=True,
            autoescape=False,
        )

        context = {
            "project_name": name,
            "model": model,
            "provider": provider,
        }

        template_map = _discover_template_files(template_dir)
        for template_name, output_name in template_map.items():
            output_path = project_dir / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if force and output_path.exists():
                continue

            tmpl = env.get_template(template_name)
            content = tmpl.render(**context)
            output_path.write_text(content)
    except Exception:
        if created_new and project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)
        raise

    return project_dir


def _scaffold_from_example(
    name: str,
    target_dir: Path,
    *,
    from_example: str,
    force: bool,
) -> Path:
    """Scaffold a project by copying from an examples directory."""
    example_dir = _EXAMPLES_DIR / from_example
    if not example_dir.is_dir():
        msg = f"Example '{from_example}' not found at {example_dir}"
        raise ValueError(msg)

    project_dir = _prepare_project_dir(target_dir / name, force=force)
    created_new = not (target_dir / name).exists() or project_dir == target_dir / name

    try:
        for src_path in sorted(example_dir.rglob("*")):
            if src_path.is_dir():
                continue
            rel = src_path.relative_to(example_dir)
            dest = project_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)

            if force and dest.exists():
                continue

            shutil.copy2(src_path, dest)
    except Exception:
        if created_new and project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)
        raise

    return project_dir


def _prepare_project_dir(project_dir: Path, *, force: bool) -> Path:
    """Create or validate the project directory."""
    if project_dir.exists() and not force:
        if any(project_dir.iterdir()):
            msg = f"Directory already exists and is not empty: {project_dir}"
            raise FileExistsError(msg)
    elif not project_dir.exists():
        project_dir.mkdir(parents=True)
    return project_dir


def _scaffold_legacy(
    name: str,
    target_dir: Path,
    *,
    model: str,
    provider: str,
    include_examples: bool,
    force: bool,
) -> Path:
    """Original scaffold logic using the ``project`` template directory."""
    project_dir = target_dir / name

    created_new = not project_dir.exists()

    if project_dir.exists() and not force:
        # Check if directory is non-empty
        if any(project_dir.iterdir()):
            msg = f"Directory already exists and is not empty: {project_dir}"
            raise FileExistsError(msg)
        # Empty directory is fine — proceed
    elif not project_dir.exists():
        project_dir.mkdir(parents=True)
    try:
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            keep_trailing_newline=True,
            autoescape=False,
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

            # With --force, never overwrite existing files
            if force and output_path.exists():
                continue

            template = env.get_template(template_name)
            content = template.render(**context)
            output_path.write_text(content)

        # Create extra directories
        for d in _EXTRA_DIRS:
            (project_dir / d).mkdir(parents=True, exist_ok=True)

        # Create nested directory structures
        for base_dir, subdirs in _NESTED_DIRS.items():
            base_path = project_dir / base_dir
            base_path.mkdir(parents=True, exist_ok=True)
            for subdir in subdirs:
                (base_path / subdir).mkdir(parents=True, exist_ok=True)
    except Exception:
        if created_new:
            shutil.rmtree(project_dir, ignore_errors=True)
        raise

    return project_dir
