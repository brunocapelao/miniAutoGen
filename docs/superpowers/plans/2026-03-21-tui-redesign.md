# TUI Redesign — AI Flow Studio Style Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign MiniAutoGen Dash from sidebar-left + chat layout to AI Flow Studio layout with top tab bar, inline tab content, and persistent right execution sidebar.

**Architecture:** Evolutionary refactor. Keep data layer (`DashDataProvider`), event pipeline (`TuiEventSink`, `EventBridgeWorker`, `EventMapper`), status vocabulary, themes, and reusable widgets (`InteractionLog`, `ApprovalBanner`, `StepBlock`, `ToolCallCard`). Replace app shell, navigation, and primary views.

**Important codebase notes:**
- `EmptyState` widget takes `pipelines: list[str]` — use `Static` widgets for generic empty states in CRUD views, not `EmptyState`
- `1-4` tab switching bindings must live on the App (not TabBar) because DataTables steal focus
- `CheckView` and `EventsView` exist at `views/check.py` and `views/events.py` — reuse as-is
- Widget-specific CSS lives in `DEFAULT_CSS` on each class; `dash.tcss` handles layout only

**Tech Stack:** Python 3.11+, Textual 0.x, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-21-tui-redesign-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `miniautogen/tui/widgets/tab_bar.py` | 4-tab navigation widget with active state |
| `miniautogen/tui/widgets/main_content.py` | Container that swaps child content per active tab |
| `miniautogen/tui/widgets/execution_sidebar.py` | Right panel: idle (team+recent) or active (live log) |
| `miniautogen/tui/widgets/idle_panel.py` | Sidebar idle state: team status + recent runs |
| `miniautogen/tui/content/workspace.py` | Workspace tab: project overview + health + quick actions |
| `miniautogen/tui/content/__init__.py` | Content package init |
| `miniautogen/tui/content/flows.py` | Flows tab: DataTable CRUD + run trigger |
| `miniautogen/tui/content/agents.py` | Agents tab: DataTable CRUD |
| `miniautogen/tui/content/config.py` | Config tab: engines + project + server + theme |
| `miniautogen/tui/content/run_detail.py` | Run detail view: steps, progress, stop |
| `miniautogen/tui/views/monitor.py` | MonitorView secondary screen: runs + events |
| `tests/tui/widgets/test_tab_bar.py` | TabBar tests |
| `tests/tui/widgets/test_execution_sidebar.py` | ExecutionSidebar tests |
| `tests/tui/widgets/test_idle_panel.py` | IdlePanel tests |
| `tests/tui/widgets/test_main_content.py` | MainContent tests |
| `tests/tui/content/__init__.py` | Content test package |
| `tests/tui/content/test_workspace.py` | WorkspaceContent tests |
| `tests/tui/content/test_flows.py` | FlowsContent tests |
| `tests/tui/content/test_agents.py` | AgentsContent tests |
| `tests/tui/content/test_config.py` | ConfigContent tests |
| `tests/tui/content/test_run_detail.py` | RunDetailView tests |
| `tests/tui/views/test_monitor.py` | MonitorView tests |

### Modified Files

| File | Changes |
|------|---------|
| `miniautogen/tui/app.py` | Complete rewrite of compose(), bindings, message handlers |
| `miniautogen/tui/dash.tcss` | New layout CSS replacing old sidebar-left layout |
| `miniautogen/tui/messages.py` | Add `TabChanged`, `RunStarted`, `RunStopped` messages |
| `miniautogen/tui/widgets/__init__.py` | Export new widgets |
| `tests/tui/test_app.py` | Rewrite for new layout and tab navigation |

### Preserved Files (No Changes)

All files listed in spec Section 14 "Tests That Survive": `data_provider.py`, `event_mapper.py`, `event_sink.py`, `notifications.py`, `status.py`, `themes.py`, `workers.py`, `interaction_log.py`, `approval_banner.py`, `tool_call_card.py`, `step_block.py`, `empty_state.py`, `create_form.py`, `confirm_dialog.py`, `init_wizard.py`, `agent_card.py` (screen), `diff_view.py`, `help_screen.py`.

---

## Task 1: New Messages

**Files:**
- Modify: `miniautogen/tui/messages.py`
- Test: `tests/tui/test_messages.py`

- [ ] **Step 1: Write failing tests for new messages**

```python
# tests/tui/test_messages.py — append to existing
from miniautogen.tui.messages import TabChanged, RunStarted, RunStopped


def test_tab_changed_message() -> None:
    msg = TabChanged(tab_name="flows")
    assert msg.tab_name == "flows"


def test_run_started_message() -> None:
    msg = RunStarted(flow_name="research-flow", run_id="abc123")
    assert msg.flow_name == "research-flow"
    assert msg.run_id == "abc123"


def test_run_stopped_message() -> None:
    msg = RunStopped(run_id="abc123", final_status="completed")
    assert msg.run_id == "abc123"
    assert msg.final_status == "completed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/tui/test_messages.py -v -k "tab_changed or run_started or run_stopped"`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement new messages**

Add to `miniautogen/tui/messages.py`:

```python
class TabChanged(Message):
    """Posted when user switches tabs."""

    def __init__(self, tab_name: str) -> None:
        super().__init__()
        self.tab_name = tab_name


class RunStarted(Message):
    """Posted when a flow execution begins."""

    def __init__(self, flow_name: str, run_id: str) -> None:
        super().__init__()
        self.flow_name = flow_name
        self.run_id = run_id


class RunStopped(Message):
    """Posted when a flow execution ends (any reason)."""

    def __init__(self, run_id: str, final_status: str) -> None:
        super().__init__()
        self.run_id = run_id
        self.final_status = final_status
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/tui/test_messages.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
feat(tui): add TabChanged, RunStarted, RunStopped messages
```

---

## Task 2: TabBar Widget

