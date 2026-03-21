# TUI Redesign — AI Flow Studio Style

> **Version:** 1.0.0 | **Date:** 2026-03-21
> **Status:** Approved
> **Scope:** Visual and structural redesign of MiniAutoGen Dash TUI
> **Approach:** Evolutionary (refactor existing codebase, preserve data layer and event pipeline)

---

## 1. Design Vision

Redesign the MiniAutoGen Dash TUI from a Slack-like layout (sidebar left + chat center) to an **AI Flow Studio** layout inspired by Bit Office and AI Flow Canvas Editor. The new design uses a top tab bar for navigation, a persistent right sidebar for execution monitoring, and a main content area that changes per tab.

### References

- **Bit Office** (github.com/longyangxi/OpenOffice): Team panel UX, agent status badges, chat interaction, activity awareness
- **AI Flow Canvas Editor**: Tab bar navigation, contextual sidebar, bottom panel for logs, IDE-like feel

---

## 2. Architecture Overview

### 2.1 Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ Header: [MiniAutoGen] [Workspace|Flows|Agents|Config]  ● Server│
├──────────────────────────────────────────┬──────────────────────┤
│                                          │                      │
│  Main Content Area                       │  Execution Sidebar   │
│  (changes per tab)                       │  (always visible)    │
│                                          │                      │
│                                          │  Idle: team status   │
│                                          │  + recent runs       │
│                                          │                      │
│                                          │  Active: live log    │
│                                          │  + approval controls │
│                                          │                      │
├──────────────────────────────────────────┴──────────────────────┤
│ Footer: [1-4] tabs  [:] commands  [?] help  [t] sidebar  [q]   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Model

| Layer | Type | Examples |
|-------|------|----------|
| **L0 — Shell** | App frame | Header + TabBar + MainContent + Sidebar + Footer |
| **L1 — Tab Content** | Inline views | Workspace, Flows, Agents, Config (rendered in MainContent) |
| **L2 — Secondary Views** | Pushed screens via command palette | `:monitor`, `:canvas`, `:check`, `:events` |
| **L3 — Modals** | ModalScreens | InitWizard, CreateForm, AgentCardScreen, ConfirmDialog, DiffView |

### 2.3 Component Hierarchy

```
MiniAutoGenDash (App)
│
├── Header (title + tab bar + server status)
│   └── TabBar (4 tabs: Workspace, Flows, Agents, Config)
│
├── MainContent (area principal, 1fr)
│   ├── WorkspaceContent (when tab=Workspace)
│   ├── FlowsContent (when tab=Flows)
│   ├── AgentsContent (when tab=Agents)
│   ├── ConfigContent (when tab=Config)
│   └── RunDetailView (auto-replaces active tab during execution)
│
├── ExecutionSidebar (dock: right, ~280px)
│   ├── IdlePanel (when no execution)
│   │   ├── TeamStatus (agent list with status dots)
│   │   └── RecentRuns (last N runs with status)
│   └── LivePanel (during execution)
│       ├── InteractionLog (RichLog, auto-scroll)
│       └── ApprovalBanner (inline, when needed)
│
└── Footer (key hints)
```

---

## 3. Navigation System

### 3.1 Primary Navigation (Tabs)

4 primary tabs, navigable via number keys and command palette:

| Tab | Key | Command | Content |
|-----|-----|---------|---------|
| Workspace | `1` | `:workspace` | Project overview, health check, quick actions |
| Flows | `2` | `:flows` | Flow list DataTable with CRUD + run |
| Agents | `3` | `:agents` | Agent roster DataTable with CRUD |
| Config | `4` | `:config` | Engines DataTable + project settings + theme switcher |

**Behavior:** Tabs change only the main content area. The execution sidebar remains constant.

### 3.2 Secondary Navigation (Command Palette)

Accessible via `:` (command palette). These push a screen on top of the current view:

| Command | View | Content |
|---------|------|---------|
| `:monitor` | MonitorView | Run history + event stream with filtering |
| `:canvas` | CanvasView | Pipeline topology graph (new feature) |
| `:check` | CheckView | Project health check details |
| `:events` | EventsView | Event stream with type/agent/keyword filters |

