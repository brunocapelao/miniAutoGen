# Agent Frameworks & Protocols Research (March 2026)

Deep-dive research into 5 major AI agent technologies: Google A2A, Anthropic Agent SDK, ACP (IBM/BeeAI), OpenAI Swarm/Agents SDK, and Google ADK. Conducted for MiniAutoGen architectural alignment.

---

## Table of Contents

1. [Google A2A (Agent-to-Agent Protocol)](#1-google-a2a-agent-to-agent-protocol)
2. [Anthropic Claude Agent SDK](#2-anthropic-claude-agent-sdk)
3. [ACP (Agent Communication Protocol)](#3-acp-agent-communication-protocol)
4. [OpenAI Swarm & Agents SDK](#4-openai-swarm--agents-sdk)
5. [Google ADK (Agent Development Kit)](#5-google-adk-agent-development-kit)
6. [Comparative Analysis](#6-comparative-analysis)
7. [Implications for MiniAutoGen](#7-implications-for-miniautogen)

---

## 1. Google A2A (Agent-to-Agent Protocol)

**Repository**: https://github.com/a2aproject/A2A
**Spec**: https://a2a-protocol.org/latest/specification/
**Status**: Active, Linux Foundation governance. ACP merged into A2A as of Sept 2025.

### 1.1 What It Is

A2A is an **open wire protocol** for communication between opaque agent systems. It is NOT an agent framework -- it defines how independently-built agents discover each other and exchange work. Think of it as "HTTP for agents." Agents remain opaque: they never expose internal reasoning, tools, or memory.

### 1.2 Agent Definition Model

Agents are defined externally via an **AgentCard** -- a JSON metadata document published at `/.well-known/agent.json`. The AgentCard declares:

| Field | Purpose |
|-------|---------|
| `id` | Unique agent identifier |
| `name` | Human-readable name |
| `description` | Capability summary |
| `endpoint` | Service URL |
| `interfaces` | Supported protocol bindings (JSON-RPC, gRPC, HTTP/REST) |
| `capabilities` | Feature flags: `streaming`, `pushNotifications`, `extendedAgentCard` |
| `skills` | Array of `AgentSkill` objects with `inputSchema`/`outputSchema` |
| `securitySchemes` | Auth methods: API key, OAuth2, mTLS, OpenID Connect |
| `extensions` | Custom extension URIs |
| `signature` | Cryptographic authenticity proof |

**AgentSkill** is how agents advertise what they can do:
```
{
  "id": "translate",
  "name": "Translation",
  "description": "Translates text between languages",
  "inputSchema": { ... },
  "outputSchema": { ... },
  "mimeTypes": ["text/plain"]
}
```

### 1.3 Communication Model

A2A is layered into 3 tiers:

1. **Data Model Layer** (protocol-agnostic): Task, Message, Part, Artifact, AgentCard, Extension
2. **Operations Layer** (abstract capabilities): SendMessage, GetTask, CancelTask, etc.
3. **Protocol Bindings** (concrete wire formats): JSON-RPC 2.0, gRPC, HTTP/REST

**Core JSON-RPC Methods:**

| Method | Purpose |
|--------|---------|
| `SendMessage` | Initiate or continue interaction; returns Task or Message |
| `SendStreamingMessage` | Same but with SSE streaming |
| `GetTask` | Retrieve task state and artifacts |
| `ListTasks` | Query tasks with filtering/pagination |
| `CancelTask` | Request cancellation |
| `SubscribeToTask` | Stream updates for existing task |
| `GetExtendedAgentCard` | Authenticated detailed metadata |

Plus push notification CRUD operations for webhooks.

**Message Structure:**
```
Message {
  role: "user" | "agent"
  parts: Part[]  // TextPart, FilePart, DataPart (structured JSON)
}
```

**Part** is the atomic content unit -- supports text, files (via reference or inline), structured data, and embedded artifacts. MIME types make it extensible without protocol changes.

### 1.4 Runtime / Execution Model

A2A structures work as **Tasks** with a lifecycle:

```
CREATED -> WORKING -> COMPLETED
                   -> FAILED
                   -> CANCELED
                   -> REJECTED
           WORKING -> INPUT_REQUIRED -> (client responds) -> WORKING
           WORKING -> AUTH_REQUIRED -> (client authenticates) -> WORKING
```

Tasks produce **Artifacts** (output objects composed of Parts). The `contextId` groups related tasks into conversations.

**Three interaction modes:**
- **Blocking**: SendMessage waits until terminal state
- **Non-blocking**: Returns immediately; poll via GetTask or subscribe
- **Streaming**: SSE stream of `StreamResponse` events (status updates, artifact updates, messages)

### 1.5 Tool Integration Model

A2A does NOT define tools. Agents are opaque -- their tools, reasoning, and memory are internal. A2A only defines the interface between agents. This is by design: "agents collaborate based on declared capabilities and exchanged information, without needing to share their internal thoughts, plans, or tool implementations."

A2A complements MCP: MCP is agent-to-tool, A2A is agent-to-agent.

### 1.6 Extensibility

- **Extension mechanism**: Agents declare extensions via URIs with version and required flags
- **Multi-protocol**: JSON-RPC, gRPC, and HTTP/REST bindings from a single proto definition
- **SDK support**: Python, Go, JavaScript, Java, .NET
- **Framework-agnostic**: Works with ADK, LangGraph, BeeAI, CrewAI, any framework
- **AgentCard signatures**: Cryptographic authenticity via RSA/EC signatures

### 1.7 Strengths

- Extremely well-specified wire protocol with formal proto definition as normative source
- Three protocol bindings (JSON-RPC, gRPC, REST) cover all deployment scenarios
- Rich security model (OAuth2, mTLS, API keys, OpenID Connect)
- Push notifications via webhooks for event-driven architectures
- Task lifecycle with INPUT_REQUIRED/AUTH_REQUIRED enables human-in-the-loop
- Extension mechanism for forward compatibility
- Now the unified standard (absorbed ACP)

### 1.8 Weaknesses

- Only defines the wire protocol, not how to build agents
- No opinion on internal agent architecture, orchestration, or tool use
- Requires implementing a server to expose agents (non-trivial for simple use cases)
- Still relatively new; ecosystem is growing but not yet mature
- No built-in concept of agent memory or shared state between agents

---

## 2. Anthropic Claude Agent SDK

**Repository**: https://github.com/anthropics/claude-agent-sdk-python
**Docs**: https://platform.claude.com/docs/en/agent-sdk/overview
**Status**: Active. Python v0.1.48, TypeScript v0.2.71 (March 2026). Renamed from Claude Code SDK.

### 2.1 What It Is

The Claude Agent SDK packages **Claude Code's agent loop as a library**. The core philosophy: "give Claude access to a computer." It provides the same tools, agent loop, and context management that power Claude Code, embeddable in custom applications.

### 2.2 Agent Definition Model

There is no `Agent` class. Instead, agents are defined implicitly through the `query()` function or `ClaudeSDKClient` with configuration:

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="Find and fix the bug in auth.py",
    options=ClaudeAgentOptions(
        system_prompt="You are a senior engineer",
        allowed_tools=["Read", "Edit", "Bash"],
        max_turns=10,
        cwd="/path/to/project",
        permission_mode='acceptEdits',
    ),
):
    print(message)
```

**Key configuration:**
- `system_prompt`: Agent persona/instructions
- `allowed_tools` / `disallowed_tools`: Tool allowlist/blocklist
- `permission_mode`: 'ask', 'acceptEdits', 'rejectEdits'
- `can_use_tool`: Custom permission callback
- `mcp_servers`: External MCP servers or in-process SDK MCP servers
- `hooks`: Lifecycle callbacks (PreToolUse, PostToolUse, etc.)
- `agents`: Named sub-agent definitions for delegation
- `max_turns`: Execution limit

### 2.3 Communication Model

The SDK operates as a **single-process agent loop** -- not a network protocol. Communication is:
- **Human-to-agent**: Via `query()` prompts
- **Agent-to-subagent**: Via the `Agent` tool (delegation to named subagents)
- **Agent-to-tools**: Via built-in tools + MCP servers

**Subagent delegation:**
```python
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Grep", "Agent"],
    agents={
        "code-reviewer": AgentDefinition(
            description="Expert code reviewer",
            prompt="Analyze code quality and suggest improvements.",
            tools=["Read", "Glob", "Grep"],
        )
    },
)
```

Subagents run in isolated context and return results to the parent. Messages include `parent_tool_use_id` for tracking.

### 2.4 Runtime / Execution Model

The agent operates in a **four-phase feedback loop**:

1. **Gather Context**: Agentic search (grep, file reads), semantic search, subagent delegation, compaction when context is full
2. **Take Action**: Tool execution, bash commands, code generation, MCP calls
3. **Verify Work**: Rules-based evaluation, visual feedback (screenshots), LLM-as-judge
4. **Iterate**: Loop until task completion or max_turns

**Session management**: Stateful via `ClaudeSDKClient` (maintains conversation across turns) or stateless via `query()`. Sessions can be resumed with `session_id`.

**Under the hood**: The SDK spawns a Claude Code CLI process and communicates via stdio JSON. The CLI bundles with the pip package.

### 2.5 Tool Integration Model

**Built-in tools** (same as Claude Code):

| Tool | Purpose |
|------|---------|
| Read | Read files |
| Write | Create files |
| Edit | Precise file edits |
| Bash | Terminal commands |
| Glob | File pattern matching |
| Grep | Content search with regex |
| WebSearch | Web search |
| WebFetch | Fetch/parse web pages |
| AskUserQuestion | Clarifying questions to user |
| Agent | Delegate to subagents |

**Custom tools** via in-process SDK MCP servers (zero subprocess overhead):
```python
@tool("greet", "Greet a user", {"name": str})
async def greet_user(args):
    return {"content": [{"type": "text", "text": f"Hello, {args['name']}!"}]}

server = create_sdk_mcp_server(name="my-tools", tools=[greet_user])
```

Also supports external MCP servers (stdio or SSE transport).

### 2.6 Guardrails / Hooks

**Permission flow**: `allowed_tools` (auto-approve) -> `disallowed_tools` (block) -> `permission_mode` -> `can_use_tool` (custom callable)

**Hook events**: `PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, `SessionEnd`, `UserPromptSubmit`

Hooks can validate, log, block, or transform agent behavior at each lifecycle point. Pattern-matched via `HookMatcher`.

### 2.7 Extensibility

- MCP integration for arbitrary tool servers
- Custom hooks at every lifecycle point
- Subagent definitions for delegation
- Claude Code config integration (CLAUDE.md, skills, slash commands)
- Plugin system for extending with custom commands/agents/MCP servers
- Works with Bedrock, Vertex AI, and Azure AI Foundry

### 2.8 Strengths

- Battle-tested: Same agent loop that powers Claude Code
- Rich built-in tool set -- agents work immediately without custom tool implementation
- Powerful hook system for guardrails and observability
- Subagent delegation with context isolation
- Session persistence and resumption
- MCP ecosystem access (hundreds of integrations)
- In-process MCP servers eliminate subprocess overhead

### 2.9 Weaknesses

- Tightly coupled to Claude (cannot use other LLMs)
- Agent definition is implicit (configuration, not a class hierarchy)
- Under the hood spawns CLI process -- not a pure library
- No inter-agent networking protocol (agents are in-process only)
- Relatively new SDK; API still evolving (v0.1.x)
- No formal multi-agent orchestration patterns (just parent/subagent)

---

## 3. ACP (Agent Communication Protocol)

**Repository**: https://github.com/i-am-bee/acp (archived August 2025)
**Docs**: https://agentcommunicationprotocol.dev
**Status**: Merged into A2A under Linux Foundation as of September 2025. Development wound down.

### 3.1 What It Is

ACP was an open REST-based protocol for agent-to-agent communication, created by IBM Research as part of the BeeAI project. Unlike A2A's JSON-RPC approach, ACP used standard REST/HTTP conventions. As of September 2025, the ACP team joined forces with A2A, contributing their technology to the unified standard.

### 3.2 Agent Definition Model

Agents were defined via an **Agent Manifest** -- metadata describing name, description, and optional capabilities for discovery without exposing implementation.

### 3.3 Communication Model

**REST-based** with standard HTTP conventions:
- `GET /agents` -- Discover available agents
- `POST /runs` -- Execute agent with input messages

**Message structure:**
```
Message {
  role: string
  parts: MessagePart[]
}

MessagePart {
  content_type: string  // MIME type
  content: any          // Payload
  content_encoding: string  // plain, base64, etc.
  content_url: string  // Optional external reference
}
```

**Three communication patterns:**
- **Synchronous**: Request-response
- **Streaming**: Progressive results via generators
- **Interactive (Await)**: Agent pauses, requests input from client, client responds, agent resumes

### 3.4 Runtime / Execution Model

Centered on **Runs** -- a single agent execution:
```
Run {
  run_id: string
  status: "completed" | "awaiting" | "error"
  output: Message[]
  await_request: AwaitRequest?  // Optional pause for input
}
```

**Session support**: Maintains state and conversation history across multiple interactions. Distributed sessions via URI-based resource sharing for horizontal scalability.

**Deployment**: Python/TypeScript SDKs, Redis/PostgreSQL for HA, decorator-based server implementation:
```python
@server.agent()
async def my_agent(input):
    yield Message(role="agent", parts=[TextPart("Hello")])
```

### 3.5 Tool Integration Model

ACP did not define tools -- it focused purely on agent-to-agent communication. Tools were the responsibility of the agent framework (BeeAI, LangChain, CrewAI, etc.).

### 3.6 Extensibility

- MIME-type based content extensibility (no protocol changes for new types)
- Dual discovery: online (active registration) and offline (metadata in packages, scale-to-zero friendly)
- Trajectory metadata for audit trails
- Citation metadata for RAG attribution
- OpenAPI specification (`openapi.yaml`) as the formal definition

### 3.7 Strengths

- Simplest protocol of the three (REST only, no SDK required -- curl/Postman work)
- Async-first with sync support
- Await mechanism for human-in-the-loop
- Distributed session support
- MIME-type extensibility is elegant

### 3.8 Weaknesses

- **Archived** -- merged into A2A. No longer actively developed.
- Less feature-rich than A2A (no gRPC binding, simpler security model)
- Smaller ecosystem than A2A
- No streaming via SSE (used generator patterns instead)

### 3.9 Legacy Value

ACP's contributions to A2A include the REST/HTTP binding, the await/resume interaction pattern, and MIME-type content extensibility. Understanding ACP helps understand A2A's REST binding layer.

---

## 4. OpenAI Swarm & Agents SDK

**Swarm Repository**: https://github.com/openai/swarm
**Agents SDK Docs**: https://openai.github.io/openai-agents-python/
**Status**: Swarm is educational/archived. OpenAI Agents SDK (March 2025) is the production successor.

### 4.1 What They Are

**Swarm** was an educational framework exploring lightweight multi-agent orchestration with just two primitives: Agents and Handoffs. It was explicitly not production-ready.

**OpenAI Agents SDK** is Swarm's production evolution, adding guardrails, tracing, sessions, and structured outputs while maintaining the same philosophy of minimal abstractions.

### 4.2 Agent Definition Model

**Swarm (educational):**
```python
agent = Agent(
    name="Refund Agent",
    instructions="You handle refund requests...",
    functions=[process_refund, check_status],
    model="gpt-4o",
)
```

**Agents SDK (production):**
```python
from agents import Agent, function_tool

@function_tool
def get_weather(city: str) -> str:
    return f"Sunny in {city}"

agent = Agent(
    name="Weather Agent",
    instructions="You help with weather queries",
    tools=[get_weather],
    handoffs=[specialist_agent],
    output_type=WeatherReport,  # Pydantic model for structured output
    input_guardrails=[safety_check],
    output_guardrails=[quality_check],
    model="gpt-4o",
    model_settings=ModelSettings(temperature=0.7),
)
```

**Key Agent parameters:**
- `name`, `instructions` (static string or dynamic function)
- `tools`: Function tools, MCP tools, agents-as-tools
- `handoffs`: Other agents this agent can delegate to
- `output_type`: Pydantic model for structured output
- `input_guardrails` / `output_guardrails`: Validation checks
- `hooks`: Agent-scoped lifecycle callbacks
- `model_settings`: Temperature, tool_choice, etc.
- `tool_use_behavior`: "run_llm_again", "stop_on_first_tool", `StopAtTools`, custom function
- `handoff_description`: Description when this agent is a handoff target
- `.clone()`: Create variants with property overrides

### 4.3 Communication Model (Handoffs)

Handoffs are the core multi-agent coordination mechanism. They are represented as **tools to the LLM** -- a handoff to "Refund Agent" becomes a callable tool named `transfer_to_refund_agent`.

**How handoffs work:**
1. Agent A has `handoffs=[agent_b]`
2. LLM decides to call `transfer_to_refund_agent` tool
3. Conversation history is passed to Agent B
4. Agent B takes over completely (no return to A)

**Customization via `handoff()` function:**
```python
handoff(
    agent=refund_agent,
    tool_name_override="escalate_to_refunds",
    tool_description_override="Use when customer wants a refund",
    on_handoff=lambda ctx: fetch_customer_data(ctx),  # Pre-handoff callback
    input_type=HandoffMetadata,  # Pydantic model for metadata at handoff time
    input_filter=remove_all_tools,  # Filter conversation history
    is_enabled=lambda ctx: ctx.context.can_escalate,  # Runtime toggle
)
```

**Key insight**: Handoffs transfer control completely. For manager-style orchestration (where a central agent delegates and gets results back), use **agents-as-tools** instead:
```python
manager = Agent(
    name="Manager",
    tools=[research_agent.as_tool(
        tool_name="research",
        tool_description="Research a topic"
    )],
)
```

### 4.4 Runtime / Execution Model

**Swarm**: `client.run()` implements a synchronous loop: get completion -> execute tools -> handoff if needed -> repeat until no more tool calls.

**Agents SDK**: `Runner.run_sync()` or `Runner.run()` (async) with:
- Built-in agent loop handling tool invocation and LLM calls
- Automatic tool result forwarding
- Tracing for debugging and monitoring
- Session persistence for multi-turn context

**Context management**: Generic `Agent[ContextType]` -- context objects inject dependencies/state, accessed in tools, handoffs, and callbacks via `RunContextWrapper`.

### 4.5 Tool Integration Model

**Function tools**: Python functions with `@function_tool` decorator. Automatic schema generation from type hints, Pydantic validation.

**MCP tools**: Built-in MCP integration, functions identically to function tools.

**Agents as tools**: `agent.as_tool()` wraps a sub-agent as a callable tool (manager pattern).

### 4.6 Guardrails

**Three types:**

| Type | When | Scope |
|------|------|-------|
| Input guardrails | Before agent runs | First agent only |
| Output guardrails | After agent output | Final agent only |
| Tool guardrails | Around tool invocation | Every tool call |

Input guardrails support **parallel execution** (run alongside agent for latency) or **blocking** (complete before agent starts). Output guardrails always run after.

**Tripwire mechanism**: When a guardrail fails, it raises `InputGuardrailTripwireTriggered` or `OutputGuardrailTripwireTriggered`, immediately halting execution.

Guardrails can internally run sub-agents for sophisticated validation.

### 4.7 Extensibility

- Function tools with automatic schema generation
- MCP server integration
- Agents-as-tools for composition
- Custom guardrails with sub-agent validation
- Agent cloning for variants
- Dynamic instructions via callbacks
- Built-in tracing compatible with OpenAI's eval/fine-tuning tools
- Realtime voice agents with speech-to-text pipelines
- Provider-agnostic (documented paths for non-OpenAI models)

### 4.8 Strengths

- Extremely clean API with minimal abstractions (4 primitives: Agents, Handoffs, Guardrails, Tools)
- Two distinct multi-agent patterns: handoffs (transfer control) vs agents-as-tools (delegation)
- Guardrails with parallel execution and tripwire mechanism
- Built-in tracing and observability
- Structured outputs via Pydantic
- Provider-agnostic design
- Session persistence
- Handoff input filters for controlling conversation history

### 4.9 Weaknesses

- No formal inter-agent networking protocol (in-process only, like Claude Agent SDK)
- Handoffs are one-way -- no built-in "return to caller" pattern
- OpenAI-centric despite being "provider-agnostic"
- No built-in file/shell tools (unlike Claude Agent SDK)
- Guardrails only run at boundaries (first/last agent), not at every agent in chain
- No workflow agents (sequential, parallel, loop) -- everything is LLM-driven

---

## 5. Google ADK (Agent Development Kit)

**Docs**: https://google.github.io/adk-docs/
**Status**: Active. Python, TypeScript, Go, Java SDKs.

### 5.1 What It Is

ADK is a **full agent framework** for building, deploying, and orchestrating AI agents. It is model-agnostic, deployment-agnostic, and designed for compatibility with other frameworks. ADK is complementary to A2A: ADK builds agents, A2A connects them.

### 5.2 Agent Definition Model

All agents extend `BaseAgent`. Three primary types:

**LlmAgent** (non-deterministic, language-driven):
```python
agent = LlmAgent(
    name="research_agent",
    model="gemini-2.5-flash",
    description="Researches topics using web search",
    instruction="You are a research assistant. Use search tools to find information.",
    tools=[google_search, summarize],
    output_key="research_result",  # Stores output in session state
    generate_content_config=GenerateContentConfig(temperature=0.3),
    include_contents='default',  # Whether to include conversation history
    sub_agents=[detail_agent],
)
```

**Key LlmAgent parameters:**
- `model`: LLM identifier
- `name`: Unique identifier (critical in multi-agent systems)
- `description`: Used by other agents for routing decisions
- `instruction`: Core behavioral prompt (supports `{var}` dynamic state insertion)
- `tools`: Functions, BaseTool, AgentTool instances
- `output_key`: Saves final response to session state under this key
- `input_schema` / `output_schema`: Structured I/O
- `include_contents`: 'default' or 'none' (history inclusion)
- `planner`: Multi-step reasoning
- `code_executor`: Code block execution

**Workflow Agents** (deterministic orchestration):
- `SequentialAgent(sub_agents=[a, b, c])` -- Execute in order
- `ParallelAgent(sub_agents=[a, b, c])` -- Execute concurrently
- `LoopAgent(sub_agents=[a, b], max_iterations=5)` -- Repeat until condition/limit

**Custom Agents**: Extend `BaseAgent` directly for unique logic.

### 5.3 Communication Model (Multi-Agent)

Three coordination mechanisms:

**1. Shared Session State:**
Agents sharing an `InvocationContext` access the same `session.state`. One agent writes via `output_key`, subsequent agents read. Passive, asynchronous data exchange.

**2. LLM-Driven Delegation (Agent Transfer):**
LLM agents generate `transfer_to_agent(agent_name='target')` function calls. The framework's AutoFlow intercepts, locates the target via `root_agent.find_agent()`, and switches context. Requires clear `instructions` on when to transfer and distinct `description` on target agents.

**3. Explicit Invocation (AgentTool):**
Wrap agents in `AgentTool` to treat them as callable functions. The framework runs the target agent, captures its response, and forwards state/artifact changes back to the parent context.

### 5.4 Runtime / Execution Model

**Event loop** with yield/pause/resume cycle. Agents can suspend and resume from saved state.

**Three execution interfaces:**
- `adk web` -- Browser-based UI
- `adk run` -- CLI interaction
- `adk api_server` -- RESTful API

**Session management**: Sessions with rewinding and migration. State persists within invocations, isolated between invocations.

**Deployment options**: Local, Vertex AI Agent Engine, Cloud Run, GKE, Docker.

### 5.5 Tool Integration Model

The richest tool ecosystem of all 5 technologies:

| Tool Type | Description |
|-----------|-------------|
| **Function Tools** | Python/TS/Go/Java functions, auto-wrapped |
| **MCP Tools** | Model Context Protocol integration, MCP Toolbox for Databases (30+ data sources) |
| **OpenAPI Tools** | Generated from OpenAPI specifications |
| **Agents as Tools** | AgentTool wraps agents as callable tools |
| **Code Execution** | Run AI-generated code in sandbox |
| **Computer Use** | UI automation tools |
| **Built-in** | Google Search, Vertex AI Search |
| **Third-party** | 60+ pre-built integrations (BigQuery, MongoDB, GitHub, Slack, etc.) |

### 5.6 Multi-Agent Patterns

ADK documents 6 canonical patterns:

| Pattern | Implementation |
|---------|---------------|
| **Coordinator/Dispatcher** | Central LlmAgent routes to specialized sub-agents |
| **Sequential Pipeline** | SequentialAgent chains agents, shared state via output_key |
| **Parallel Fan-Out/Gather** | ParallelAgent for concurrent work + sequential aggregator |
| **Hierarchical Decomposition** | Multi-level agent trees with downward delegation |
| **Generator-Critic** | Sequential: one generates, one reviews |
| **Iterative Refinement** | LoopAgent with escalation conditions |

**Parent-child hierarchy**: `sub_agents` parameter establishes the tree. An agent instance can only have one parent (`ValueError` on double-assignment). The hierarchy defines scope for workflow orchestration and influences delegation targets.

### 5.7 Extensibility

- Model-agnostic (primarily Gemini but supports others)
- Deployment-agnostic (local, cloud, container)
- Multi-language (Python, TypeScript, Go, Java)
- Built-in evaluation framework with test cases
- Context caching and compression
- Memory persistence
- Callbacks at execution lifecycle points
- A2A compatibility for exposing agents as network services
- Plugin/integration ecosystem (60+ integrations)

### 5.8 Strengths

- Most complete agent framework: covers definition, orchestration, tools, deployment, evaluation
- Three agent types (LLM, Workflow, Custom) for different determinism needs
- Richest tool ecosystem (60+ integrations, MCP, OpenAPI, code execution)
- Formal multi-agent patterns with both LLM-driven and deterministic orchestration
- Shared session state enables clean data pipelines
- A2A-compatible for inter-system communication
- Multi-language support
- Built-in evaluation framework

### 5.9 Weaknesses

- Complexity: large API surface with many concepts
- Gemini-centric despite claiming model-agnosticism
- Google Cloud-centric deployment options
- Parent hierarchy is rigid (single-parent constraint)
- `output_schema` + `tools` only works with specific models (Gemini 3.0+)
- Newer Java/Go SDKs may lag behind Python/TypeScript features

---

## 6. Comparative Analysis

### 6.1 Technology Category Matrix

| Technology | Category | Scope |
|-----------|----------|-------|
| **A2A** | Wire Protocol | Agent-to-agent communication |
| **Claude Agent SDK** | Agent Runtime | Single-agent with subagent delegation |
| **ACP** | Wire Protocol | Agent-to-agent communication (archived, merged into A2A) |
| **OpenAI Agents SDK** | Agent Framework | Multi-agent orchestration |
| **Google ADK** | Agent Framework | Full lifecycle: build, orchestrate, deploy, evaluate |

### 6.2 Agent Definition Comparison

| Aspect | A2A | Claude Agent SDK | ACP | OpenAI Agents SDK | Google ADK |
|--------|-----|-----------------|-----|-------------------|------------|
| Definition unit | AgentCard (JSON) | ClaudeAgentOptions | Agent Manifest | Agent class | LlmAgent / WorkflowAgent / BaseAgent |
| Has agent class? | No (protocol only) | No (config-driven) | No (protocol only) | Yes | Yes (hierarchy) |
| Instructions | N/A | system_prompt | N/A | instructions (str/fn) | instruction (str/fn with {var}) |
| Structured output | Via outputSchema in skills | No | Via MIME types | output_type (Pydantic) | output_schema + output_key |
| Discovery | /.well-known/agent.json | N/A (in-process) | GET /agents | N/A (in-process) | N/A (in-process) or A2A |

### 6.3 Communication Comparison

| Aspect | A2A | Claude Agent SDK | ACP | OpenAI Agents SDK | Google ADK |
|--------|-----|-----------------|-----|-------------------|------------|
| Transport | HTTP(S) + JSON-RPC/gRPC/REST | stdio (CLI process) | HTTP REST | In-process | In-process + A2A |
| Agent-to-agent | Network protocol | Subagent tool | Network protocol | Handoffs / agents-as-tools | transfer_to_agent / AgentTool / shared state |
| Streaming | SSE | Async iterator | Generator | Async iterator | Event stream |
| Human-in-loop | INPUT_REQUIRED state | AskUserQuestion tool | Await mechanism | Guardrail tripwire | Escalation events |

### 6.4 Orchestration Comparison

| Pattern | A2A | Claude Agent SDK | OpenAI Agents SDK | Google ADK |
|---------|-----|-----------------|-------------------|------------|
| Sequential | N/A | Manual | Via handoff chain | SequentialAgent |
| Parallel | N/A | Subagent delegation | N/A | ParallelAgent |
| Loop/Retry | N/A | Agent loop (iterate) | N/A | LoopAgent |
| Hierarchical | N/A | Parent/subagent | Handoffs + agents-as-tools | sub_agents tree |
| Coordinator | N/A | Manual | Agent with handoffs | LlmAgent as router |
| Fan-out/gather | N/A | Manual | N/A | ParallelAgent + aggregator |

### 6.5 Tool Integration Comparison

| Aspect | A2A | Claude Agent SDK | OpenAI Agents SDK | Google ADK |
|--------|-----|-----------------|-------------------|------------|
| Built-in tools | None | Read/Write/Edit/Bash/Glob/Grep/Web | None | Search, Code Execution |
| Custom functions | N/A | @tool decorator + MCP server | @function_tool decorator | Native functions / FunctionTool |
| MCP support | N/A | Yes (in-process + external) | Yes | Yes + MCP Toolbox |
| OpenAPI | N/A | No | No | Yes |
| Agents as tools | N/A | Agent tool (delegation) | agent.as_tool() | AgentTool wrapper |
| Pre-built integrations | N/A | MCP ecosystem | MCP ecosystem | 60+ native integrations |

### 6.6 Safety & Guardrails Comparison

| Aspect | Claude Agent SDK | OpenAI Agents SDK | Google ADK |
|--------|-----------------|-------------------|------------|
| Permission model | allowed/disallowed tools + permission_mode + can_use_tool | input/output/tool guardrails | Callbacks |
| Pre-execution check | PreToolUse hook | Input guardrails (parallel or blocking) | Before-tool callbacks |
| Post-execution check | PostToolUse hook | Output guardrails | After-tool callbacks |
| Fail-fast | Hook can deny | Tripwire raises exception | Callback can escalate |
| Sub-agent validation | No | Guardrails can run sub-agents | No |

---

## 7. Implications for MiniAutoGen

> Os padrões identificados nesta pesquisa mapeiam directamente para a arquitectura do MiniAutoGen: Engines abstraem providers heterogéneos, Flows implementam os modos de coordenação (Workflow, Agentic Loop, Deliberation, Composite), e Interceptors/Policies operam lateralmente como middleware composável. A tese "o agente é commodity, o runtime é o produto" é reforçada pela convergência dos protocolos analisados para separação entre agente e orquestração.

### 7.1 Protocol Layer

**Recommendation**: Align with A2A for inter-agent communication. A2A is the clear winner as the unified standard (absorbed ACP, backed by Google + Linux Foundation). Key concepts to adopt:
- AgentCard model for capability advertisement
- Task lifecycle (CREATED -> WORKING -> COMPLETED/FAILED/INPUT_REQUIRED)
- Message/Part content model with MIME-type extensibility
- Support JSON-RPC and/or REST bindings

### 7.2 Agent Definition

**Best patterns observed:**
- Google ADK's three-tier agent hierarchy (LLM, Workflow, Custom) is the most complete model
- OpenAI's minimal 4-primitive approach (Agents, Handoffs, Guardrails, Tools) offers the best ergonomics
- ADK's `instruction` with `{var}` state interpolation is a clean pattern
- ADK's `output_key` for automatic state persistence is elegant for pipelines

**For MiniAutoGen**: The existing PipelineRunner (executor de Flows) + component model aligns well with ADK's SequentialAgent/ParallelAgent patterns. Consider:
- LLM-driven agents that can transfer control (like ADK/OpenAI handoffs)
- Deterministic workflow agents (already covered by PipelineRunner)
- Agent metadata (name, description, skills) for discovery and routing

### 7.3 Orchestration

**Best patterns:**
- ADK's 6 canonical patterns (Coordinator, Sequential, Parallel, Hierarchical, Generator-Critic, Iterative Refinement)
- OpenAI's clean distinction between handoffs (transfer control) and agents-as-tools (delegation with return)
- ADK's shared session state for data pipeline patterns

### 7.4 Tool Integration

**Best patterns:**
- MCP as the standard for tool integration (used by Claude, OpenAI, ADK)
- Function tools with automatic schema generation (OpenAI and ADK)
- In-process MCP servers for zero-overhead custom tools (Claude Agent SDK)

### 7.5 Guardrails

**Best patterns:**
- OpenAI's tripwire mechanism with parallel execution
- Claude Agent SDK's hook system (more lifecycle points)
- Both are superior to simple callback-only approaches

### 7.6 Key Architectural Takeaways

1. **Protocols vs Frameworks**: A2A/ACP are wire protocols; the SDKs are frameworks. MiniAutoGen needs both: a clean internal agent model AND ability to expose/consume agents via A2A.

2. **Opacity is good**: A2A's core insight -- agents should be opaque to each other. This aligns with MiniAutoGen's adapter isolation principle.

3. **Two delegation patterns**: Transfer (handoff, one-way) vs Invocation (tool, returns). Both are needed for different use cases.

4. **Deterministic + LLM orchestration**: ADK's combination of workflow agents (deterministic) and LLM agents (adaptive) is the most flexible model. MiniAutoGen already has PipelineRunner for deterministic; needs LLM-driven routing.

5. **MCP is universal**: All three major framework providers (Anthropic, OpenAI, Google) support MCP for tool integration. MiniAutoGen should too.

6. **Session state is the coordination primitive**: ADK's shared state model (write via output_key, read via state) is the cleanest pattern for multi-agent data flow within a single system.

---

## Sources

- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [A2A GitHub Repository](https://github.com/a2aproject/A2A)
- [Google A2A Announcement](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [Claude Agent SDK Overview](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Claude Agent SDK Python GitHub](https://github.com/anthropics/claude-agent-sdk-python)
- [Building Agents with Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)
- [ACP GitHub (archived)](https://github.com/i-am-bee/acp)
- [ACP Documentation](https://agentcommunicationprotocol.dev/introduction/welcome)
- [ACP - IBM Research](https://research.ibm.com/projects/agent-communication-protocol)
- [ACP - IBM Think](https://www.ibm.com/think/topics/agent-communication-protocol)
- [OpenAI Swarm GitHub](https://github.com/openai/swarm)
- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK Review (Dec 2025)](https://mem0.ai/blog/openai-agents-sdk-review)
- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [ADK Agent Types](https://google.github.io/adk-docs/agents/)
- [ADK Multi-Agent Architecture](https://google.github.io/adk-docs/agents/multi-agents/)
- [ADK LLM Agents](https://google.github.io/adk-docs/agents/llm-agents/)
- [ADK Integrations](https://google.github.io/adk-docs/integrations/)
- [AI Agent Protocols 2026 Guide](https://www.ruh.ai/blogs/ai-agent-protocols-2026-complete-guide)
- [MCP, ACP, and A2A - Camunda](https://camunda.com/blog/2025/05/mcp-acp-a2a-growing-world-inter-agent-communication/)
