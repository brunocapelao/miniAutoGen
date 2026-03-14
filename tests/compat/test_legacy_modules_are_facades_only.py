from pathlib import Path

from miniautogen.llms.llm_client import LiteLLMClient, OpenAIClient
from miniautogen.storage.in_memory_repository import InMemoryChatRepository
from miniautogen.storage.repository import ChatRepository
from miniautogen.storage.sql_repository import SQLAlchemyAsyncRepository


def test_legacy_modules_remain_importable() -> None:
    assert ChatRepository is not None
    assert InMemoryChatRepository is not None
    assert SQLAlchemyAsyncRepository is not None
    assert OpenAIClient is not None
    assert LiteLLMClient is not None


def test_runtime_packages_do_not_import_legacy_modules() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source_root = project_root / "miniautogen"

    checked_files = 0
    for path in source_root.rglob("*.py"):
        relative = path.relative_to(source_root)
        if relative.parts[0] in {"llms", "storage"}:
            continue

        contents = path.read_text()
        assert "from miniautogen.storage" not in contents
        assert "import miniautogen.storage" not in contents
        assert "from miniautogen.llms" not in contents
        assert "import miniautogen.llms" not in contents
        checked_files += 1

    assert checked_files > 0