### 3.3 Modal Navigation

Modals overlay the current view:

| Trigger | Modal | Purpose |
|---------|-------|---------|
| Auto (no project) | InitWizardScreen | Project bootstrap |
| `n` in CRUD views | CreateFormScreen | Create agent/engine/flow |
| `e` in CRUD views | CreateFormScreen (edit) | Edit resource |
| `d` in CRUD views | ConfirmDialog → delete | Delete with confirmation |
| Click agent in sidebar | AgentCardScreen | Agent detail |
| `?` | HelpScreen | Keybinding reference |
| `:diff` (command palette) | DiffViewScreen | Code diff viewer |

---

## 4. Tab Content Specifications

### 4.1 Workspace Tab

The home screen. Shows project overview and health.

```
┌─────────────────────────────────────────┐
│ PROJECT OVERVIEW                        │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌──────┐      │
│ │  4  │ │  2  │ │  3  │ │  ✓   │      │
│ │Agents│ │Flows│ │Engs │ │Last  │      │
│ │ready │ │     │ │     │ │Run   │      │
│ └─────┘ └─────┘ └─────┘ └──────┘      │
│                                         │
│ HEALTH CHECK                            │
│ ✓ miniautogen.yaml found               │
│ ✓ Engine "default_api" reachable        │
│ ✓ All agents have valid engine profiles │
│ ⚠ Agent "coder" has no tools configured │
│                                         │
│ QUICK ACTIONS                           │
│ [n] New Agent  [r] Run Flow  [:] Cmds   │
└─────────────────────────────────────────┘
```

**Data sources:**
- `provider.get_agents()` → count
- `provider.get_pipelines()` → count
- `provider.get_engines()` → count
- `provider.check_project()` → health results
- `provider.get_runs()[-1]` → last run status

### 4.2 Flows Tab

Flow management with CRUD and execution trigger.

```
┌─────────────────────────────────────────┐
│ Flows                                   │
│ Keys: [n]ew  [e]dit  [d]elete  [r]un   │
├─────────────────────────────────────────┤
│ Name          │ Mode        │ Agents    │
│───────────────│─────────────│───────────│
│ research-flow │ workflow    │ 4         │
│ code-review   │ deliberation│ 3         │
│ qa-loop       │ loop        │ 2         │
├─────────────────────────────────────────┤
│ [F5] Refresh                            │
└─────────────────────────────────────────┘
```

**Key bindings:**

| Key | Action | Notes |
|-----|--------|-------|
| `n` | New flow | Opens CreateForm with participants field |
| `e` | Edit selected | CreateForm in edit mode |
| `d` | Delete selected | **ConfirmDialog first** (UX fix) |
| `r` | Run selected flow | Triggers execution, auto-switches to RunDetailView |
| `F5` | Refresh | Consistent across all CRUD views |
| `Enter` | View detail | Show flow configuration |

**UX fix:** `r` here means "Run" (not Refresh like other views). This is intentional for Flows — the footer clearly labels it. `F5` is universal Refresh.

### 4.3 Agents Tab

Agent management with CRUD.

```
┌─────────────────────────────────────────┐
│ Agents                                  │
│ Keys: [n]ew  [e]dit  [d]elete          │
├─────────────────────────────────────────┤
│ Name       │ Role       │ Engine │Status│
│────────────│────────────│────────│──────│
│ planner    │ planner    │ gpt-4o │ready │
│ researcher │ researcher │ gpt-4o │ready │
│ reviewer   │ reviewer   │ claude │ready │
│ coder      │ developer  │ gpt-4o │ready │
├─────────────────────────────────────────┤
│ [F5] Refresh                            │
└─────────────────────────────────────────┘
```

**Key bindings:** `n` (new), `e` (edit), `d` (delete with ConfirmDialog), `F5` (refresh), `Enter` (open AgentCardScreen)

### 4.4 Config Tab

Consolidated configuration: engines + project settings + theme.

