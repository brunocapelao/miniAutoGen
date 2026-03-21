# TUI Visual Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Match the TUI's visual quality to the approved mockup — stat cards, styled tabs, section containers, visual hierarchy.

**Architecture:** CSS + compose() changes only. No structural changes — TabBar, MainContent, ExecutionSidebar architecture is correct. Each task modifies one widget's `DEFAULT_CSS` and `compose()` to add visual richness (backgrounds, borders, containers, spacing).

**Tech Stack:** Python 3.11+, Textual CSS, pytest

**Spec:** `docs/superpowers/specs/2026-03-21-tui-redesign-design.md`
**Mockup reference:** User-provided screenshot showing the approved visual identity

**Worktree:** `.worktrees/tui-redesign` (branch `feat/tui-redesign`)

**Visual verification:** After each task, run `cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign && python tests/tui/visual_test.py` to capture SVG screenshots, then inspect the relevant SVG file to verify visual changes.

**Important Textual CSS notes:**
- Textual CSS uses character-based units, not pixels
- `background: $surface;` gives a dark panel background
- `border: solid $primary;` adds visible borders
- `text-style: bold;` for emphasis
- `content-align: center middle;` for centering
- `layout: horizontal;` for side-by-side containers
- `height: auto;` for content-fitting height
- Containers use `Horizontal` and `Vertical` from `textual.containers`
- `Static` widgets render Rich markup (e.g., `[bold]text[/bold]`, `[dim]text[/dim]`)

---

## File Structure

All modifications — no new files:

| File | Changes |
|------|---------|
| `miniautogen/tui/widgets/tab_bar.py` | Richer compose: brand left, tabs center, server status right. Better active tab styling. |
| `miniautogen/tui/content/workspace.py` | Stat cards as Horizontal with 4 bordered containers. Health check in bordered container. Quick actions as styled buttons. |
| `miniautogen/tui/content/flows.py` | Better header with title styling. Styled empty state. |
| `miniautogen/tui/content/agents.py` | Same as flows — header and empty state polish. |
| `miniautogen/tui/content/config.py` | Section containers with backgrounds. Better visual separation between engines/project/server/theme. |
| `miniautogen/tui/widgets/execution_sidebar.py` | Header with status indicator. Better border styling. |
| `miniautogen/tui/widgets/idle_panel.py` | Better section headers. Agent rows with proper spacing. |
| `miniautogen/tui/dash.tcss` | Shared utility classes for stat cards, section containers, action buttons. |

---

## Task 1: Shared CSS Utility Classes

**Files:**
- Modify: `miniautogen/tui/dash.tcss`

- [ ] **Step 1: Add shared utility classes to dash.tcss**

Add these classes at the end of the existing `dash.tcss` file. These will be used by multiple content widgets:

```tcss
/* ── Shared Layout Utilities ────────────── */

/* Stat card row (horizontal container of cards) */
.stat-row {
    layout: horizontal;
    height: auto;
    margin: 0 0 1 0;
}

/* Individual stat card */
.stat-card {
    background: $surface;
    border: round $primary-background;
    padding: 1 2;
    margin: 0 1 0 0;
    width: 1fr;
    height: auto;
    min-height: 5;
}

.stat-card .stat-value {
    text-style: bold;
    color: $text;
}

.stat-card .stat-label {
    color: $text-muted;
}

.stat-card .stat-sub {
    color: $text-muted;
}

/* Section container (bordered box for content groups) */
.section-box {
    background: $surface;
    border: round $primary-background;
    padding: 1 2;
    margin: 0 0 1 0;
    height: auto;
}

/* Section title (uppercase muted label) */
.section-title {
    color: $text-muted;
    text-style: bold;
    margin: 1 0 0 0;
    height: 1;
}

/* Action button row */
.action-row {
    layout: horizontal;
    height: auto;
    margin: 1 0 0 0;
}

/* Individual action button */
.action-btn {
    background: $surface;
    border: tall $primary;
    padding: 0 2;
    margin: 0 1 0 0;
    height: 3;
    content-align: center middle;
    color: $primary;
}

.action-btn:hover {
    background: $primary-background;
}

/* Content view header (title + hints) */
.content-header {
    height: auto;
    padding: 1 2 0 2;
}

.content-title {
    text-style: bold;
    color: $text;
    height: 1;
}

.content-hint {
    color: $text-muted;
    height: 1;
    margin: 0 0 1 0;
}

/* Empty state for CRUD views */
.crud-empty {
    content-align: center middle;
    height: 1fr;
    color: $text-muted;
    text-style: italic;
}
```