**Files:**
- Create: `miniautogen/tui/widgets/tab_bar.py`
- Test: `tests/tui/widgets/test_tab_bar.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tui/widgets/test_tab_bar.py
import pytest
from textual.app import App, ComposeResult

from miniautogen.tui.widgets.tab_bar import TabBar


def test_tab_bar_is_widget() -> None:
    bar = TabBar()
    assert hasattr(bar, "compose")


def test_tab_bar_default_tabs() -> None:
    bar = TabBar()
    assert bar.tab_names == ["Workspace", "Flows", "Agents", "Config"]


def test_tab_bar_active_tab_default() -> None:
    bar = TabBar()
    assert bar.active_tab == "Workspace"


def test_tab_bar_set_active() -> None:
    bar = TabBar()
    bar.active_tab = "Flows"
    assert bar.active_tab == "Flows"


class TabBarTestApp(App):
    def compose(self) -> ComposeResult:
        yield TabBar()


@pytest.mark.asyncio
async def test_tab_bar_renders() -> None:
    app = TabBarTestApp()
    async with app.run_test(size=(120, 5)) as pilot:
        bar = app.query_one(TabBar)
        assert bar.active_tab == "Workspace"


@pytest.mark.asyncio
async def test_tab_bar_switch_programmatic() -> None:
    """Number keys live on App level. TabBar is set via active_tab property."""
    app = TabBarTestApp()
    async with app.run_test(size=(120, 5)) as pilot:
        bar = app.query_one(TabBar)
        bar.active_tab = "Flows"
        assert bar.active_tab == "Flows"
        bar.active_tab = "Agents"
        assert bar.active_tab == "Agents"
        bar.active_tab = "Config"
        assert bar.active_tab == "Config"
        bar.active_tab = "Workspace"
        assert bar.active_tab == "Workspace"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/tui/widgets/test_tab_bar.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement TabBar**

```python
# miniautogen/tui/widgets/tab_bar.py
"""Tab bar navigation widget for MiniAutoGen Dash."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.messages import TabChanged

_TABS = ["Workspace", "Flows", "Agents", "Config"]


class TabBar(Widget):
    """Horizontal tab bar with 4 primary tabs.

    Note: Number key bindings (1-4) live on the App, not here,
    because DataTables in content widgets steal focus.
    The App calls `tab_bar.active_tab = name` directly.
    """

    DEFAULT_CSS = """
    TabBar {
        dock: top;
        height: 1;
        background: $surface;
        layout: horizontal;
    }
    TabBar .tab {
        padding: 0 2;
        color: $text-muted;
    }
    TabBar .tab.--active {
        color: $text;
        text-style: bold;
        background: $primary-background;
    }
    TabBar .tab:hover {
        background: $primary-background-darken-1;
    }
    """

    active_tab: reactive[str] = reactive("Workspace")

    @property
    def tab_names(self) -> list[str]:
        return list(_TABS)

    def compose(self) -> ComposeResult:
        for name in _TABS:
            classes = "tab --active" if name == self.active_tab else "tab"
            yield Static(name, classes=classes, id=f"tab-{name.lower()}")

    def watch_active_tab(self, old_value: str, new_value: str) -> None:
        """Update visual state when active tab changes."""
        for name in _TABS:
            tab = self.query_one(f"#tab-{name.lower()}", Static)
            tab.set_classes("tab --active" if name == new_value else "tab")
        self.post_message(TabChanged(tab_name=new_value))

    def action_switch_tab(self, tab_name: str) -> None:
        """Switch to a named tab."""
        if tab_name in _TABS:
            self.active_tab = tab_name
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/tui/widgets/test_tab_bar.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
feat(tui): add TabBar widget with 4-tab navigation
```

---

## Task 3: IdlePanel Widget

**Files:**
- Create: `miniautogen/tui/widgets/idle_panel.py`
- Test: `tests/tui/widgets/test_idle_panel.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tui/widgets/test_idle_panel.py
import pytest
from textual.app import App, ComposeResult

from miniautogen.tui.widgets.idle_panel import IdlePanel


def test_idle_panel_is_widget() -> None:
    panel = IdlePanel()
    assert hasattr(panel, "compose")


def test_idle_panel_update_agents() -> None:
    panel = IdlePanel()
    agents = [
        {"name": "planner", "status": "idle"},
        {"name": "researcher", "status": "idle"},
    ]
    panel.set_agents(agents)
    assert panel.agent_count == 2


def test_idle_panel_update_recent_runs() -> None:
    panel = IdlePanel()
    runs = [
        {"flow_name": "research-flow", "status": "done", "ago": "2m"},
    ]
    panel.set_recent_runs(runs)
    assert panel.run_count == 1


class IdlePanelTestApp(App):
    def compose(self) -> ComposeResult:
        yield IdlePanel()


@pytest.mark.asyncio
async def test_idle_panel_renders_empty() -> None:
    app = IdlePanelTestApp()
    async with app.run_test(size=(40, 20)) as pilot:
        panel = app.query_one(IdlePanel)
        assert panel is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/tui/widgets/test_idle_panel.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement IdlePanel**

```python
# miniautogen/tui/widgets/idle_panel.py
"""Sidebar idle state: team status + recent runs."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.status import AgentStatus, StatusVocab