```
┌─────────────────────────────────────────┐
│ ENGINES                                 │
│ Keys: [n]ew  [e]dit  [d]elete          │
├─────────────────────────────────────────┤
│ Name       │ Kind │ Provider │ Model    │
│────────────│──────│──────────│──────────│
│ default_api│ api  │ litellm  │ gpt-4o   │
│ claude     │ api  │ litellm  │ claude-3 │
│ local_llm  │ local│ ollama   │ llama3   │
├─────────────────────────────────────────┤
│ PROJECT                                 │
│ Name: my-project  Version: 0.1.0       │
│ Default Engine: default_api             │
│ Database: sqlite:///miniautogen.db      │
├─────────────────────────────────────────┤
│ SERVER                                  │
│ Status: ● running (:8080)               │
│ [S] Start  [X] Stop                    │
├─────────────────────────────────────────┤
│ THEME                                   │
│ Active: tokyo-night                     │
│ [T] Switch theme                        │
└─────────────────────────────────────────┘
```

---

## 5. Execution Sidebar

### 5.1 Idle State

When no flow is running, the sidebar shows:

```
┌──────────────────────┐
│ Execution      idle  │
├──────────────────────┤
│ TEAM STATUS          │
│ ○ Planner      idle  │
│ ○ Researcher   idle  │
│ ○ Reviewer     idle  │
│ ○ Coder        idle  │
│──────────────────────│
│ RECENT               │
│ ✓ research-flow  2m  │
│ ✕ code-review   15m  │
└──────────────────────┘
```

**Data sources:**
- `provider.get_agents()` → team list
- `provider.get_runs()` → recent runs (in-memory, last 5)

### 5.2 Active State (During Execution)

When a flow is running, the sidebar transitions to a live execution log:

```
┌──────────────────────┐
│ Execution Log  ◐live │
├──────────────────────┤
│ ── Step 1: Planning──│
│ Planner: I'll analyze│
│ the requirements...  │
│ ✓ Step 1 (4.2s)      │
│                      │
│ ── Step 2: Research──│
│ Researcher: Searching│
│ ◐ web_search  1.3s   │
│                      │
│            auto-scroll│
├──────────────────────┤
│ ⏛ Approval Required │
│ Researcher wants to  │
│ access external API  │
│ [a]Approve [d]Deny   │
└──────────────────────┘
```

**Components reused:** `InteractionLog` (RichLog), `ApprovalBanner`

**Interactive entries:** Each log entry links to its source component:
- Click agent name → opens AgentCardScreen
- Click tool call → shows tool detail
- Click step header → highlights step in RunDetailView (if visible)

### 5.3 Responsive Behavior

**Note:** Replaces old breakpoints (6/28 columns for TeamSidebar). Textual uses character columns, not pixels.

| Terminal Width | Sidebar | Sidebar Width |
|---------------|---------|---------------|
| < 100 columns | Hidden | 0 |
| 100-130 columns | Visible | 25 columns (compact) |
| > 130 columns | Visible | 35 columns (full) |

Toggle: `t` key. Auto-hide on narrow terminals.

---

## 6. Run Detail View (During Execution)

When a flow is triggered (via `r` in Flows tab), the main content area auto-switches to RunDetailView:

```
┌─────────────────────────────────────────┐
│ research-flow                    ■ Stop │
│ workflow · 4 agents · step 2/5          │
│ [████████░░░░░░░░░░░░░░░]  40%          │
├─────────────────────────────────────────┤
│ ✓ Step 1: Planning — Planner     4.2s  │ ← collapsed (done)
│                                         │
│ ◐ Step 2: Research — Researcher        │ ← expanded (active)
│ │ Researcher: Searching for papers...  │
│ │ ◐ web_search  executing 1.3s         │
│                                         │
│ ○ Step 3: Analysis — Reviewer          │ ← pending
│ ○ Step 4: Implementation — Coder       │ ← pending
│ ○ Step 5: Review — Reviewer            │ ← pending
└─────────────────────────────────────────┘
```

