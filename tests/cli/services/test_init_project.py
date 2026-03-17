"""Tests for init_project service."""

import pytest

from miniautogen.cli.services.init_project import scaffold_project


@pytest.mark.anyio
async def test_scaffold_creates_directory(tmp_path) -> None:
    result = await scaffold_project("myproject", tmp_path)
    assert result.exists()
    assert result.name == "myproject"


@pytest.mark.anyio
async def test_scaffold_creates_config(tmp_path) -> None:
    result = await scaffold_project("myproject", tmp_path)
    config = result / "miniautogen.yaml"
    assert config.is_file()
    content = config.read_text()
    assert "myproject" in content
    assert "memory_profiles" in content
    assert "engine_profiles" in content


@pytest.mark.anyio
async def test_scaffold_creates_full_structure(tmp_path) -> None:
    result = await scaffold_project("myproject", tmp_path)
    assert (result / "agents" / "researcher.yaml").is_file()
    assert (result / "skills" / "example" / "SKILL.md").is_file()
    assert (result / "skills" / "example" / "skill.yaml").is_file()
    assert (result / "tools" / "web_search.yaml").is_file()
    assert (result / "memory" / "profiles.yaml").is_file()
    assert (result / "pipelines" / "main.py").is_file()
    assert (result / ".env").is_file()
    assert (result / "mcp").is_dir()


@pytest.mark.anyio
async def test_scaffold_no_examples(tmp_path) -> None:
    result = await scaffold_project(
        "myproject",
        tmp_path,
        include_examples=False,
    )
    assert (result / "miniautogen.yaml").is_file()
    assert (result / "pipelines" / "main.py").is_file()
    assert not (result / "agents" / "researcher.yaml").exists()
    assert not (result / "skills" / "example").exists()
    assert not (result / "tools" / "web_search.yaml").exists()


@pytest.mark.anyio
async def test_scaffold_custom_model_provider(tmp_path) -> None:
    result = await scaffold_project(
        "myproject",
        tmp_path,
        model="gemini-2.5-pro",
        provider="gemini",
    )
    content = (result / "miniautogen.yaml").read_text()
    assert "gemini-2.5-pro" in content
    assert "gemini" in content


@pytest.mark.anyio
async def test_scaffold_creates_gitignore(tmp_path) -> None:
    result = await scaffold_project("myproject", tmp_path)
    assert (result / ".gitignore").is_file()


@pytest.mark.anyio
async def test_scaffold_fails_if_exists(tmp_path) -> None:
    (tmp_path / "myproject").mkdir()
    with pytest.raises(FileExistsError):
        await scaffold_project("myproject", tmp_path)


@pytest.mark.anyio
async def test_scaffold_rejects_invalid_name(tmp_path) -> None:
    with pytest.raises(ValueError, match="Invalid project name"):
        await scaffold_project("my: project", tmp_path)


@pytest.mark.anyio
async def test_scaffold_rejects_path_traversal(tmp_path) -> None:
    with pytest.raises(ValueError, match="Invalid project name"):
        await scaffold_project("../evil", tmp_path)


@pytest.mark.anyio
async def test_scaffold_rejects_empty_name(tmp_path) -> None:
    with pytest.raises(ValueError, match="Invalid project name"):
        await scaffold_project("", tmp_path)