class IdlePanel(Widget):
    """Shows team status and recent runs when no flow is executing."""

    DEFAULT_CSS = """
    IdlePanel {
        height: 1fr;
        padding: 1;
    }
    IdlePanel .section-label {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 1;
    }
    IdlePanel .agent-row {
        height: 1;
    }
    IdlePanel .run-row {
        height: 1;
        color: $text-muted;
    }
    IdlePanel .separator {
        height: 1;
        margin: 1 0;
        color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._agents: list[dict] = []
        self._recent_runs: list[dict] = []

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    @property
    def run_count(self) -> int:
        return len(self._recent_runs)

    def compose(self) -> ComposeResult:
        yield Static("TEAM STATUS", classes="section-label")
        yield Static("", id="team-list")
        yield Static("─" * 20, classes="separator")
        yield Static("RECENT", classes="section-label")
        yield Static("", id="recent-list")

    def set_agents(self, agents: list[dict]) -> None:
        """Update the team status list."""
        self._agents = agents
        self._refresh_team()

    def set_recent_runs(self, runs: list[dict]) -> None:
        """Update the recent runs list."""
        self._recent_runs = runs[:5]
        self._refresh_runs()

    def _refresh_team(self) -> None:
        try:
            team_list = self.query_one("#team-list", Static)
        except Exception:
            return
        if not self._agents:
            team_list.update("No agents configured.")
            return
        lines = []
        _STATUS_MAP = {
            "idle": AgentStatus.PENDING,
            "working": AgentStatus.WORKING,
            "done": AgentStatus.DONE,
            "active": AgentStatus.ACTIVE,
            "waiting": AgentStatus.WAITING,
            "failed": AgentStatus.FAILED,
            "cancelled": AgentStatus.CANCELLED,
        }
        for agent in self._agents:
            status_str = agent.get("status", "idle")
            agent_status = _STATUS_MAP.get(status_str, AgentStatus.PENDING)
            info = StatusVocab.get(agent_status)
            symbol = info.symbol if info else "○"
            name = agent.get("name", "unknown")
            lines.append(f"{symbol} {name}  {status_str}")
        team_list.update("\n".join(lines))

    def _refresh_runs(self) -> None:
        try:
            runs_list = self.query_one("#recent-list", Static)
        except Exception:
            return
        if not self._recent_runs:
            runs_list.update("No runs yet.")
            return
        lines = []
        for run in self._recent_runs:
            status_char = "✓" if run.get("status") == "done" else "✕"
            name = run.get("flow_name", "unknown")
            ago = run.get("ago", "")
            lines.append(f"{status_char} {name}  {ago}")
        runs_list.update("\n".join(lines))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/tui/widgets/test_idle_panel.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
feat(tui): add IdlePanel widget for sidebar idle state
```

---

## Task 4: ExecutionSidebar Widget

**Files:**
- Create: `miniautogen/tui/widgets/execution_sidebar.py`
- Test: `tests/tui/widgets/test_execution_sidebar.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tui/widgets/test_execution_sidebar.py
import pytest
from textual.app import App, ComposeResult

from miniautogen.tui.widgets.execution_sidebar import ExecutionSidebar


def test_execution_sidebar_is_widget() -> None:
    sidebar = ExecutionSidebar()
    assert hasattr(sidebar, "compose")


def test_execution_sidebar_starts_idle() -> None:
    sidebar = ExecutionSidebar()
    assert sidebar.is_executing is False


class SidebarTestApp(App):
    def compose(self) -> ComposeResult:
        yield ExecutionSidebar()


@pytest.mark.asyncio
async def test_sidebar_renders_idle() -> None:
    app = SidebarTestApp()
    async with app.run_test(size=(40, 30)) as pilot:
        sidebar = app.query_one(ExecutionSidebar)
        assert sidebar.is_executing is False


@pytest.mark.asyncio
async def test_sidebar_transitions_to_active() -> None:
    app = SidebarTestApp()
    async with app.run_test(size=(40, 30)) as pilot:
        sidebar = app.query_one(ExecutionSidebar)
        sidebar.start_execution()
        assert sidebar.is_executing is True


@pytest.mark.asyncio
async def test_sidebar_transitions_to_idle() -> None:
    app = SidebarTestApp()
    async with app.run_test(size=(40, 30)) as pilot:
        sidebar = app.query_one(ExecutionSidebar)
        sidebar.start_execution()
        sidebar.stop_execution()
        assert sidebar.is_executing is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/tui/widgets/test_execution_sidebar.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement ExecutionSidebar**

```python
# miniautogen/tui/widgets/execution_sidebar.py
"""Persistent right sidebar: idle panel or live execution log."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.widgets.idle_panel import IdlePanel
from miniautogen.tui.widgets.interaction_log import InteractionLog


class ExecutionSidebar(Widget):
    """Right sidebar that shows idle state or live execution log."""

    DEFAULT_CSS = """
    ExecutionSidebar {
        dock: right;
        width: 35;
        background: $surface;
        border-left: solid $primary-background;
    }
    ExecutionSidebar .sidebar-header {
        height: 1;
        padding: 0 1;
        color: $primary;
        text-style: bold;
        background: $surface;
    }
    ExecutionSidebar .status-indicator {
        color: $text-muted;
    }
    """

    is_executing: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        super().__init__()
        self.interaction_log = InteractionLog()

    def compose(self) -> ComposeResult:
        yield Static("Execution", classes="sidebar-header", id="sidebar-title")
        yield IdlePanel()
        yield self.interaction_log

    def on_mount(self) -> None:
        self.interaction_log.display = False

    def watch_is_executing(self, value: bool) -> None:
        """Toggle between idle panel and live log."""
        try:
            idle = self.query_one(IdlePanel)
            idle.display = not value
            self.interaction_log.display = value
            title = self.query_one("#sidebar-title", Static)
            title.update("Execution Log  ◐ live" if value else "Execution")
        except Exception:
            pass

    def start_execution(self) -> None:
        """Switch to live execution mode."""
        self.is_executing = True

    def stop_execution(self) -> None:
        """Switch back to idle mode."""
        self.is_executing = False

    def set_agents(self, agents: list[dict]) -> None:
        """Pass through to idle panel."""
        try:
            idle = self.query_one(IdlePanel)
            idle.set_agents(agents)
        except Exception:
            pass

    def set_recent_runs(self, runs: list[dict]) -> None:
        """Pass through to idle panel."""
        try:
            idle = self.query_one(IdlePanel)
            idle.set_recent_runs(runs)
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/tui/widgets/test_execution_sidebar.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
feat(tui): add ExecutionSidebar with idle/active states
```

---

## Task 5: MainContent Container

**Files:**
- Create: `miniautogen/tui/widgets/main_content.py`
- Test: `tests/tui/widgets/test_main_content.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tui/widgets/test_main_content.py
import pytest
from textual.app import App, ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from miniautogen.tui.widgets.main_content import MainContent


class PlaceholderContent(Widget):
    def __init__(self, label: str) -> None:
        super().__init__(id=f"content-{label}")
        self.label = label

    def compose(self):
        yield Static(self.label)


def test_main_content_is_widget() -> None:
    mc = MainContent()
    assert hasattr(mc, "compose")