**Features:**
- Flow name + metadata header
- Overall progress bar (steps completed / total)
- **Stop** button (replaces current undiscoverable Ctrl+X)
- Collapsible step blocks: done steps collapse (show summary), active step expands (shows messages + tool calls inline), pending steps grayed out
- User can navigate away via tabs; RunDetailView stays as the active "content" until execution completes
- **Only one concurrent run is supported.** Starting a second run while one is active requires stopping the first.

**Tab interaction during execution:**
- RunDetailView replaces the Flows tab content. Pressing `2` (Flows) during execution shows RunDetailView.
- Pressing `1`, `3`, `4` shows their normal content (Workspace, Agents, Config).
- When the user navigates to another tab and back to Flows, they return to RunDetailView (not FlowsContent).
- After execution completes or is stopped, pressing `Esc` or `F5` in Flows tab dismisses RunDetailView and returns to FlowsContent.

**After completion:** RunDetailView shows final status (success/failure), duration, step summary. Press `Esc` to dismiss and return to FlowsContent.

---

## 7. UX Fixes Included

All anti-patterns from the current UX spec (section 10.3) are addressed:

| Anti-Pattern | Fix |
|-------------|-----|
| Delete without confirmation | All delete operations go through `ConfirmDialog` |
| Inconsistent `r` key | `r` = Run in Flows tab (intentional, labeled), `F5` = universal Refresh |
| Fullscreen without restore | `f` is a proper toggle (show/hide sidebar) |
| Empty DataTables without guidance | `EmptyState` widget with "[n] to create one" message |
| Pipeline form missing participants | Add multi-select field for agents + optional leader field |
| Search announced but not functional | Remove `/` from footer until implemented |
| Server controls hidden | Visible in Config tab with `S`/`X` (shift) labels |
| Agent detail edit/history stubs | Mark as "coming soon" or implement basic versions |

---

## 8. Keyboard Bindings (Complete Map)

### Global (App Level)

| Key | Action | Footer | Notes |
|-----|--------|--------|-------|
| `1-4` | Switch to tab N | Yes | |
| `:` | Command palette | Yes | |
| `?` | Help screen | Yes | |
| `t` | Toggle sidebar | Yes | |
| `f` | Toggle fullscreen (hide all chrome) | No | |
| `s` | Stop current run | Yes (during execution only) | Only active when a flow is running |
| `q` | Quit | Yes | |
| `Esc` | Back (pop screen in L2/L3, noop in L1) | Yes | In Flows tab after run: dismisses RunDetailView |

### CRUD Views (Agents, Flows, Config/Engines)

| Key | Action | Notes |
|-----|--------|-------|
| `n` | New resource | Opens CreateForm |
| `e` | Edit selected | CreateForm in edit mode |
| `x` | Delete selected | ConfirmDialog first |
| `F5` | Refresh | Universal across all views |
| `Enter` | View detail | AgentCard or Flow detail |

**Note on `x` for delete:** Changed from `d` to avoid conflict with ApprovalBanner's `d` (deny). `x` is mnemonic for "remove/cross out."

### Flows Tab (Additional)

| Key | Action |
|-----|--------|
| `r` | Run selected flow |

### Config Tab (Additional)

| Key | Action | Notes |
|-----|--------|-------|
| `S` (shift+s) | Start server | Scoped to Config tab |
| `X` (shift+x) | Stop server | Scoped to Config tab |
| `T` (shift+t) | Cycle theme | Scoped to Config tab |

**Note:** Uses uppercase (shift) keys to avoid terminal signal conflicts (`Ctrl+S` = XOFF, `Ctrl+X` = Textual internal).

### Execution Context (Sidebar-scoped)

| Key | Action | Scope |
|-----|--------|-------|
| `a` | Approve | Only when ApprovalBanner is focused in sidebar |
| `d` | Deny | Only when ApprovalBanner is focused in sidebar |

**Binding conflict resolution:** `d` (deny) and `x` (delete) are in different focus domains — ApprovalBanner lives in the ExecutionSidebar, CRUD delete lives in MainContent. Textual resolves by widget focus hierarchy, so they never conflict.

---

## 9. Theme System

Preserved from current implementation. 4 themes with semantic tokens:

- **tokyo-night** (default)
- **catppuccin**
- **monokai**
- **light**