- [ ] **Step 2: Verify CSS loads without errors**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen/.worktrees/tui-redesign && python -c "from miniautogen.tui.app import MiniAutoGenDash; print('OK')"`
Expected: "OK" (no CSS parse errors)

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/tui/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```
refactor(tui): add shared CSS utility classes for visual polish
```

---

## Task 2: TabBar Visual Polish

**Files:**
- Modify: `miniautogen/tui/widgets/tab_bar.py`

The mockup shows: `MiniAutoGen  [Workspace] Flows  Agents  Config           ● Server :8080  ?:help`

The active tab has a visible border/background. The brand "MiniAutoGen" is on the left. Server status is on the right.

- [ ] **Step 1: Rewrite TabBar compose() and DEFAULT_CSS**

Replace the entire `tab_bar.py` content with:

```python
"""Tab bar navigation widget for MiniAutoGen Dash."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.messages import TabChanged

_TABS = ["Workspace", "Flows", "Agents", "Config"]


class TabBar(Widget):
    """Horizontal tab bar with brand, 4 tabs, and status indicator.

    Number key bindings (1-4) live on the App, not here,
    because DataTables in content widgets steal focus.
    """

    DEFAULT_CSS = """
    TabBar {
        dock: top;
        height: 3;
        background: $surface;
        layout: horizontal;
        padding: 0 1;
    }
    TabBar #tab-brand {
        width: auto;
        padding: 1 2 1 1;
        color: $primary;
        text-style: bold;
    }
    TabBar #tab-nav {
        width: 1fr;
        height: 3;
        layout: horizontal;
        padding: 1 0;
    }
    TabBar .tab {
        padding: 0 2;
        height: 1;
        color: $text-muted;
    }
    TabBar .tab.--active {
        color: $text;
        text-style: bold;
        background: $primary 15%;
        border-bottom: tall $primary;
    }
    TabBar .tab:hover {
        color: $text;
        background: $primary 10%;
    }
    TabBar #tab-status {
        width: auto;
        padding: 1 1 1 2;
        color: $text-muted;
    }
    """

    active_tab: reactive[str] = reactive("Workspace")

    def __init__(self) -> None:
        super().__init__()
        self._server_status = ""

    @property
    def tab_names(self) -> list[str]:
        return list(_TABS)

    def compose(self) -> ComposeResult:
        yield Static("MiniAutoGen", id="tab-brand")
        with Horizontal(id="tab-nav"):
            for name in _TABS:
                classes = "tab --active" if name == self.active_tab else "tab"
                yield Static(name, classes=classes, id=f"tab-{name.lower()}")
        yield Static("", id="tab-status")

    def watch_active_tab(self, old_value: str, new_value: str) -> None:
        if not self.is_mounted:
            return
        for name in _TABS:
            try:
                tab = self.query_one(f"#tab-{name.lower()}", Static)
                tab.set_classes("tab --active" if name == new_value else "tab")
            except Exception:
                pass
        self.post_message(TabChanged(tab_name=new_value))

    def action_switch_tab(self, tab_name: str) -> None:
        if tab_name in _TABS:
            self.active_tab = tab_name

    def update_server_status(self, status_text: str) -> None:
        """Update the server status indicator on the right."""
        self._server_status = status_text
        try:
            self.query_one("#tab-status", Static).update(status_text)
        except Exception:
            pass
```

- [ ] **Step 2: Update tests for new structure**

The TabBar now has `#tab-brand`, `#tab-nav`, `#tab-status`. Read `tests/tui/widgets/test_tab_bar.py` and update any tests that query old structure. The key tests (active_tab property, tab_names, programmatic switching) should still work since the reactive `active_tab` API is unchanged.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/tui/widgets/test_tab_bar.py -v`
Expected: All pass

- [ ] **Step 4: Run visual test and inspect**

Run: `python tests/tui/visual_test.py`
Then read: `cat /Users/brunocapelao/Projects/miniAutoGen/.superpowers/brainstorm/48862-1774089727/01-workspace.svg | head -5` (verify SVG generated)

- [ ] **Step 5: Commit**

```
refactor(tui): polish TabBar with brand, active indicator, status
```

---

## Task 3: WorkspaceContent Visual Polish

**Files:**
- Modify: `miniautogen/tui/content/workspace.py`

The mockup shows 4 stat cards in a row, a bordered health check section, and styled quick action buttons.

- [ ] **Step 1: Rewrite WorkspaceContent compose() and DEFAULT_CSS**

Replace the entire `workspace.py` content with:

```python
"""Workspace tab: project overview, health check, quick actions."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static


