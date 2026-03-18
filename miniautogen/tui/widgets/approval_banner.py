"""Inline HITL approval banner for the interaction log.

Appears inline in the conversation flow (not as a blocking modal).
Shows action description with [A]pprove / [D]eny key bindings.
Double border styling to stand out visually.
"""

from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Static


class ApprovalDecision(Message):
    """Message posted when the user makes an approval decision."""

    def __init__(
        self,
        request_id: str,
        decision: Literal["approved", "denied"],
        reason: str | None = None,
    ) -> None:
        super().__init__()
        self.request_id = request_id
        self.decision = decision
        self.reason = reason


class ApprovalBanner(Widget):
    """Inline approval request in the conversation flow.

    Renders a double-border banner with the action description
    and [A]pprove / [D]eny buttons. Shows files affected if provided.
    """

    DEFAULT_CSS = """
    ApprovalBanner {
        height: auto;
        margin: 1 2;
        padding: 1 2;
        border: double $warning;
        background: $surface;
    }

    ApprovalBanner .approval-title {
        text-style: bold;
        color: $warning;
    }

    ApprovalBanner .approval-description {
        margin: 1 0;
    }

    ApprovalBanner .approval-files {
        margin: 0 0 1 2;
        color: $text-muted;
    }

    ApprovalBanner .approval-buttons {
        height: 3;
    }

    ApprovalBanner Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        request_id: str,
        action: str,
        description: str,
        files_affected: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.request_id = request_id
        self.action = action
        self.description = description
        self.files_affected = files_affected or []

    def compose(self) -> ComposeResult:
        yield Static(
            "\u231b Approval Required",
            classes="approval-title",
        )
        yield Static(
            f"{self.description}\n[dim]Action: {self.action}[/dim]",
            classes="approval-description",
        )
        if self.files_affected:
            files_str = "\n".join(
                f"  \u2022 {f}" for f in self.files_affected
            )
            yield Static(
                f"[dim]Files affected:[/dim]\n{files_str}",
                classes="approval-files",
            )
        with Horizontal(classes="approval-buttons"):
            yield Button("[A]pprove", variant="success", id="approve-btn")
            yield Button("[D]eny", variant="error", id="deny-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle approve/deny button presses."""
        if event.button.id == "approve-btn":
            self.post_message(
                ApprovalDecision(
                    request_id=self.request_id,
                    decision="approved",
                )
            )
        elif event.button.id == "deny-btn":
            self.post_message(
                ApprovalDecision(
                    request_id=self.request_id,
                    decision="denied",
                )
            )

    def key_a(self) -> None:
        """Keyboard shortcut for approve."""
        self.post_message(
            ApprovalDecision(
                request_id=self.request_id,
                decision="approved",
            )
        )

    def key_d(self) -> None:
        """Keyboard shortcut for deny."""
        self.post_message(
            ApprovalDecision(
                request_id=self.request_id,
                decision="denied",
            )
        )