class MainContentTestApp(App):
    def compose(self) -> ComposeResult:
        mc = MainContent()
        mc.register_tab("Workspace", PlaceholderContent("Workspace"))
        mc.register_tab("Flows", PlaceholderContent("Flows"))
        yield mc


@pytest.mark.asyncio
async def test_main_content_shows_default_tab() -> None:
    app = MainContentTestApp()
    async with app.run_test(size=(80, 20)) as pilot:
        mc = app.query_one(MainContent)
        assert mc.active_tab == "Workspace"


@pytest.mark.asyncio
async def test_main_content_switches_tab() -> None:
    app = MainContentTestApp()
    async with app.run_test(size=(80, 20)) as pilot:
        mc = app.query_one(MainContent)
        mc.switch_to("Flows")
        assert mc.active_tab == "Flows"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/tui/widgets/test_main_content.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement MainContent**

```python
# miniautogen/tui/widgets/main_content.py
"""Container that swaps content widgets based on active tab."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget


class MainContent(Widget):
    """Main content area that shows one tab's content at a time."""

    DEFAULT_CSS = """
    MainContent {
        width: 1fr;
        height: 1fr;
    }
    """

    active_tab: reactive[str] = reactive("Workspace")

    def __init__(self) -> None:
        super().__init__()
        self._tabs: dict[str, Widget] = {}

    def register_tab(self, name: str, content: Widget) -> None:
        """Register a content widget for a tab name."""
        self._tabs[name] = content

    def compose(self) -> ComposeResult:
        for name, widget in self._tabs.items():
            widget.display = name == self.active_tab
            yield widget

    def switch_to(self, tab_name: str) -> None:
        """Switch visible content to the named tab."""
        if tab_name in self._tabs:
            self.active_tab = tab_name

    def watch_active_tab(self, old_value: str, new_value: str) -> None:
        """Show/hide content widgets based on active tab."""
        for name, widget in self._tabs.items():
            widget.display = name == new_value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/tui/widgets/test_main_content.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
feat(tui): add MainContent container for tab-based content switching
```

---

## Task 6: WorkspaceContent (Workspace Tab)

**Files:**
- Create: `miniautogen/tui/content/__init__.py`
- Create: `miniautogen/tui/content/workspace.py`
- Test: `tests/tui/content/__init__.py`
- Test: `tests/tui/content/test_workspace.py`

- [ ] **Step 1: Create package init files**

```python
# miniautogen/tui/content/__init__.py
"""Tab content widgets for MiniAutoGen Dash."""

# tests/tui/content/__init__.py
# (empty file)
```

- [ ] **Step 2: Write failing tests**

```python
# tests/tui/content/test_workspace.py
import pytest
from textual.app import App, ComposeResult

from miniautogen.tui.content.workspace import WorkspaceContent


def test_workspace_content_is_widget() -> None:
    ws = WorkspaceContent()
    assert hasattr(ws, "compose")


class WorkspaceTestApp(App):
    def compose(self) -> ComposeResult:
        yield WorkspaceContent()


@pytest.mark.asyncio
async def test_workspace_renders() -> None:
    app = WorkspaceTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        ws = app.query_one(WorkspaceContent)
        assert ws is not None


@pytest.mark.asyncio
async def test_workspace_has_overview_section() -> None:
    app = WorkspaceTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        ws = app.query_one(WorkspaceContent)
        overview = ws.query_one("#overview-section")
        assert overview is not None


@pytest.mark.asyncio
async def test_workspace_has_health_section() -> None:
    app = WorkspaceTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        ws = app.query_one(WorkspaceContent)
        health = ws.query_one("#health-section")
        assert health is not None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/tui/content/test_workspace.py -v`
Expected: FAIL

- [ ] **Step 4: Implement WorkspaceContent**

```python
# miniautogen/tui/content/workspace.py
"""Workspace tab: project overview, health check, quick actions."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class WorkspaceContent(Widget):
    """Home tab showing project overview and health status."""

    DEFAULT_CSS = """
    WorkspaceContent {
        height: 1fr;
        padding: 1 2;
    }
    WorkspaceContent .section-label {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 1;
        margin-top: 1;
    }
    WorkspaceContent .stat-card {
        height: 3;
        padding: 0 2;
        background: $surface;
        margin: 0 1 0 0;
    }
    WorkspaceContent .stat-value {
        text-style: bold;
    }
    WorkspaceContent .health-item {
        height: 1;
    }
    WorkspaceContent #quick-actions {
        height: 1;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("PROJECT OVERVIEW", classes="section-label")
        yield Static("Loading...", id="overview-section")
        yield Static("HEALTH CHECK", classes="section-label")
        yield Static("Running checks...", id="health-section")
        yield Static("QUICK ACTIONS", classes="section-label")
        yield Static(
            "[n] New Agent  [r] Run Flow  [:] Commands",
            id="quick-actions",
        )

    def refresh_data(
        self,
        agents_count: int = 0,
        flows_count: int = 0,
        engines_count: int = 0,
        last_run_status: str = "—",
        health_items: list[tuple[str, str]] | None = None,
    ) -> None:
        """Update the workspace with fresh data."""
        overview = f"Agents: {agents_count}  Flows: {flows_count}  Engines: {engines_count}  Last Run: {last_run_status}"
        try:
            self.query_one("#overview-section", Static).update(overview)
        except Exception:
            pass

        if health_items:
            lines = []
            for symbol, text in health_items:
                lines.append(f"{symbol} {text}")
            try:
                self.query_one("#health-section", Static).update(
                    "\n".join(lines)
                )
            except Exception:
                pass
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/tui/content/test_workspace.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```
feat(tui): add WorkspaceContent tab with overview and health
```

---

## Task 7: FlowsContent (Flows Tab)

**Files:**
- Create: `miniautogen/tui/content/flows.py`
- Test: `tests/tui/content/test_flows.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tui/content/test_flows.py
import pytest
from textual.app import App, ComposeResult

from miniautogen.tui.content.flows import FlowsContent


def test_flows_content_is_widget() -> None:
    fc = FlowsContent()
    assert hasattr(fc, "compose")


class FlowsTestApp(App):
    def compose(self) -> ComposeResult:
        yield FlowsContent()


