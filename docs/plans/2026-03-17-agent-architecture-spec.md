# Agent Architecture Specification

**Status:** Approved
**Date:** 2026-03-17

## Summary

Agents are defined by `AgentSpec`, enriched by Skills, Tools and MCP bindings,
bound to an `EngineProfile`, resolved at runtime by an `AgentResolver`,
and executed within `AgentSession`s persisted separately.

## Core Entities

| Entity | Purpose | Format |
|---|---|---|
| `AgentSpec` | Declarative agent definition (role, skills, tools, MCP, permissions) | YAML |
| `SkillSpec` | Reusable behavioral knowledge with SKILL.md | Directory + YAML |
| `ToolSpec` | Executable action with explicit interface | YAML |
| `McpServerBinding` | External system integration via MCP protocol | YAML |
| `EngineProfile` | How the agent runs (provider, model, adapter) | YAML in project config |
| `ResolvedAgentProfile` | Fully resolved agent ready for execution | Runtime object |
| `AgentSession` | Live agent execution instance | Store-persisted |

## Project Structure

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
  pipelines/
    main.py
  .env
```

## Key Design Principles

1. Python-first, declarative when useful
2. Agent is not a persisted object — it's resolved at runtime
3. Capability (what) separated from execution (how)
4. Skills != Tools != MCP — each has distinct role
5. Session state persisted separately from definition
6. Filesystem is initial source of truth
7. CLI imports only miniautogen.api

## Project Config Schema (miniautogen.yaml)

```yaml
project:
  name: my-agent-team
  version: "0.1.0"

defaults:
  engine_profile: gemini_api_default

engine_profiles:
  gemini_api_default:
    kind: api
    provider: gemini
    model: gemini-2.5-pro
    temperature: 0.2

pipelines:
  main:
    target: pipelines.main:build_pipeline
```

## Agent Resolution Flow

1. Load AgentSpec from YAML
2. Resolve attached skills (load SKILL.md + skill.yaml)
3. Resolve allowed tools (load tool specs)
4. Resolve MCP bindings and filter accessible tools
5. Apply project defaults
6. Apply EngineProfile
7. Produce ResolvedAgentProfile

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
miniautogen agent list          # future M2 extension
miniautogen skill list          # future M2 extension
```

## References

Full spec with examples: provided inline during brainstorming session 2026-03-17.