**New:** Theme switcher accessible from Config tab via `T` key, cycling through available themes.

---

## 10. What Changes vs. What Stays

### What Changes

| Component | Current | New |
|-----------|---------|-----|
| Layout | Sidebar left + WorkPanel right | TabBar top + MainContent left + Sidebar right |
| Navigation | Command palette only | Tab bar (1-4 keys) + command palette |
| Sidebar content | Agent roster (TeamSidebar) | Execution log (idle: team + recent; active: RichLog) |
| Views | Pushed screens (L1) | Tab content (inline) for primary, pushed for secondary |
| During execution | Only InteractionLog updates | RunDetailView in main + InteractionLog in sidebar |
| Server controls | Hidden keybindings | Visible in Config tab |
| Delete operations | No confirmation | ConfirmDialog |
| Flow form | Missing participants | Multi-select for agents |

### What Stays (Reused As-Is)

| Component | Notes |
|-----------|-------|
| `DashDataProvider` | Data layer unchanged |
| `EventMapper` | 44 event types → 7 statuses |
| `TuiEventSink` + `EventBridgeWorker` | Event pipeline unchanged |
| `AgentStatus` 7-state vocabulary | Symbols, colors, labels |
| `InteractionLog` | Moves to sidebar, same widget |
| `ApprovalBanner` | Moves to sidebar, same widget |
| `CreateFormScreen` | Enhanced with participants field |
| `ConfirmDialog` | Already exists, now used for deletes |
| `AgentCardScreen` | Unchanged |
| `InitWizardScreen` | Unchanged |
| `DiffViewScreen` | Unchanged |
| `HelpScreen` | Updated with new keybindings |
| 4 theme system | Add runtime switcher |
| Toast notifications | Unchanged |
| Desktop notifications (OSC 9/99) | Unchanged |

### New Components

| Component | Purpose |
|-----------|---------|
| `TabBar` | 4-tab navigation widget |
| `MainContent` | Container that swaps content per active tab |
| `WorkspaceContent` | Project overview + health check + quick actions |
| `FlowsContent` | Flow DataTable (replaces PipelinesView) |
| `AgentsContent` | Agent DataTable (replaces AgentsView) |
| `ConfigContent` | Engines DataTable + project config + server + theme |
| `ExecutionSidebar` | Right panel with idle/active states |
| `IdlePanel` | Team status + recent runs |
| `RunDetailView` | Step-by-step execution visualization |
| `CanvasView` | Pipeline topology graph (secondary, via `:canvas`) |
| `MonitorView` | Run history + event stream (secondary, via `:monitor`) |

---

## 11. Secondary Views (Command Palette)

### 11.1 MonitorView (`:monitor`)

Run history + event stream. Demoted from primary tab due to persistence gaps.

```
┌─────────────────────────────────────────┐
│ Monitor                                 │
│ [Runs] [Events]   ← sub-tabs           │
├─────────────────────────────────────────┤
│ Run ID   │ Flow          │ Status │ Dur │
│──────────│───────────────│────────│─────│
│ a1b2c3   │ research-flow │ ✓ done │ 12s │
│ d4e5f6   │ code-review   │ ✕ fail │ 3s  │
├─────────────────────────────────────────┤
│ [F5] Refresh  [Enter] Detail            │
└─────────────────────────────────────────┘
```

**Sub-tab navigation:** Uses Textual's `TabbedContent` widget. Switch between Runs and Events via:
- Click on sub-tab labels
- `Tab` key cycles between sub-tabs
- Content area updates immediately on switch

### 11.2 CanvasView (`:canvas`) — Deferred to v2

**Status:** Out of scope for v1 redesign. Included in the command palette as a placeholder.

Visual pipeline topology graph. Shows agents as nodes, connections as edges, flow direction.

**Rendering approach (for future implementation):**
- Use Textual's `Static` widget with Rich `Text` renderables to draw ASCII DAG
- Consider `rich.tree.Tree` for hierarchical flows or a custom ASCII graph renderer
- Nodes: `[agent_name]` boxes with status color borders
- Edges: Unicode box-drawing characters (`─`, `│`, `├`, `└`, `→`)
- Read-only visualization, no editing

