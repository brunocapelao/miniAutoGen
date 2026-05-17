"""Architectural test: verify no adapter/SDK imports in mailbox modules.

Enforces Constraint #2 (Isolamento de Adapters) and Constraint #6
(AgentRuntime untouched) from Spec 017.
"""

from pathlib import Path

FORBIDDEN_IMPORTS = [
    "litellm",
    "google.generativeai",
    "openai",
    "jinja",
    "sqlalchemy",
    "httpx",
]

TARGET_MODULES = [
    "miniautogen/core/runtime/team_mailbox.py",
    "miniautogen/core/runtime/team_plan_approval.py",
    "miniautogen/core/runtime/approval_gated_tool_registry.py",
    "miniautogen/core/runtime/builtin_team_tools.py",
]

AGENT_RUNTIME_PATH = "miniautogen/core/runtime/agent_runtime.py"
FORBIDDEN_PATTERNS_IN_AGENT_RUNTIME = [
    "plan_approval",
    "MailboxStore",
    "MailMessage",
    "TeamHook",
    "team_mailbox",
    "builtin_team_tools",
    "PlanApprovalRegistry",
    "ApprovalGatedToolRegistry",
]


def _module_text(module_path: str) -> str:
    full = Path(__file__).resolve().parent.parent.parent / module_path
    if not full.exists():
        return ""
    return full.read_text()


def test_no_adapter_imports_in_mailbox_modules() -> None:
    for mod in TARGET_MODULES:
        text = _module_text(mod)
        if not text:
            continue
        for forbidden in FORBIDDEN_IMPORTS:
            assert forbidden not in text, (
                f"{mod} must not import {forbidden}"
            )


def test_agent_runtime_untouched() -> None:
    text = _module_text(AGENT_RUNTIME_PATH)
    if not text:
        return
    for pattern in FORBIDDEN_PATTERNS_IN_AGENT_RUNTIME:
        assert pattern not in text, (
            f"agent_runtime.py must not reference {pattern}"
        )
