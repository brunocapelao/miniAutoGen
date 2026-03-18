# MiniAutoGen Dash — Design Specification v5.0

**Date:** 2026-03-17
**Status:** Approved
**Concept:** "Your AI Team at Work"

## Vision

MiniAutoGen Dash shows your team of AI agents working. Each agent is a colleague with name, icon, and role. The pipeline is their conversation — who spoke, what they did, what they decided. You observe, and when asked, you decide.

**It's not a metrics panel. It's a workspace where you see your team think.**

## Architecture

```
Core (PipelineRunner, Runtimes)
      │ publishes ExecutionEvent
      ▼
CompositeEventSink
      ├── InMemoryEventSink (existing)
      ├── LoggingEventSink (existing)
      └── TuiEventSink (NEW) → MemoryObjectStream → Textual Worker → UI
```

Zero coupling to core. TuiEventSink implements existing EventSink protocol.
Event bridge uses `anyio.create_memory_object_stream()` for async-safe cross-loop communication.

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| TUI Engine | Textual ≥1.0 | Layout, widgets, reactivity, CSS, themes |
| Rendering | Rich (bundled) | Syntax highlighting, markdown, tables |
| Charts | textual-plotext | Only in `:metrics` secondary view |
| Event Bridge | TuiEventSink | EventSink → MemoryObjectStream → Worker |
| Packaging | `miniautogen[tui]` | Optional extra dependency |

## The Workspace (Primary View)

Two panels. Only two.

- **The Team** (left, narrow) — Agent roster. Icon, name, role, status.
- **The Work** (right, wide) — Interaction log. Steps as conversation blocks.

Layout inspiration: Slack (channels left, conversation right).

### The Team (Left Panel)

Each agent is a colleague:
- `🏛 Planner` — Architect
- `✏ Writer` — Developer
- `🔍 Reviewer` — QA Lead
- `✨ Editor` — Refiner

Shows: icon, name, role, status indicator. Syncs with pipeline execution.

### The Work (Right Panel)

The pipeline IS the conversation. Steps appear as collapsible blocks:

- **Done step:** Collapsed to 2-3 line summary. Enter to expand.
- **Active step:** Fully expanded with streaming output.
- **Pending step:** One descriptive line ("Reviewer will review the code").

Inside each step:
- Agent messages with icon + name
- Syntax-highlighted code blocks (Rich Syntax)
- Tool call inline cards (sidebar `▌` indicator)
- Streaming indicators (`░░░ thinking...`, cursor block `▊`)

### Progress Bar

Bottom of work panel: `▰▰▰▰▰▰▰▱▱▱▱▱▱ Step 2 of 4`

## Status Vocabulary (7 States)

| Symbol | Color | Meaning | When |
|--------|-------|---------|------|
| `✓` | dim green | Done | Completed |
| `●` | bright green | Active | Executing now |
| `◐` | yellow | Working | LLM generating |
| `⏳` | amber | Waiting | Blocked (HITL) |
| `○` | gray | Pending | Not started |
| `✕` | red | Failed | Error |
| `⊘` | dim red | Cancelled | Cancelled |

Each symbol is distinguishable without color (accessibility).

## Streaming States

- **Thinking:** `░░░ thinking...` (pulsing)
- **Generating:** Text appears with cursor block `▊`
- **Tool in-flight:** `▌🔧 tool_name` + `◐ executing... 2.1s`
- **Tool complete:** `▌🔧 tool_name` + `✓ result summary`

## HITL Approval

Inline in conversation flow (not blocking modal):
- Double-border banner with action description
- `[A]pprove` (filled) and `[D]eny` (hollow) buttons
- Contextual: developer sees what led to the request

## Agent Detail (Slide-in Panel)

Click agent in sidebar → slide-in from right:
- Name (large), role, engine, goal description
- Tools list, permissions
- Current run status
- Actions: `[e]dit`, `[h]istory`, `[Esc]close`

## Multiple Pipelines

When 2+ pipelines active → tabs at top:
```
┌─ ● main ─────┐  ┌─ ◐ data-prep ─┐
```
Number keys (1-9) for quick switch. Tab key cycles.

## Empty States

- No pipelines: "Your team is ready." + pipeline list + run instructions
- No agents: "No agents configured. Define agents in your pipeline YAML."
- No messages: "Waiting for agents to begin..."

## Responsive Breakpoints

| Terminal | Behavior |
|----------|----------|
| ≥120×40 | Full layout: Team sidebar + Work panel |
| 100×30 | Team sidebar collapses to icons only |
| 80×24 | Team sidebar hidden (toggle with `t`). Work panel full-width |

## Navigation

### Global Keys

| Key | Action |
|-----|--------|
| `:` | Command palette (fuzzy search) |
| `/` | Search/filter in current view |
| `?` | Help overlay |
| `Esc` | Back / close panel |
| `Tab` | Switch pipeline tab |
| `1-9` | Quick-switch pipeline |
| `d` | Diff view |
| `f` | Fullscreen work panel |
| `t` | Toggle team sidebar |

### Hint Bar (always visible)
```
[Enter]detail  [/]search  [:]commands  [d]iff  [?]help
```

### Context Keymap

| Key | Workspace | Agent Detail | Command Palette |
|-----|-----------|-------------|-----------------|
| Enter | Expand step/agent | — | Execute |
| Esc | — | Close | Dismiss |
| / | Filter log | — | — |
| : | Open palette | Open palette | — |

## Secondary Views (via `:command`)

| Command | Content | Priority |
|---------|---------|----------|
| `:agents` | Agent roster CRUD | v1 |
| `:pipelines` | Pipeline list CRUD | v1 |
| `:runs` | Run history | v1 |
| `:events` | Raw event stream with filters | v1 |
| `:engines` | Engine profiles CRUD | v1 |
| `:config` | Project configuration | v1 |
| `:metrics` | Token/cost/latency details | v2 |

Each is a DataTable with per-row actions.

## Coordination Mode Adaptations

- **Workflow:** Steps sequential (Step 1 → Step 2 → ...)
- **Deliberation:** Steps as rounds (Round 1: contributions, Round 2: reviews...)
- **AgenticLoop:** Steps as turns with router decisions
- **Composite:** Nested step blocks

The Work panel adapts labeling and structure per mode.

## Desktop Notifications (OSC 9/99)

Events that trigger notifications:
- `APPROVAL_REQUESTED` → "⏳ Agent X needs approval"
- `RUN_FINISHED` → "✓ Pipeline completed"
- `RUN_FAILED` → "✕ Pipeline failed"

Fallback to terminal bell when OSC unsupported.
Config: `notifications: all | failures-only | none`

## Themes

4 built-in themes via Textual TCSS variables:
- tokyo-night (default dark)
- catppuccin
- monokai
- light

Semantic color tokens: `status.active`, `status.done`, `surface.primary`, etc.

## What Was Cut

| Feature | Reason |
|---------|--------|
| Mascot "Mini" | Noise without informational value |
| Web mode | Scope creep, loses to web-native tools |
| Topology graph (separate) | Pipeline IS the conversation |
| NetworkX | No graph to calculate |
| textual-canvas | No pixel rendering needed |
| 5 simultaneous zones | UX anti-pattern |
| Circular loop layout | XL cost, marginal value |
| Complex CSS animations | Textual limited, marginal value |
| Metrics as first-class | User directive: secondary |
| SVG export prominence | Nice-to-have, trivial built-in |