**Why deferred:** Requires graph layout algorithm (topological sort → ASCII positioning) which is non-trivial. The text-based execution log + RunDetailView cover the primary use case.

### 11.3 CheckView (`:check`)

Detailed project health check results. Expanded version of the Workspace health section.

---

## 12. Error Handling & Empty States

| Context | Empty State Message |
|---------|-------------------|
| Workspace (no project, after wizard dismissed) | "No project found. Use `:init` to create one." |
| Workspace (no agents) | "No agents yet. Go to Agents tab [3] to create one." |
| Flows tab (no flows) | "No flows defined. Press [n] to create one." |
| Agents tab (no agents) | "No agents yet. Press [n] to create one." |
| Config/Engines (no engines) | "No engines configured. Press [n] to add one." |
| Sidebar idle (no recent runs) | "No runs yet. Run a flow from the Flows tab." |
| Monitor (no history) | "No run history. Runs are recorded during this session." |

---

## 13. Accessibility

Improvements over current implementation:

| Item | Action |
|------|--------|
| Status symbols | Already unique per status (no color dependency) ✓ |
| Focus management | ApprovalBanner auto-focuses when it appears |
| Tab navigation | Number keys provide direct access (no sequential tabbing) |
| Screen reader | Add proper widget names/descriptions to custom widgets |
| Color contrast | Verify all theme combinations meet WCAG AA |
| Duplicate status colors | Fix light theme: `waiting` and `failed` use same color |

---

## 14. Test Migration Strategy

The existing 198 tests need to be mapped to the new component structure:

### Tests That Survive (Reusable)

| Test File/Area | Reason |
|----------------|--------|
| `test_data_provider.py` | Data layer unchanged |
| `test_event_mapper.py` | Event mapping unchanged |
| `test_event_sink.py` | Stream bridge unchanged |
| `test_notifications.py` | Notification system unchanged |
| `test_status.py` | 7-state vocabulary unchanged |
| `test_themes.py` | Theme system unchanged |
| `test_interaction_log.py` | Widget reused in sidebar |
| `test_approval_banner.py` | Widget reused in sidebar |
| `test_tool_call_card.py` | Widget reused |
| `test_step_block.py` | Widget reused in RunDetailView |
| `test_empty_state.py` | Widget reused |
| `test_create_form.py` | Screen reused (enhanced) |
| `test_confirm_dialog.py` | Screen reused |
| `test_init_wizard.py` | Screen unchanged |
| `test_agent_card_screen.py` | Screen unchanged |
| `test_diff_view.py` | Screen unchanged |
| Zero coupling tests | Still valid — TUI imports only protocols |

### Tests That Need Rewriting

| Test File/Area | Reason |
|----------------|--------|
| `test_app.py` (shell tests) | Layout completely restructured — tabs replace command palette nav |
| `test_team_sidebar.py` | Widget replaced by ExecutionSidebar |
| `test_agent_card_widget.py` | Widget removed (sidebar no longer has agent cards) |
| `test_work_panel.py` | Widget replaced by MainContent + tab content |
| `test_hint_bar.py` | Replaced by new footer context |
| `test_pipeline_tabs.py` | Replaced by TabBar |
| App integration tests | Mount, bindings, event flow need new assertions |

### New Tests Required

| Component | Test Focus |
|-----------|-----------|
| `TabBar` | Tab switching, active state, number key nav |
| `MainContent` | Content swapping per tab, RunDetailView takeover |
| `ExecutionSidebar` | Idle → active transition, log entries, approval |
| `WorkspaceContent` | Stats display, health check, quick actions |
| `FlowsContent` | CRUD + run trigger + RunDetailView lifecycle |
| `AgentsContent` | CRUD + ConfirmDialog integration |
| `ConfigContent` | Engines CRUD + server controls + theme switcher |
| `RunDetailView` | Step blocks, progress, stop, completion state |
| `MonitorView` | Sub-tabs, run history display |

**Estimated impact:** ~40% of tests reusable, ~30% need rewriting, ~30% new tests.
