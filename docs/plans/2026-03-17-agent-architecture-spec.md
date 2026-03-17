# Agent Architecture Specification

**Status:** Approved (v2 — with memory architecture and per-agent organization)
**Date:** 2026-03-17

## Summary

Agents are defined by `AgentSpec`, enriched by Skills, Tools and MCP bindings,
bound to an `EngineProfile`, resolved at runtime by an `AgentResolver`,
and executed within `AgentSession`s persisted separately.

Memory is a **runtime-resolved capability**, not a magic attribute embedded in the agent.

## Core Entities

| Entity | Purpose | Format |
|---|---|---|
| `AgentSpec` | Declarative agent definition (role, skills, tools, MCP, memory profile, permissions) | YAML |
| `SkillSpec` | Reusable behavioral knowledge with SKILL.md | Directory + YAML |
| `ToolSpec` | Executable action with explicit interface | YAML |
| `McpServerBinding` | External system integration via MCP protocol | YAML |
| `EngineProfile` | How the agent runs (provider, model, adapter) | YAML in project config |
| `MemoryProfile` | How the agent recovers and persists context | YAML in project or agent config |
| `ResolvedAgentProfile` | Fully resolved agent ready for execution | Runtime object |
| `AgentSession` | Live agent execution instance | Store-persisted |

## Project Organization

Two valid structures are supported. The project chooses based on team size and complexity.

### Option A: Per-registry (flat) — default, scalable

```
project/
  miniautogen.yaml
  agents/
    planner.yaml
    researcher.yaml
  skills/
    deep-research/
      SKILL.md
      skill.yaml
  tools/
    web_search.yaml
  mcp/
    github.yaml
  memory/
    profiles.yaml
  pipelines/
    main.py
  .env
```

### Option B: Per-agent (encapsulated) — intuitive for small teams

```
project/
  miniautogen.yaml
  agents/
    pesquisador/
      agent.yaml
      skills/
      tools/
      mcp/
      memory/
        config.yaml
  pipelines/
    main.py
  .env
```

Both are valid. The `AgentResolver` resolves resources from either layout.
The CLI `init` generates Option A by default.

## Key Design Principles

1. Python-first, declarative when useful
2. Agent is not a persisted object — it's resolved at runtime
3. Capability (what) separated from execution (how)
4. Skills != Tools != MCP — each has distinct role
5. Session state persisted separately from definition
6. Filesystem is initial source of truth
7. CLI imports only miniautogen.api
8. **Memory is a runtime-resolved capability, not a magic attribute**

## Memory Architecture

### Principle

The MiniAutoGen does NOT impose an opaque memory abstraction embedded in the agent class.
Instead, each agent declares a **memory policy/profile**, and the runtime resolves that
profile into concrete components of retrieval, persistence, compaction, and context injection.

### Memory Profile in AgentSpec

```yaml
# In agent.yaml
memory:
  profile: research-light        # References a named profile
  session_memory: true            # Keep session conversation history
  retrieval_memory: true          # Enable semantic retrieval
  max_context_tokens: 24000       # Context window budget
```

### Memory Profiles (project-level)

```yaml
# In memory/profiles.yaml or miniautogen.yaml
memory_profiles:
  research-light:
    session: true
    retrieval:
      enabled: true
      store: vector
      top_k: 5
    compaction:
      enabled: true
      strategy: summary
      threshold_tokens: 16000
    summaries:
      enabled: true
      frequency: every_5_turns
    retention:
      max_sessions: 10
      ttl_days: 30
```

### Memory Resolution Flow

1. Agent declares memory profile in its spec
2. Project defines concrete memory components for that profile
3. During agent resolution, runtime connects profile to stores/adapters
4. During execution:
   - Memory retrieves relevant context
   - Context is injected into execution state
   - Engine adapter consumes enriched state
   - Results may update session, summary, checkpoint, or vector store

### Why this is better than magic memory

| Property | Benefit |
|---|---|
| **Visibility** | Know when memory was used, what sources, how many tokens |
| **Controllability** | Apply timeout, retry, fallback, degradation, isolation |
| **Auditability** | Which memory influenced this response? Which store? |
| **Portability** | Same memory profile works with any engine (Gemini, Codex, OpenAI, etc.) |

### Memory Components

A memory profile may compose:
- Session memory (conversation history)
- Semantic retrieval (vector store queries)
- Persistent history (across sessions)
- Summaries (periodic compression)
- Checkpoints (state snapshots)
- Context compaction (token budget management)

## Project Config Schema (miniautogen.yaml)

```yaml
project:
  name: my-agent-team
  version: "0.1.0"

defaults:
  engine_profile: gemini_api_default
  memory_profile: default          # NEW: default memory profile

engine_profiles:
  gemini_api_default:
    kind: api
    provider: gemini
    model: gemini-2.5-pro
    temperature: 0.2

memory_profiles:                    # NEW: memory profiles at project level
  default:
    session: true
    retrieval:
      enabled: false
    compaction:
      enabled: false

pipelines:
  main:
    target: pipelines.main:build_pipeline

database:
  url: sqlite+aiosqlite:///miniautogen.db
```

## Agent Resolution Flow

1. Load AgentSpec from YAML
2. Resolve attached skills (load SKILL.md + skill.yaml)
3. Resolve allowed tools (load tool specs)
4. Resolve MCP bindings and filter accessible tools
5. **Resolve memory profile into concrete components** (NEW)
6. Apply project defaults
7. Apply EngineProfile
8. Produce ResolvedAgentProfile (includes resolved memory)

## Public API Surface

```python
register_agent(spec) / get_agent(agent_id) / list_agents()
register_skill(path) / get_skill(skill_id) / list_skills()
register_tool(spec) / get_tool(tool_name) / list_tools()
register_mcp_server(binding) / get_mcp_server(server_id)
resolve_agent(agent_id) -> ResolvedAgentProfile
create_session(agent_id) -> AgentSession
```

## CLI Commands (M2 scope)

```bash
miniautogen init <project>
miniautogen check
miniautogen run <pipeline>
miniautogen sessions list|clean
```

## References

Full spec with examples: provided inline during brainstorming session 2026-03-17.
