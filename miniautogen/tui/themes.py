"""Theme definitions for MiniAutoGen Dash.

Uses semantic color tokens for consistent theming across widgets.
4 built-in themes: tokyo-night (default dark), catppuccin, monokai, light.

Each DashTheme is converted to a Textual ``Theme`` via ``to_textual_theme()``
so that ``app.theme = name`` triggers the built-in CSS variable refresh.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.theme import Theme as TextualTheme


@dataclass(frozen=True)
class DashTheme:
    """Theme definition with semantic color tokens."""

    name: str
    dark: bool = True
    primary: str = "#7aa2f7"
    secondary: str = "#bb9af7"
    accent: str = "#7dcfff"
    background: str = "#1a1b26"
    surface: str = "#24283b"
    text: str = "#c0caf5"
    text_muted: str = "#565f89"
    status_active: str = "#9ece6a"
    status_done: str = "#73daca"
    status_working: str = "#e0af68"
    status_waiting: str = "#ff9e64"
    status_failed: str = "#f7768e"
    status_cancelled: str = "#db4b4b"

    def to_textual_theme(self) -> TextualTheme:
        """Convert to a Textual Theme for CSS variable injection."""
        return TextualTheme(
            name=self.name,
            primary=self.primary,
            secondary=self.secondary,
            accent=self.accent,
            background=self.background,
            surface=self.surface,
            foreground=self.text,
            dark=self.dark,
            variables={
                "text-muted": self.text_muted,
                "status-active": self.status_active,
                "status-done": self.status_done,
                "status-working": self.status_working,
                "status-waiting": self.status_waiting,
                "status-failed": self.status_failed,
                "status-cancelled": self.status_cancelled,
            },
        )


_TOKYO_NIGHT = DashTheme(name="tokyo-night")

_CATPPUCCIN = DashTheme(
    name="catppuccin",
    primary="#89b4fa",
    secondary="#cba6f7",
    accent="#89dceb",
    background="#1e1e2e",
    surface="#313244",
    text="#cdd6f4",
    text_muted="#6c7086",
    status_active="#a6e3a1",
    status_done="#94e2d5",
    status_working="#f9e2af",
    status_waiting="#fab387",
    status_failed="#f38ba8",
    status_cancelled="#eba0ac",
)

_MONOKAI = DashTheme(
    name="monokai",
    primary="#66d9ef",
    secondary="#ae81ff",
    accent="#a6e22e",
    background="#272822",
    surface="#3e3d32",
    text="#f8f8f2",
    text_muted="#75715e",
    status_active="#a6e22e",
    status_done="#66d9ef",
    status_working="#e6db74",
    status_waiting="#fd971f",
    status_failed="#f92672",
    status_cancelled="#cc6633",
)

_LIGHT = DashTheme(
    name="light",
    dark=False,
    primary="#4078f2",
    secondary="#a626a4",
    accent="#0184bc",
    background="#fafafa",
    surface="#f0f0f0",
    text="#383a42",
    text_muted="#a0a1a7",
    status_active="#50a14f",
    status_done="#0184bc",
    status_working="#c18401",
    status_waiting="#e45649",
    status_failed="#e45649",
    status_cancelled="#986801",
)

THEMES: dict[str, DashTheme] = {
    "tokyo-night": _TOKYO_NIGHT,
    "catppuccin": _CATPPUCCIN,
    "monokai": _MONOKAI,
    "light": _LIGHT,
}


DEFAULT_THEME = "tokyo-night"


def get_theme(name: str) -> DashTheme:
    """Get a theme by name. Falls back to tokyo-night."""
    return THEMES.get(name, _TOKYO_NIGHT)


def register_dash_themes(app: object) -> None:
    """Register all DashThemes as Textual themes on *app*.

    Call this once during ``App.__init__`` or ``on_mount``.
    """
    register = getattr(app, "register_theme", None)
    if register is None:
        return
    for dash_theme in THEMES.values():
        register(dash_theme.to_textual_theme())