class StatCard(Widget):
    """Single stat display card."""

    DEFAULT_CSS = """
    StatCard {
        background: $surface;
        border: round $primary-background;
        padding: 1 2;
        margin: 0 1 0 0;
        width: 1fr;
        height: 5;
    }
    StatCard .stat-label {
        color: $text-muted;
        height: 1;
    }
    StatCard .stat-value {
        text-style: bold;
        height: 1;
    }
    StatCard .stat-sub {
        color: $text-muted;
        height: 1;
    }
    """

    def __init__(self, label: str, value: str = "0", sub: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._value = value
        self._sub = sub

    def compose(self) -> ComposeResult:
        yield Static(self._label, classes="stat-label")
        yield Static(self._value, classes="stat-value", id=f"val-{self._label.lower()}")
        yield Static(self._sub, classes="stat-sub", id=f"sub-{self._label.lower()}")

    def update_stat(self, value: str, sub: str = "") -> None:
        try:
            self.query_one(f"#val-{self._label.lower()}", Static).update(value)
            if sub:
                self.query_one(f"#sub-{self._label.lower()}", Static).update(sub)
        except Exception:
            pass


class WorkspaceContent(Widget):
    """Home tab showing project overview and health status."""

    DEFAULT_CSS = """
    WorkspaceContent {
        height: 1fr;
        padding: 1 2;
    }
    WorkspaceContent .section-title {
        color: $text-muted;
        text-style: bold;
        margin: 1 0 0 0;
        height: 1;
    }
    WorkspaceContent #stat-row {
        layout: horizontal;
        height: auto;
        margin: 0 0 1 0;
    }
    WorkspaceContent #health-box {
        background: $surface;
        border: round $primary-background;
        padding: 1 2;
        margin: 0 0 1 0;
        height: auto;
    }
    WorkspaceContent #action-row {
        layout: horizontal;
        height: auto;
        margin: 1 0 0 0;
    }
    WorkspaceContent .action-btn {
        background: $surface;
        border: tall $primary;
        padding: 0 2;
        margin: 0 1 0 0;
        height: 3;
        content-align: center middle;
        color: $primary;
    }
    WorkspaceContent .action-btn:hover {
        background: $primary-background;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("PROJECT OVERVIEW", classes="section-title")
        with Horizontal(id="stat-row"):
            yield StatCard("Agents", "0", "—", id="card-agents")
            yield StatCard("Flows", "0", "—", id="card-flows")
            yield StatCard("Engines", "0", "—", id="card-engines")
            yield StatCard("Last Run", "—", "", id="card-lastrun")

        yield Static("HEALTH CHECK", classes="section-title")
        yield Static("Running checks...", id="health-box")

        yield Static("QUICK ACTIONS", classes="section-title")
        with Horizontal(id="action-row"):
            yield Static("[n] New Agent", classes="action-btn")
            yield Static("[r] Run Flow", classes="action-btn")
            yield Static("[:] Commands", classes="action-btn")

    def refresh_data(
        self,
        agents_count: int = 0,
        flows_count: int = 0,
        engines_count: int = 0,
        last_run_status: str = "—",
        health_items: list[tuple[str, str]] | None = None,
    ) -> None:
        """Update the workspace with fresh data."""
        try:
            self.query_one("#card-agents", StatCard).update_stat(
                str(agents_count), "all ready" if agents_count > 0 else "—"
            )
            self.query_one("#card-flows", StatCard).update_stat(str(flows_count))
            self.query_one("#card-engines", StatCard).update_stat(str(engines_count))
            self.query_one("#card-lastrun", StatCard).update_stat(last_run_status)
        except Exception:
            pass

        if health_items:
            lines = [f"{symbol} {text}" for symbol, text in health_items]
            try:
                self.query_one("#health-box", Static).update("\n".join(lines))
            except Exception:
                pass
```

- [ ] **Step 2: Update tests**

Read `tests/tui/content/test_workspace.py`. The tests check for `#overview-section` and `#health-section` which no longer exist. Update:
- `#overview-section` → `#stat-row` (or `#card-agents`)
- `#health-section` → `#health-box`

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/tui/content/test_workspace.py -v`
Expected: All pass

- [ ] **Step 4: Run visual test and inspect workspace screenshot**

Run: `python tests/tui/visual_test.py`

- [ ] **Step 5: Commit**

```
refactor(tui): polish WorkspaceContent with stat cards and styled sections
```

---

## Task 4: ExecutionSidebar + IdlePanel Visual Polish

**Files:**
- Modify: `miniautogen/tui/widgets/execution_sidebar.py`
- Modify: `miniautogen/tui/widgets/idle_panel.py`

The mockup shows a clear "Execution" header with status indicator, well-separated sections in the idle panel.

- [ ] **Step 1: Update ExecutionSidebar DEFAULT_CSS and compose()**

Update the `DEFAULT_CSS` for better visual treatment:

```python
DEFAULT_CSS = """
ExecutionSidebar {
    dock: right;
    width: 35;
    background: $surface;
    border-left: tall $primary-background;
}
ExecutionSidebar #sidebar-header {
    height: 1;
    padding: 0 1;
    background: $primary 15%;
    layout: horizontal;
}
ExecutionSidebar #sidebar-title {
    width: 1fr;
    color: $primary;
    text-style: bold;
}
ExecutionSidebar #sidebar-status {
    width: auto;
    color: $text-muted;
}
"""
```

Update `compose()`:
```python
def compose(self) -> ComposeResult:
    with Horizontal(id="sidebar-header"):
        yield Static("Execution", id="sidebar-title")
        yield Static("idle", id="sidebar-status")
    yield IdlePanel()
    yield self.interaction_log
```

Update `watch_is_executing()` to update `#sidebar-status`:
```python
title.update("Execution Log")
status = self.query_one("#sidebar-status", Static)
status.update("[green]● live[/green]" if value else "idle")
```

- [ ] **Step 2: Update IdlePanel DEFAULT_CSS**

```python
DEFAULT_CSS = """
IdlePanel {
    height: 1fr;
    padding: 1;
}
IdlePanel .section-label {
    color: $text-muted;
    text-style: bold;
    margin: 1 0 0 0;
    height: 1;
}
IdlePanel .agent-entry {
    height: 1;
    layout: horizontal;
}
IdlePanel .separator {
    height: 1;
    margin: 1 0;
    color: $primary-background;
}
"""
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/tui/widgets/test_execution_sidebar.py tests/tui/widgets/test_idle_panel.py -v`
Expected: All pass. If tests query old `#sidebar-title` as the only child, update them.

- [ ] **Step 4: Run visual test**

Run: `python tests/tui/visual_test.py`

- [ ] **Step 5: Commit**

```
refactor(tui): polish ExecutionSidebar and IdlePanel styling
```

---

## Task 5: FlowsContent + AgentsContent Visual Polish

**Files:**
- Modify: `miniautogen/tui/content/flows.py`
- Modify: `miniautogen/tui/content/agents.py`

Both follow the same pattern: styled header + DataTable + styled empty state.

- [ ] **Step 1: Update FlowsContent DEFAULT_CSS**

Replace the current `DEFAULT_CSS` with better visual treatment:

```python
DEFAULT_CSS = """
FlowsContent {
    height: 1fr;
}
FlowsContent .content-header {
    height: auto;
    padding: 1 2 0 2;
}
FlowsContent .content-title {
    text-style: bold;
    color: $text;
    height: 1;
}
FlowsContent .content-hint {
    color: $text-muted;
    height: 1;
    margin: 0 0 1 0;
}
FlowsContent DataTable {
    height: 1fr;
    width: 1fr;
    margin: 0 2;
}
FlowsContent .crud-empty {
    content-align: center middle;
    height: 1fr;
    color: $text-muted;
    text-style: italic;
    padding: 4;
}
"""
```

Update `compose()` to wrap title+hint in a container:

```python
def compose(self) -> ComposeResult:
    with Vertical(classes="content-header"):
        yield Static("Flows", classes="content-title")
        yield Static(
            "Keys: [bold]n[/bold] new  [bold]e[/bold] edit  [bold]x[/bold] delete  [bold]r[/bold] run  [bold]F5[/bold] refresh",
            classes="content-hint",
        )
    table = DataTable(id="flows-table")
    table.add_columns("Name", "Mode", "Agents", "Status")
    yield table
    yield Static(
        "No flows defined.\nPress [bold]n[/bold] to create one.",
        id="flows-empty",
        classes="crud-empty",
    )
```

Add import for `Vertical`:
```python
from textual.containers import Vertical
```

- [ ] **Step 2: Apply same changes to AgentsContent**

Same pattern — update `DEFAULT_CSS` and `compose()` with `Vertical` header container, Rich markup in hint text, styled empty state.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/tui/content/test_flows.py tests/tui/content/test_agents.py -v`
Expected: All pass

- [ ] **Step 4: Run visual test**

Run: `python tests/tui/visual_test.py`

- [ ] **Step 5: Commit**

```
refactor(tui): polish FlowsContent and AgentsContent styling
```

---

## Task 6: ConfigContent Visual Polish

**Files:**
- Modify: `miniautogen/tui/content/config.py`

The mockup shows 4 distinct sections (ENGINES, PROJECT, SERVER, THEME) with visual separation.

- [ ] **Step 1: Update ConfigContent DEFAULT_CSS and compose()**

Update `DEFAULT_CSS`:

```python
DEFAULT_CSS = """
ConfigContent {
    height: 1fr;
    padding: 1 2;
}
ConfigContent .section-title {
    color: $text-muted;
    text-style: bold;
    margin: 1 0 0 0;
    height: 1;
}
ConfigContent .content-hint {
    color: $text-muted;
    height: 1;
    margin: 0 0 1 0;
}
ConfigContent DataTable {
    height: auto;
    max-height: 40%;
    width: 1fr;
    margin: 0 0 1 0;
}
ConfigContent .config-box {
    background: $surface;
    border: round $primary-background;
    padding: 1 2;
    margin: 0 0 1 0;
    height: auto;
}
ConfigContent .server-controls {
    layout: horizontal;
    height: auto;
    margin: 0 0 1 0;
}
ConfigContent .action-btn {
    background: $surface;
    border: tall $primary;
    padding: 0 2;
    margin: 0 1 0 0;
    height: 3;
    content-align: center middle;
    color: $primary;
}
"""
```

Update `compose()` to use containers:

```python
def compose(self) -> ComposeResult:
    yield Static("ENGINES", classes="section-title", id="engines-section")
    yield Static(
        "Keys: [bold]n[/bold] new  [bold]e[/bold] edit  [bold]x[/bold] delete  [bold]F5[/bold] refresh",
        classes="content-hint",
    )
    table = DataTable(id="engines-table")
    table.add_columns("Name", "Kind", "Provider", "Model")
    yield table

    yield Static("PROJECT", classes="section-title", id="project-section")
    yield Static("Loading...", id="project-info", classes="config-box")

    yield Static("SERVER", classes="section-title")
    yield Static("Status: checking...", id="server-status", classes="config-box")
    with Horizontal(classes="server-controls"):
        yield Static("[bold]S[/bold] Start", classes="action-btn")
        yield Static("[bold]X[/bold] Stop", classes="action-btn")

    yield Static("THEME", classes="section-title")
    yield Static("Active: tokyo-night  [bold]T[/bold] Switch", id="theme-info", classes="config-box")
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/tui/content/test_config.py -v`
Expected: All pass

- [ ] **Step 3: Run visual test**

Run: `python tests/tui/visual_test.py`

- [ ] **Step 4: Commit**

```
refactor(tui): polish ConfigContent with section containers and controls
```

---

## Task 7: Final Visual Verification + Fix Test Fixture

**Files:**
- Modify: `tests/tui/visual_test.py`

The visual test creates a temp project with YAML that doesn't match `WorkspaceConfig` schema (missing `project` field). This causes data not to load in Flows/Agents tabs.

- [ ] **Step 1: Fix test fixture YAML**

Read the existing test fixtures in the test suite to find the correct YAML format:
```bash
grep -r "miniautogen.yaml" tests/ --include="*.py" -l
```

Then look at how valid YAML is structured (likely needs a `project:` key wrapping the config). Update `create_test_project()` in `tests/tui/visual_test.py` to use the correct schema.

- [ ] **Step 2: Run visual test**

Run: `python tests/tui/visual_test.py`
Verify: All 6 screenshots captured. Flows/Agents tabs now show data.

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/tui/ -v --tb=short`
Expected: All 240+ tests pass

- [ ] **Step 4: Inspect screenshots side-by-side with mockup**

Read each SVG file to verify:
- [ ] Tab bar shows brand + tabs + status
- [ ] Workspace has 4 stat cards
- [ ] Health check is in bordered box
- [ ] Quick actions are styled buttons
- [ ] Sidebar has clear header with status
- [ ] Flows/Agents have styled headers
- [ ] Config has section containers

- [ ] **Step 5: Commit**

```
fix(tui): fix visual test fixture and verify polish
```

---

## Execution Order

| Task | Component | Dependencies | Est. Complexity |
|------|-----------|-------------|-----------------|
| 1 | Shared CSS classes | None | Low |
| 2 | TabBar polish | Task 1 | Medium |
| 3 | WorkspaceContent polish | Task 1 | Medium |
| 4 | Sidebar + IdlePanel polish | None | Low |
| 5 | Flows + Agents polish | Task 1 | Low |
| 6 | ConfigContent polish | Task 1 | Medium |
| 7 | Test fixture + final verification | All above | Low |

**Parallelizable:** Tasks 2, 3, 4, 5, 6 can run in parallel after Task 1. Task 7 is sequential after all.