@pytest.mark.asyncio
async def test_flows_renders() -> None:
    app = FlowsTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        fc = app.query_one(FlowsContent)
        assert fc is not None


@pytest.mark.asyncio
async def test_flows_has_data_table() -> None:
    app = FlowsTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        fc = app.query_one(FlowsContent)
        from textual.widgets import DataTable
        table = fc.query_one(DataTable)
        assert table is not None
```

- [ ] **Step 2: Run tests, verify fail, implement**

Implement `FlowsContent` following the same pattern as existing `PipelinesView` (from `miniautogen/tui/views/pipelines.py`) but as an inline Widget instead of a Screen. Key differences:
- Extends `Widget` (not `Screen`)
- No Header/Footer (those belong to the app shell)
- Uses `x` for delete (not `d`), `F5` for refresh, `r` for run
- Delete goes through `ConfirmDialog`
- Posts `RunStarted` message when triggering a flow
- Has `_refresh_table()` method that reads from `self.app._provider.get_pipelines()`

```python
# miniautogen/tui/content/flows.py
"""Flows tab: DataTable with CRUD and run trigger."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import DataTable, Static

from miniautogen.tui.messages import SidebarRefresh
class FlowsContent(Widget, can_focus=True):
    """Flows tab with DataTable CRUD and run trigger."""

    DEFAULT_CSS = """
    FlowsContent {
        height: 1fr;
    }
    FlowsContent DataTable {
        height: 1fr;
        width: 1fr;
    }
    FlowsContent .view-title {
        padding: 1 2;
        text-style: bold;
    }
    FlowsContent .view-hint {
        padding: 0 2;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("n", "new_flow", "New", show=True),
        Binding("e", "edit_flow", "Edit", show=True),
        Binding("x", "delete_flow", "Delete", show=True),
        Binding("r", "run_flow", "Run", show=True),
        Binding("f5", "refresh", "Refresh", show=True),
    ]

    @property
    def provider(self):
        return self.app._provider

    def compose(self) -> ComposeResult:
        yield Static("Flows", classes="view-title")
        yield Static(
            "Keys: [n]ew  [e]dit  [x] delete  [r]un  [F5] refresh",
            classes="view-hint",
        )
        table = DataTable(id="flows-table")
        table.add_columns("Name", "Mode", "Agents", "Status")
        yield table
        yield Static(
            "No flows defined. Press [bold][n][/bold] to create one.",
            id="flows-empty",
            classes="empty-hint",
        )

    def on_mount(self) -> None:
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#flows-table", DataTable)
        table.clear()
        empty = self.query_one("#flows-empty", Static)
        if not self.provider:
            empty.display = True
            table.display = False
            return
        pipelines = self.provider.get_pipelines()
        if not pipelines:
            empty.display = True
            table.display = False
            return
        empty.display = False
        table.display = True
        for p in pipelines:
            agents = p.get("participants", [])
            agent_count = len(agents) if isinstance(agents, list) else str(agents)
            table.add_row(
                p.get("name", ""),
                p.get("mode", "workflow"),
                str(agent_count),
                "ready",
            )

    def action_new_flow(self) -> None:
        from miniautogen.tui.screens.create_form import CreateFormScreen
        self.app.push_screen(
            CreateFormScreen(resource_type="pipeline"),
            callback=self._on_form_result,
        )

    def action_edit_flow(self) -> None:
        table = self.query_one("#flows-table", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            self.app.notify("No flow selected", severity="warning")
            return
        row = table.get_row_at(table.cursor_row)
        name = str(row[0])
        from miniautogen.tui.screens.create_form import CreateFormScreen
        self.app.push_screen(
            CreateFormScreen(resource_type="pipeline", edit_name=name),
            callback=self._on_form_result,
        )

    def action_delete_flow(self) -> None:
        table = self.query_one("#flows-table", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            self.app.notify("No flow selected", severity="warning")
            return
        row = table.get_row_at(table.cursor_row)
        name = str(row[0])
        from miniautogen.tui.screens.confirm_dialog import ConfirmDialog
        self.app.push_screen(
            ConfirmDialog(f"Delete flow '{name}'?"),
            callback=lambda confirmed: self._do_delete(name) if confirmed else None,
        )

    def _do_delete(self, name: str) -> None:
        try:
            self.provider.delete_pipeline(name)
            self.app.notify(f"Flow '{name}' deleted")
        except Exception as e:
            self.app.notify(str(e), severity="error")
        self._refresh_table()

    def action_run_flow(self) -> None:
        table = self.query_one("#flows-table", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            self.app.notify("No flow selected", severity="warning")
            return
        row = table.get_row_at(table.cursor_row)
        name = str(row[0])
        from miniautogen.tui.messages import RunStarted
        self.post_message(RunStarted(flow_name=name, run_id=""))
        self.app.notify(f"Starting flow '{name}'...")

    def action_refresh(self) -> None:
        self._refresh_table()

    def _on_form_result(self, result: bool) -> None:
        if result:
            self._refresh_table()
            self.post_message(SidebarRefresh())
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `python -m pytest tests/tui/content/test_flows.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```
feat(tui): add FlowsContent tab with CRUD and run trigger
```

---

## Task 8: AgentsContent (Agents Tab)

**Files:**
- Create: `miniautogen/tui/content/agents.py`
- Test: `tests/tui/content/test_agents.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tui/content/test_agents.py
import pytest
from textual.app import App, ComposeResult

from miniautogen.tui.content.agents import AgentsContent


def test_agents_content_is_widget() -> None:
    ac = AgentsContent()
    assert hasattr(ac, "compose")


class AgentsTestApp(App):
    def compose(self) -> ComposeResult:
        yield AgentsContent()


@pytest.mark.asyncio
async def test_agents_renders() -> None:
    app = AgentsTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        ac = app.query_one(AgentsContent)
        assert ac is not None


@pytest.mark.asyncio
async def test_agents_has_data_table() -> None:
    app = AgentsTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        from textual.widgets import DataTable
        table = app.query_one(DataTable)
        assert table is not None
```

- [ ] **Step 2: Implement AgentsContent**

Follow same pattern as FlowsContent. Refactor from `miniautogen/tui/views/agents.py`:
- Extends `Widget` (not `Screen`)
- Bindings: `n` (new), `e` (edit), `x` (delete with ConfirmDialog), `F5` (refresh), `Enter` (detail)
- DataTable columns: Name, Role, Engine, Status
- Posts `SidebarRefresh` after CRUD

```python
# miniautogen/tui/content/agents.py
"""Agents tab: DataTable with CRUD."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import DataTable, Static

from miniautogen.tui.messages import SidebarRefresh
class AgentsContent(Widget, can_focus=True):
    """Agents tab with DataTable CRUD."""

    DEFAULT_CSS = """
    AgentsContent {
        height: 1fr;
    }
    AgentsContent DataTable {
        height: 1fr;
        width: 1fr;
    }
    AgentsContent .view-title {
        padding: 1 2;
        text-style: bold;
    }
    AgentsContent .view-hint {
        padding: 0 2;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("n", "new_agent", "New", show=True),
        Binding("e", "edit_agent", "Edit", show=True),
        Binding("x", "delete_agent", "Delete", show=True),
        Binding("f5", "refresh", "Refresh", show=True),
        Binding("enter", "view_detail", "Detail", show=True),
    ]

    @property
    def provider(self):
        return self.app._provider

    def compose(self) -> ComposeResult:
        yield Static("Agents", classes="view-title")
        yield Static(
            "Keys: [n]ew  [e]dit  [x] delete  [F5] refresh  [Enter] detail",
            classes="view-hint",
        )
        table = DataTable(id="agents-table")
        table.add_columns("Name", "Role", "Engine", "Status")
        yield table
        yield Static(
            "No agents yet. Press [bold][n][/bold] to create one.",
            id="agents-empty",
            classes="empty-hint",
        )

    def on_mount(self) -> None:
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        table.clear()
        empty = self.query_one("#agents-empty", Static)
        if not self.provider:
            empty.display = True
            table.display = False
            return
        agents = self.provider.get_agents()
        if not agents:
            empty.display = True
            table.display = False
            return
        empty.display = False
        table.display = True
        for a in agents:
            table.add_row(
                a.get("name", ""),
                a.get("role", ""),
                a.get("engine", ""),
                "ready",
            )

    def action_new_agent(self) -> None:
        from miniautogen.tui.screens.create_form import CreateFormScreen
        self.app.push_screen(
            CreateFormScreen(resource_type="agent"),
            callback=self._on_form_result,
        )

    def action_edit_agent(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            self.app.notify("No agent selected", severity="warning")
            return
        row = table.get_row_at(table.cursor_row)
        name = str(row[0])
        from miniautogen.tui.screens.create_form import CreateFormScreen
        self.app.push_screen(
            CreateFormScreen(resource_type="agent", edit_name=name),
            callback=self._on_form_result,
        )

    def action_delete_agent(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            self.app.notify("No agent selected", severity="warning")
            return
        row = table.get_row_at(table.cursor_row)
        name = str(row[0])
        from miniautogen.tui.screens.confirm_dialog import ConfirmDialog
        self.app.push_screen(
            ConfirmDialog(f"Delete agent '{name}'?"),
            callback=lambda confirmed: self._do_delete(name) if confirmed else None,
        )

    def _do_delete(self, name: str) -> None:
        try:
            self.provider.delete_agent(name)
            self.app.notify(f"Agent '{name}' deleted")
        except Exception as e:
            self.app.notify(str(e), severity="error")
        self._refresh_table()
        self.post_message(SidebarRefresh())

    def action_view_detail(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            return
        row = table.get_row_at(table.cursor_row)
        name = str(row[0])
        if self.provider:
            agent_data = self.provider.get_agent(name)
            if agent_data:
                from miniautogen.tui.screens.agent_card import AgentCardScreen
                self.app.push_screen(AgentCardScreen(agent_data))

    def action_refresh(self) -> None:
        self._refresh_table()

    def _on_form_result(self, result: bool) -> None:
        if result:
            self._refresh_table()
            self.post_message(SidebarRefresh())
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `python -m pytest tests/tui/content/test_agents.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```
feat(tui): add AgentsContent tab with CRUD
```

---

## Task 9: ConfigContent (Config Tab)

**Files:**
- Create: `miniautogen/tui/content/config.py`
- Test: `tests/tui/content/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tui/content/test_config.py
import pytest
from textual.app import App, ComposeResult

from miniautogen.tui.content.config import ConfigContent


def test_config_content_is_widget() -> None:
    cc = ConfigContent()
    assert hasattr(cc, "compose")


class ConfigTestApp(App):
    def compose(self) -> ComposeResult:
        yield ConfigContent()


@pytest.mark.asyncio
async def test_config_renders() -> None:
    app = ConfigTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        cc = app.query_one(ConfigContent)
        assert cc is not None


@pytest.mark.asyncio
async def test_config_has_engines_section() -> None:
    app = ConfigTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        cc = app.query_one(ConfigContent)
        engines = cc.query_one("#engines-section")
        assert engines is not None


@pytest.mark.asyncio
async def test_config_has_project_section() -> None:
    app = ConfigTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        cc = app.query_one(ConfigContent)
        project = cc.query_one("#project-section")
        assert project is not None
```

- [ ] **Step 2: Implement ConfigContent**

Consolidates engines DataTable (from EnginesView) + project config (from ConfigView) + server controls + theme switcher. Uses `S`/`X`/`T` shift-key bindings scoped to this widget.

- [ ] **Step 3: Run tests, verify pass, commit**

```
feat(tui): add ConfigContent tab with engines, project, server, theme
```

---

## Task 10: RunDetailView

**Files:**
- Create: `miniautogen/tui/content/run_detail.py`
- Test: `tests/tui/content/test_run_detail.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tui/content/test_run_detail.py
import pytest
from textual.app import App, ComposeResult

from miniautogen.tui.content.run_detail import RunDetailView


def test_run_detail_is_widget() -> None:
    rdv = RunDetailView(flow_name="test-flow", flow_mode="workflow")
    assert rdv.flow_name == "test-flow"


def test_run_detail_starts_at_step_zero() -> None:
    rdv = RunDetailView(flow_name="test", flow_mode="workflow")
    assert rdv.current_step == 0
    assert rdv.total_steps == 0


class RunDetailTestApp(App):
    def compose(self) -> ComposeResult:
        yield RunDetailView(flow_name="research-flow", flow_mode="workflow")


@pytest.mark.asyncio
async def test_run_detail_renders() -> None:
    app = RunDetailTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        rdv = app.query_one(RunDetailView)
        assert rdv is not None


@pytest.mark.asyncio
async def test_run_detail_update_progress() -> None:
    app = RunDetailTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        rdv = app.query_one(RunDetailView)
        rdv.update_progress(current=2, total=5, label="Research")
        assert rdv.current_step == 2
        assert rdv.total_steps == 5
```

- [ ] **Step 2: Implement RunDetailView**

Shows: flow name + metadata, progress bar, collapsible step blocks (reuses `StepBlock` widget), stop button. Receives `TuiEvent` messages to update step states.

- [ ] **Step 3: Run tests, verify pass, commit**

```
feat(tui): add RunDetailView for execution visualization
```

---

## Task 11: MonitorView (Secondary Screen)

**Files:**
- Create: `miniautogen/tui/views/monitor.py`
- Test: `tests/tui/views/test_monitor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tui/views/test_monitor.py
import pytest
from miniautogen.tui.views.monitor import MonitorView


def test_monitor_view_is_screen() -> None:
    from textual.screen import Screen
    assert issubclass(MonitorView, Screen)


def test_monitor_view_has_title() -> None:
    assert MonitorView.VIEW_TITLE == "Monitor"
```

- [ ] **Step 2: Implement MonitorView**

Extends `SecondaryView` (from `views/base.py`). Uses Textual's `TabbedContent` for Runs/Events sub-tabs. Reuses DataTable patterns from RunsView and EventsView.

- [ ] **Step 3: Run tests, verify pass, commit**

```
feat(tui): add MonitorView secondary screen with runs and events
```

---

## Task 12: New CSS Stylesheet

**Files:**
- Modify: `miniautogen/tui/dash.tcss`

- [ ] **Step 1: Rewrite CSS for new layout**

Replace the old sidebar-left + WorkPanel layout with the new structure:

```tcss
/* ── Layout ─────────────────── */
Screen {
    background: $background;
}

#app-grid {
    layout: horizontal;
    height: 1fr;
}

/* ── TabBar ──────────────────── */
TabBar {
    dock: top;
    height: 1;
    background: $surface;
}
TabBar .tab {
    padding: 0 2;
    color: $text-muted;
}
TabBar .tab.--active {
    color: $text;
    text-style: bold;
    background: $primary-background;
}

/* ── MainContent ─────────────── */
MainContent {
    width: 1fr;
    height: 1fr;
}

/* ── ExecutionSidebar ────────── */
ExecutionSidebar {
    dock: right;
    width: 35;
    background: $surface;
    border-left: solid $primary-background;
}

/* ── Content tabs ────────────── */
WorkspaceContent, FlowsContent, AgentsContent, ConfigContent {
    height: 1fr;
}

/* ── RunDetailView ───────────── */
RunDetailView {
    height: 1fr;
    padding: 1 2;
}
RunDetailView .flow-header {
    height: 2;
    text-style: bold;
}
RunDetailView #run-progress {
    height: 1;
    margin: 1 0;
}

/* Keep existing widget styles */
/* StepBlock, ToolCallCard, ApprovalBanner, EmptyState styles preserved */
```

- [ ] **Step 2: Verify existing widget CSS still works**

Ensure `StepBlock`, `ToolCallCard`, `ApprovalBanner`, `EmptyState`, `InteractionLog` CSS is preserved (these widgets use `DEFAULT_CSS` inline, so they're self-contained).

- [ ] **Step 3: Commit**

```
refactor(tui): rewrite CSS for AI Flow Studio layout
```

---

## Task 13a: App Shell — compose() and Bindings

**Files:**
- Modify: `miniautogen/tui/app.py`

- [ ] **Step 1: Rewrite app compose()**

Replace old `Header + TeamSidebar + WorkPanel + Footer` with:

```python
def compose(self) -> ComposeResult:
    yield Header()
    yield TabBar()
    with Horizontal(id="app-grid"):
        main = MainContent()
        main.register_tab("Workspace", WorkspaceContent())
        main.register_tab("Flows", FlowsContent())
        main.register_tab("Agents", AgentsContent())
        main.register_tab("Config", ConfigContent())
        yield main
        yield ExecutionSidebar()
    yield Footer()
```

- [ ] **Step 2: Update BINDINGS**

Number keys `1-4` go on the App (not TabBar) because DataTables steal focus:

```python
BINDINGS = [
    Binding("q", "quit", "Quit", show=True),
    Binding("question_mark", "help", "Help", show=True),
    Binding("escape", "back", "Back", show=True),
    Binding("t", "toggle_sidebar", "Sidebar", show=True),
    Binding("f", "fullscreen", "Fullscreen", show=False),
    Binding("s", "stop_run", "Stop", show=False),
    Binding("1", "switch_tab('Workspace')", "1", show=False),
    Binding("2", "switch_tab('Flows')", "2", show=False),
    Binding("3", "switch_tab('Agents')", "3", show=False),
    Binding("4", "switch_tab('Config')", "4", show=False),
]
```

- [ ] **Step 3: Update SCREENS dict**

```python
SCREENS = {
    "monitor": MonitorView,
    "check": CheckView,    # existing views/check.py
    "events": EventsView,  # existing views/events.py
    "diff": DiffViewScreen,
}
```

Remove: `agents`, `pipelines`, `runs`, `engines`, `config` (now tab content).

- [ ] **Step 4: Implement action_switch_tab**

```python
def action_switch_tab(self, tab_name: str) -> None:
    tab_bar = self.query_one(TabBar)
    tab_bar.active_tab = tab_name
```

- [ ] **Step 5: Commit**

```
refactor(tui): rewrite app compose() and bindings for tab layout
```

---

## Task 13b: App Shell — Message Handlers and Lifecycle

**Files:**
- Modify: `miniautogen/tui/app.py`

- [ ] **Step 1: Update message handlers**

```python
def on_tab_changed(self, event: TabChanged) -> None:
    main = self.query_one(MainContent)
    main.switch_to(event.tab_name)

def on_run_started(self, event: RunStarted) -> None:
    sidebar = self.query_one(ExecutionSidebar)
    sidebar.start_execution()
    # Show RunDetailView in MainContent (replaces Flows content)

def on_run_stopped(self, event: RunStopped) -> None:
    sidebar = self.query_one(ExecutionSidebar)
    sidebar.stop_execution()

def on_tui_event(self, event: TuiEvent) -> None:
    sidebar = self.query_one(ExecutionSidebar)
    sidebar.interaction_log.handle_event(event.event)

def on_sidebar_refresh(self, event: SidebarRefresh) -> None:
    self._populate_sidebar()
    self._refresh_workspace()
```

- [ ] **Step 2: Update on_mount() lifecycle**

1. `_apply_responsive()` — breakpoints: < 100 hide sidebar, 100-130 = 25 cols, > 130 = 35 cols
2. `_init_provider()` — keep existing, show InitWizard if no project
3. `_update_server_status()` — keep
4. `_populate_sidebar()` → call `sidebar.set_agents()` instead of `sidebar.add_agent()`
5. `_refresh_workspace()` — new: update WorkspaceContent with stats
6. `_start_event_bridge()` — keep existing logic

- [ ] **Step 3: Commit**

```
refactor(tui): wire message handlers and lifecycle for new layout
```

---

## Task 13c: App Shell — Test Rewrite

**Files:**
- Modify: `tests/tui/test_app.py`

- [ ] **Step 1: Rewrite test_app.py for new layout**

Key tests to write:
- `test_app_has_tab_bar` — verify TabBar is in the widget tree
- `test_app_has_execution_sidebar` — verify sidebar on right
- `test_app_has_main_content` — verify MainContent with 4 tabs
- `test_tab_switching_via_keys` — press 1-4, verify MainContent.active_tab changes
- `test_event_flow_to_sidebar` — publish event, verify sidebar interaction_log receives it
- `test_sidebar_toggle` — press `t`, verify sidebar hidden/shown

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/tui/ -v --tb=short`
Expected: All new tests pass. Identify any old tests that fail.

- [ ] **Step 3: Fix cascade failures**

For each failing old test, either update for new structure or delete if testing removed components (TeamSidebar, WorkPanel, HintBar, PipelineTabs, AgentCard widget).

- [ ] **Step 4: Commit**

```
test(tui): rewrite app tests for AI Flow Studio layout
```

---

## Task 14: Final Integration and Cleanup

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/tui/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 2: Visual verification**

Run: `python -c "from miniautogen.tui.app import MiniAutoGenDash; app = MiniAutoGenDash(); import asyncio; asyncio.run(app.run_test(size=(160,45)).export_screenshot())"`

Verify the layout matches the spec mockups.

- [ ] **Step 3: Remove dead code**

Delete files that are no longer imported anywhere:
- `miniautogen/tui/widgets/team_sidebar.py` (replaced by ExecutionSidebar)
- `miniautogen/tui/widgets/work_panel.py` (replaced by MainContent + tab content)
- `miniautogen/tui/widgets/hint_bar.py` (replaced by Footer)
- `miniautogen/tui/widgets/pipeline_tabs.py` (replaced by TabBar)
- `miniautogen/tui/widgets/agent_card.py` (widget, not screen — no longer in sidebar)
- Old view files if fully replaced: `views/agents.py`, `views/pipelines.py`, `views/engines.py`, `views/runs.py`

**Note:** Keep `views/events.py` and `views/check.py` (still used as secondary views). Keep `views/base.py` (MonitorView extends it).

- [ ] **Step 4: Delete old test files for removed components**

- `tests/tui/widgets/test_team_sidebar.py`
- `tests/tui/widgets/test_work_panel.py`
- `tests/tui/widgets/test_hint_bar.py`
- `tests/tui/widgets/test_pipeline_tabs.py`
- `tests/tui/widgets/test_agent_card.py` (widget tests, not screen tests)

- [ ] **Step 5: Run full test suite one final time**

Run: `python -m pytest tests/tui/ -v`
Expected: ALL PASS, zero import errors, zero dead references

- [ ] **Step 6: Commit**

```
chore(tui): remove dead code and old tests from pre-redesign
```

---

## Execution Order Summary

| Task | Component | Dependencies | Est. Complexity |
|------|-----------|-------------|-----------------|
| 1 | Messages | None | Low |
| 2 | TabBar | Task 1 (TabChanged) | Low |
| 3 | IdlePanel | None | Low |
| 4 | ExecutionSidebar | Task 3 (IdlePanel) | Medium |
| 5 | MainContent | None | Low |
| 6 | WorkspaceContent | None | Low |
| 7 | FlowsContent | Task 1 (RunStarted) | Medium |
| 8 | AgentsContent | None | Medium |
| 9 | ConfigContent | None | Medium |
| 10 | RunDetailView | None | Medium |
| 11 | MonitorView | None | Medium |
| 12 | CSS Rewrite | Tasks 2-11 | Low |
| 13a | App Shell — compose + bindings | ALL above | Medium |
| 13b | App Shell — handlers + lifecycle | Task 13a | Medium |
| 13c | App Shell — test rewrite | Task 13b | Medium |
| 14 | Cleanup | Task 13c | Low |

**Critical path:** Tasks 1-11 can largely be done in parallel (independent widgets). Task 12-13a depend on all widgets existing. Tasks 13a→13b→13c are sequential. Task 14 is final cleanup.

**Parallelizable groups:**
- Group A (no deps): Tasks 1, 3, 5, 6
- Group B (after Task 1): Tasks 2, 7
- Group C (after Task 3): Task 4
- Group D (no deps): Tasks 8, 9, 10, 11
- Group E (all above): Tasks 12, 13a, 13b, 13c, 14 (sequential)
