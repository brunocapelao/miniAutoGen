# Manual do MiniAutoGen MVP

> Orquestre múltiplos agentes de IA de qualquer provider com configuração YAML e um único comando.

Este manual cobre tudo o que você precisa para instalar, configurar e executar fluxos multi-agente com o MiniAutoGen. Ao final, você será capaz de criar um workspace, configurar engines e agentes, e executar flows nos 3 modos de coordenação — tudo sem escrever uma linha de Python.

---

## Sumário

1. [O que é o MiniAutoGen](#1-o-que-é-o-miniautogen)
2. [Instalação](#2-instalação)
3. [Quick start](#3-quick-start)
4. [Conceitos fundamentais](#4-conceitos-fundamentais)
5. [Configuração do workspace](#5-configuração-do-workspace)
6. [Engines — conexão com providers](#6-engines--conexão-com-providers)
7. [Agents — engines com superpoderes](#7-agents--engines-com-superpoderes)
8. [Flows — como agentes colaboram](#8-flows--como-agentes-colaboram)
9. [Builtin tools — ferramentas do runtime](#9-builtin-tools--ferramentas-do-runtime)
10. [Memória persistente](#10-memória-persistente)
11. [CLI reference](#11-cli-reference)
12. [Exemplos práticos](#12-exemplos-práticos)
13. [Server e gateway](#13-server-e-gateway)
14. [TUI — dashboard interativo](#14-tui--dashboard-interativo)
15. [SDK — uso programático](#15-sdk--uso-programático)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. O que é o MiniAutoGen

O MiniAutoGen é um **runtime Python de orquestração multi-agente multi-provider**. Ele não reinventa o agente — orquestra agentes reais de qualquer provider (OpenAI, Anthropic, Google, CLI agents, servidores locais) em flows customizados.

### O modelo mental

```
Workspace (miniautogen.yaml)
├── Engines        — conexão com agentes externos (OpenAI, Claude, Gemini, CLI)
├── Agents         — Engines enriquecidos com tools, memória, sandbox, delegação
├── Flows          — como os Agents colaboram (workflow, deliberation, loop)
└── Server/Gateway — como o mundo externo interage com o Workspace
```

### O que o runtime adiciona ao agente

O engine (provider) fornece a inteligência. O runtime adiciona:

- **Builtin tools** — read_file, search_codebase, list_directory com sandbox
- **Memória persistente** — contexto entre execuções
- **Sandbox** — isolamento de filesystem por agente
- **Delegação** — agentes podem delegar tarefas entre si
- **Observabilidade** — 69 tipos de eventos tipados
- **Policies** — retry, budget, timeout, approval

---

## 2. Instalação

### Requisitos

- Python 3.11 ou superior
- pip ou uv

### Instalação básica

```bash
pip install miniautogen
```

### Com providers específicos

```bash
# Apenas OpenAI
pip install miniautogen[openai]

# Apenas Anthropic
pip install miniautogen[anthropic]

# Apenas Google
pip install miniautogen[google]

# Todos os providers
pip install miniautogen[all-providers]

# Tudo (providers + TUI dashboard)
pip install miniautogen[all]
```

### Verificar instalação

```bash
miniautogen doctor
```

Este comando verifica: versão do Python, dependências instaladas, API keys configuradas e acessibilidade do gateway.

---

## 3. Quick start

### Passo 1 — Criar um workspace

```bash
miniautogen init meu-projeto
cd meu-projeto
```

Isso cria a seguinte estrutura:

```
meu-projeto/
├── miniautogen.yaml        ← Configuração principal
├── agents/
│   └── researcher.yaml     ← Agente de exemplo
├── skills/
│   └── example/
├── tools/
│   └── web_search.yaml
├── memory/
│   └── profiles.yaml
├── pipelines/
│   └── main.py             ← Pipeline callable (Python)
├── mcp/
├── .miniautogen/
│   ├── agents/             ← Config por agente (tools, memória, prompt)
│   └── shared/
├── .env                    ← Variáveis de ambiente
└── .gitignore
```

### Passo 2 — Configurar uma API key

Edite `.env` com a chave do seu provider:

```bash
# Escolha um:
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...
```

### Passo 3 — Configurar o engine

Edite `miniautogen.yaml`:

```yaml
engines:
  default_api:
    kind: api
    provider: "openai"        # ou "anthropic" ou "google"
    model: "gpt-4o-mini"     # ou "claude-sonnet-4-20250514" ou "gemini-2.5-flash"
    temperature: 0.2
```

### Passo 4 — Criar um flow config-driven

Adicione ao `miniautogen.yaml`:

```yaml
flows:
  main:
    mode: workflow
    participants:
      - researcher
```

### Passo 5 — Executar

```bash
miniautogen run main --input "Explique o que é orquestração multi-agente"
```

O MiniAutoGen vai:
1. Carregar a configuração do workspace
2. Criar um AgentRuntime para o agente "researcher"
3. Conectar ao engine (OpenAI/Anthropic/Google)
4. Executar o flow no modo workflow
5. Exibir o resultado

---

## 4. Conceitos fundamentais

### Workspace

O workspace é a raiz do seu projeto. Contém o `miniautogen.yaml` e todos os artefatos (agents, tools, memória). Cada workspace é independente.

### Engine

O engine é a **conexão com um agente externo**. Pode ser:

| Tipo | Provider | Exemplo |
|------|----------|---------|
| API stateless | OpenAI, Anthropic, Google | Chamada REST para gerar completions |
| API compatível | Groq, DeepSeek, Mistral, Together, Ollama, LM Studio | Qualquer endpoint OpenAI-compatible |
| CLI stateful | Claude Code, Gemini CLI, Codex CLI | Subprocesso com stdin/stdout |

O engine é **commodity** — o runtime é o produto. Você pode trocar de provider em uma linha.

### Agent

O agent é um **engine enriquecido com superpoderes**:

```
Agent = Engine + Tools + Memória + Sandbox + Delegação + Hooks
```

O engine fornece a inteligência. O runtime adiciona governança, observabilidade e coordenação.

### Flow

O flow define **como múltiplos agents colaboram**. Três modos nativos:

| Modo | Quando usar |
|------|-------------|
| **Workflow** | Tarefas sequenciais — cada agente executa seu step |
| **Deliberation** | Revisão por pares — contribuição, review, consolidação |
| **Loop** | Conversação livre — um router decide quem fala a seguir |

---

## 5. Configuração do workspace

O arquivo `miniautogen.yaml` é a configuração central.

### Estrutura completa

```yaml
# Metadata do projeto
project:
  name: "meu-projeto"
  version: "0.1.0"

# Defaults globais
defaults:
  engine: default_api            # Engine padrão para agentes sem engine_profile
  memory_profile: default        # Perfil de memória padrão

# Engines (conexões com providers)
engines:
  default_api:
    kind: api
    provider: "openai"
    model: "gpt-4o-mini"
    temperature: 0.2

  claude:
    kind: api
    provider: "anthropic"
    model: "claude-sonnet-4-20250514"
    temperature: 0.3

  gemini:
    kind: api
    provider: "google"
    model: "gemini-2.5-flash"

  claude_code:
    kind: cli
    provider: "claude-code"
    command: "claude"

# Perfis de memória
memory_profiles:
  default:
    session: true
    retrieval:
      enabled: false
    compaction:
      enabled: false

# Flows (como agentes colaboram)
flows:
  review:
    mode: deliberation
    participants:
      - researcher
      - reviewer
    leader: reviewer
    max_rounds: 3

  research:
    mode: workflow
    participants:
      - researcher

# Banco de dados (opcional)
database:
  url: sqlite+aiosqlite:///miniautogen.db
```

---

## 6. Engines — conexão com providers

### Providers suportados

| Provider | `provider` | `kind` | Dependência |
|----------|-----------|--------|-------------|
| OpenAI | `openai` | `api` | `pip install miniautogen[openai]` |
| Anthropic | `anthropic` | `api` | `pip install miniautogen[anthropic]` |
| Google Gemini | `google` | `api` | `pip install miniautogen[google]` |
| OpenAI-compatível | `openai-compat` | `api` | Nenhuma extra |
| Claude Code | `claude-code` | `cli` | `claude` CLI instalado |
| Gemini CLI | `gemini-cli` | `cli` | `gemini` CLI instalado |
| Codex CLI | `codex-cli` | `cli` | `codex` CLI instalado |

### Engines API (stateless)

```yaml
engines:
  meu_openai:
    kind: api
    provider: "openai"
    model: "gpt-4o"
    temperature: 0.3
    max_tokens: 4096
    timeout_seconds: 120
    max_retries: 3
```

A API key vem da variável de ambiente `OPENAI_API_KEY` (ou `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`).

### Engines OpenAI-compatível (Groq, Ollama, etc.)

```yaml
engines:
  groq:
    kind: api
    provider: "openai-compat"
    model: "llama-3.1-70b-versatile"
    endpoint: "https://api.groq.com/openai/v1"
    api_key: "${GROQ_API_KEY}"

  ollama_local:
    kind: api
    provider: "openai-compat"
    model: "llama3.2"
    endpoint: "http://localhost:11434/v1"
```

### Engines CLI (stateful)

```yaml
engines:
  claude_code:
    kind: cli
    provider: "claude-code"
    command: "claude"     # Opcional — usa default do provider

  gemini_cli:
    kind: cli
    provider: "gemini-cli"
```

### Auto-discovery de engines

O MiniAutoGen descobre engines automaticamente a partir de:

1. **Variáveis de ambiente** — `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `TOGETHER_API_KEY`, `MISTRAL_API_KEY`
2. **Servidores locais** — Ollama (porta 11434), LM Studio (porta 1234), servidor local (porta 8080)

Para ver os engines disponíveis:

```bash
miniautogen engine discover
```

### Gerenciar engines via CLI

```bash
# Criar (modo interativo — preenche campos faltantes)
miniautogen engine create meu-engine --provider openai --model gpt-4o

# Listar
miniautogen engine list

# Detalhes
miniautogen engine show meu-engine

# Atualizar
miniautogen engine update meu-engine --temperature 0.5

# Remover
miniautogen engine delete meu-engine --confirm
```

---

## 7. Agents — engines com superpoderes

### Configuração do agente

Cada agente é um arquivo YAML em `agents/`:

```yaml
# agents/researcher.yaml
id: researcher
version: "1.0.0"
name: Research Specialist
description: >
  Agente especializado em pesquisa e síntese estruturada.

role: Research Specialist
goal: >
  Investigar tópicos, localizar fontes confiáveis e produzir resumos.

# Engine a usar
engine_profile: default_api

# Acesso a tools
tool_access:
  mode: allowlist       # allowlist | denylist | all
  allow:
    - web_search
    - read_file
    - search_codebase

# Memória
memory:
  profile: default
  session_memory: true
  max_context_tokens: 16000

# Delegação
delegation:
  allow_delegation: false
  can_delegate_to: []
  max_depth: 3

# Runtime
runtime:
  max_turns: 10
  timeout_seconds: 300
```

### Per-agent config directory

Cada agente pode ter configuração avançada em `.miniautogen/agents/{nome}/`:

```
.miniautogen/agents/researcher/
├── prompt.md           ← System prompt (override do role/goal/backstory)
├── tools.yml           ← Tools adicionais do agente
└── memory/             ← Memória persistente do agente
    └── context.json
```

**prompt.md** — Se existe, substitui completamente o system prompt gerado a partir de `role`, `goal` e `backstory`. Use quando precisa de controle total:

```markdown
# Research Specialist

Você é um especialista em pesquisa acadêmica. Suas responsabilidades:

1. Investigar o tópico solicitado usando fontes primárias
2. Validar informações cruzando múltiplas fontes
3. Produzir um resumo estruturado com referências

## Regras
- Sempre cite suas fontes
- Prefira artigos peer-reviewed
- Se não tiver certeza, diga explicitamente
```

### Gerenciar agentes via CLI

```bash
# Criar (modo interativo)
miniautogen agent create reviewer --role "Code Reviewer" --goal "Revisar código" --engine claude

# Listar
miniautogen agent list

# Detalhes
miniautogen agent show researcher

# Atualizar
miniautogen agent update researcher --temperature 0.5

# Remover
miniautogen agent delete reviewer --confirm
```

---

## 8. Flows — como agentes colaboram

### Modo Workflow — tarefas sequenciais

Cada agente executa seu step na ordem definida. Ideal para pipelines onde o output de um alimenta o próximo.

```yaml
flows:
  pipeline_pesquisa:
    mode: workflow
    participants:
      - researcher     # Step 1: pesquisa
      - writer         # Step 2: escreve com base na pesquisa
      - reviewer       # Step 3: revisa o resultado
```

```bash
miniautogen run pipeline_pesquisa --input "Escreva um artigo sobre IA generativa"
```

### Modo Deliberation — revisão por pares

Múltiplos rounds de contribuição → review → refinamento. Um leader consolida.

```yaml
flows:
  revisao_codigo:
    mode: deliberation
    participants:
      - developer
      - security_expert
      - architect
    leader: architect       # Obrigatório: quem consolida
    max_rounds: 3           # Até 3 rounds de revisão
```

```bash
miniautogen run revisao_codigo --input "Revisar a implementação do módulo de autenticação"
```

### Modo Loop — conversação roteada

Um router decide quem fala a seguir. Ideal para conversações livres ou resolução iterativa.

```yaml
flows:
  debug_session:
    mode: loop
    participants:
      - debugger
      - tester
      - fixer
    router: debugger        # Obrigatório: quem roteia
    max_turns: 20           # Máximo de turnos
```

```bash
miniautogen run debug_session --input "Investigar o bug #1234 no módulo de pagamentos"
```

### Flows callable (Python)

Para casos avançados, defina o flow como código Python:

```yaml
flows:
  custom:
    target: pipelines.main:build_pipeline
```

O target aponta para uma função que retorna um objeto com `async def run(state)`.

### Gerenciar flows via CLI

```bash
# Criar workflow
miniautogen flow create meu-flow --mode workflow --participants researcher,writer

# Criar deliberation
miniautogen flow create revisao --mode deliberation --participants dev,reviewer --leader reviewer

# Listar
miniautogen flow list

# Detalhes
miniautogen flow show meu-flow

# Remover
miniautogen flow delete meu-flow --confirm
```

---

## 9. Builtin tools — ferramentas do runtime

Quando o agente usa um engine API (OpenAI, Anthropic, Google), o runtime fornece 3 tools builtin que permitem ao agente interagir com o filesystem do workspace.

### read_file

Lê um arquivo do workspace com linhas numeradas.

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `path` | string | sim | Caminho relativo ao workspace |
| `offset` | integer | não | Linha inicial (0-based) |
| `limit` | integer | não | Máximo de linhas |

**Limites:** 1 MB máximo sem `limit`. Arquivos maiores exigem `offset`/`limit`.

### search_codebase

Busca por um padrão em arquivos do workspace.

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `pattern` | string | sim | Padrão de busca |
| `glob` | string | não | Filtro de arquivos (default: `*`) |
| `max_results` | integer | não | Máximo de matches (default: 50, max: 200) |

**Limites:** 200 resultados máximos. Linhas truncadas a 500 caracteres.

### list_directory

Lista entradas de um diretório com indicador de tipo.

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `path` | string | não | Caminho relativo (default: `.`) |

**Limites:** 1000 entradas máximas.

### Segurança

Todos os builtin tools respeitam o **AgentFilesystemSandbox**:
- Agentes só leem dentro do workspace
- Agentes não leem config de outros agentes
- Path traversal (`../`) é bloqueado
- Symlinks que apontam para fora do workspace são rejeitados

### Tools customizados

Você pode adicionar tools por agente em `.miniautogen/agents/{nome}/tools.yml`:

```yaml
tools:
  - name: formatar_relatorio
    description: Formata o relatório em markdown
    script: scripts/formatar.sh
    parameters:
      type: object
      properties:
        formato:
          type: string
          enum: [markdown, html, pdf]
      required: [formato]
```

Scripts recebem parâmetros via stdin (JSON) e retornam resultado via stdout.

---

## 10. Memória persistente

Cada agente mantém memória entre execuções em `.miniautogen/agents/{nome}/memory/context.json`.

### Como funciona

1. **Ao inicializar** — o AgentRuntime carrega `context.json` do disco
2. **Durante a execução** — o agente acumula contexto na memória
3. **Ao finalizar** — a memória é persistida automaticamente no disco

### Configuração

No agent YAML:

```yaml
memory:
  profile: default
  session_memory: true        # Manter memória da sessão
  retrieval_memory: false     # Busca semântica (futuro)
  max_context_tokens: 16000   # Limite de tokens de contexto
```

### Limpar memória de um agente

```bash
rm .miniautogen/agents/researcher/memory/context.json
```

---

## 11. CLI reference

### Comandos principais

| Comando | Descrição |
|---------|-----------|
| `miniautogen init <nome>` | Criar novo workspace |
| `miniautogen check` | Validar configuração |
| `miniautogen run <flow>` | Executar um flow |
| `miniautogen doctor` | Verificar ambiente |
| `miniautogen dash` | Lançar TUI dashboard |
| `miniautogen completions <shell>` | Gerar auto-complete |

### Gestão de recursos

| Comando | Subcomandos |
|---------|-------------|
| `miniautogen engine` | `create`, `list`, `show`, `update`, `delete`, `discover` |
| `miniautogen agent` | `create`, `list`, `show`, `update`, `delete` |
| `miniautogen flow` | `create`, `list`, `show`, `update`, `delete` |
| `miniautogen sessions` | `list`, `show`, `delete`, `replay`, `export` |
| `miniautogen server` | `start`, `stop`, `status`, `logs` |

### miniautogen init

```bash
miniautogen init <nome> [OPTIONS]

Options:
  --model TEXT       Modelo LLM padrão (default: gpt-4o-mini)
  --provider TEXT    Provider padrão (default: litellm)
  --no-examples      Não criar agente/tool de exemplo
  --force            Adicionar ficheiros faltantes a diretório existente
```

### miniautogen run

```bash
miniautogen run <flow_name> [OPTIONS]

Options:
  --input TEXT       Texto de input (ou @ficheiro para ler de ficheiro)
  --timeout FLOAT    Timeout em segundos
  --format TEXT      Formato de output: text | json
  --verbose          Exibir eventos durante execução
  --resume TEXT      Retomar de checkpoint (run_id)
  --explain          Mostrar plano de execução antes de executar
```

### miniautogen check

```bash
miniautogen check [OPTIONS]

Options:
  --format TEXT    Formato: text | json

Categorias verificadas:
  1. Schema do config
  2. Definições de agentes
  3. Especificações de skills
  4. Especificações de tools
  5. Configurações de flows
  6. Engine profiles
  7. Memory profiles
  8. Variáveis de ambiente
  9. Acessibilidade do gateway
```

---

## 12. Exemplos práticos

### Exemplo 1 — Pesquisa simples com um agente

```bash
# Criar workspace
miniautogen init pesquisa --provider openai --model gpt-4o-mini
cd pesquisa

# Configurar API key
echo "OPENAI_API_KEY=sk-..." >> .env

# O agente researcher já vem criado. Editar o flow:
```

Edite `miniautogen.yaml`:

```yaml
flows:
  main:
    mode: workflow
    participants:
      - researcher
```

```bash
# Executar
miniautogen run main --input "O que é retrieval-augmented generation?"
```

### Exemplo 2 — Code review com deliberação

```bash
miniautogen init code-review --provider anthropic --model claude-sonnet-4-20250514
cd code-review
```

Crie `agents/developer.yaml`:
```yaml
id: developer
name: Senior Developer
role: Senior Software Engineer
goal: Escrever código limpo e testável
engine_profile: default_api
```

Crie `agents/security.yaml`:
```yaml
id: security
name: Security Analyst
role: Application Security Specialist
goal: Identificar vulnerabilidades e recomendar correções
engine_profile: default_api
```

Crie `agents/architect.yaml`:
```yaml
id: architect
name: Software Architect
role: System Architect
goal: Avaliar decisões arquiteturais e garantir consistência
engine_profile: default_api
```

Configure o flow em `miniautogen.yaml`:
```yaml
flows:
  review:
    mode: deliberation
    participants:
      - developer
      - security
      - architect
    leader: architect
    max_rounds: 2
```

Coloque o código a revisar no workspace e execute:
```bash
miniautogen run review --input "Revisar o módulo de autenticação em src/auth.py"
```

### Exemplo 3 — Debug iterativo com loop

```yaml
# agents/debugger.yaml
id: debugger
name: Debug Expert
role: Bug Hunter
goal: Investigar bugs sistematicamente
engine_profile: default_api
tool_access:
  mode: all    # Acesso a todos os builtin tools

# agents/fixer.yaml
id: fixer
name: Code Fixer
role: Solution Implementer
goal: Corrigir bugs de forma limpa e testável
engine_profile: default_api
tool_access:
  mode: all
```

```yaml
# miniautogen.yaml
flows:
  debug:
    mode: loop
    participants:
      - debugger
      - fixer
    router: debugger
    max_turns: 15
```

```bash
miniautogen run debug --input "TypeError: Cannot read property 'user' of undefined em api/routes.js:42"
```

### Exemplo 4 — Multi-provider (OpenAI + Claude)

```yaml
engines:
  openai_fast:
    kind: api
    provider: "openai"
    model: "gpt-4o-mini"
    temperature: 0.2

  claude_deep:
    kind: api
    provider: "anthropic"
    model: "claude-sonnet-4-20250514"
    temperature: 0.3
```

```yaml
# agents/researcher.yaml — usa OpenAI (rápido e barato)
engine_profile: openai_fast

# agents/reviewer.yaml — usa Claude (profundo)
engine_profile: claude_deep
```

Cada agente usa um provider diferente, orquestrados pelo mesmo flow.

---

## 13. Server e gateway

O MiniAutoGen inclui um servidor REST para execução remota de flows.

### Iniciar o servidor

```bash
# Foreground
miniautogen server start

# Background (daemon)
miniautogen server start --daemon --port 8080

# Com limites
miniautogen server start --max-concurrency 5 --timeout 300
```

### Endpoints da API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/health` | Health check |
| POST | `/api/v1/runs` | Criar um run |
| GET | `/api/v1/runs` | Listar runs |
| GET | `/api/v1/runs/{id}` | Status de um run |
| POST | `/api/v1/runs/{id}/cancel` | Cancelar run |
| GET | `/api/v1/runs/{id}/events` | Eventos do run |

### Exemplo de uso

```bash
# Criar um run
curl -X POST http://localhost:8080/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{"input_payload": {"text": "Pesquise sobre IA"}}'

# Verificar status
curl http://localhost:8080/api/v1/runs/{run_id}
```

### Gerenciar servidor

```bash
miniautogen server status    # Ver status
miniautogen server logs      # Ver logs
miniautogen server stop      # Parar daemon
miniautogen server restart   # Reiniciar
```

---

## 14. TUI — dashboard interativo

O MiniAutoGen Dash é um dashboard de terminal para visualizar e gerenciar flows em tempo real.

### Instalação

```bash
pip install miniautogen[tui]
```

### Lançar

```bash
miniautogen dash
```

### Funcionalidades

| View | Atalho | Descrição |
|------|--------|-----------|
| Agents | `:agents` | Roster de agentes com CRUD |
| Flows | `:pipelines` | Gerenciar e executar flows |
| Runs | `:runs` | Histórico de execuções |
| Events | `:events` | Stream de eventos em tempo real |
| Engines | `:engines` | Gerenciar engine profiles |
| Config | `:config` | Visualizar configuração |

### Layout

```
┌─────────────┬──────────────────────────────────────┐
│  Team       │  Interaction Log                     │
│  Sidebar    │  (conversação dos agentes)           │
│             │                                      │
│  ● agent1   │  [researcher] Investigando...        │
│  ○ agent2   │  [reviewer] Revisando resultado...   │
│  ◐ agent3   │  [architect] Consolidando...         │
│             │                                      │
│             ├──────────────────────────────────────┤
│             │  Progress: ████████░░ 80%            │
└─────────────┴──────────────────────────────────────┘
  [q]uit  [r]efresh  [n]ew agent  [:]command palette
```

---

## 15. SDK — uso programático

Para casos que precisam de mais controle, use o SDK Python diretamente.

### Imports principais

```python
from miniautogen.api import (
    # Runtimes
    PipelineRunner,
    AgentRuntime,

    # Tool registries
    BuiltinToolRegistry,
    CompositeToolRegistry,
    InMemoryToolRegistry,

    # Events
    EventSink,
    InMemoryEventSink,
    EventType,

    # Coordination
    WorkflowPlan,
    WorkflowStep,
    DeliberationPlan,
    AgenticLoopPlan,

    # Contracts
    AgentSpec,
    RunContext,
    RunResult,
    Message,
)
```

### Exemplo: criar um AgentRuntime manualmente

```python
import anyio
from miniautogen.api import (
    AgentRuntime,
    BuiltinToolRegistry,
    InMemoryEventSink,
    RunContext,
)
from miniautogen.backends.engine_resolver import EngineResolver

async def main():
    # Resolver um driver
    resolver = EngineResolver()
    driver = resolver.create_fresh_driver("default_api", config)

    # Criar tool registry
    tools = BuiltinToolRegistry(workspace_root=Path("."))

    # Criar runtime
    runtime = AgentRuntime(
        agent_id="my-agent",
        driver=driver,
        run_context=RunContext(run_id="run-1", ...),
        event_sink=InMemoryEventSink(),
        system_prompt="You are a helpful assistant.",
        tool_registry=tools,
    )

    # Usar
    await runtime.initialize()
    try:
        response = await runtime.process("Explique quantum computing")
        print(response)
    finally:
        await runtime.close()

anyio.run(main)
```

### Exemplo: executar flow programaticamente

```python
import anyio
from pathlib import Path
from miniautogen.api import PipelineRunner, InMemoryEventSink
from miniautogen.cli.config import load_config, FlowConfig
from miniautogen.cli.services.agent_ops import load_agent_specs

async def main():
    config = load_config(Path("miniautogen.yaml"))
    agent_specs = load_agent_specs(Path("."))

    runner = PipelineRunner(event_sink=InMemoryEventSink())

    result = await runner.run_from_config(
        flow_config=FlowConfig(
            mode="workflow",
            participants=["researcher", "writer"],
        ),
        agent_specs=agent_specs,
        workspace=Path("."),
        config=config,
        pipeline_input="Write about AI orchestration",
    )

    print(result)

anyio.run(main)
```

---

## 16. Troubleshooting

### "Flow must have either 'target' or 'mode'"

O flow precisa de um `target` (callable Python) ou `mode` + `participants` (config-driven). Verifique seu `miniautogen.yaml`.

### "Config-driven flow requires 'participants'"

Flows com `mode` precisam de uma lista de `participants`. Adicione os nomes dos agentes.

### "Flow participant 'X' not found in agent specs"

O agente referenciado no flow não existe em `agents/`. Crie o arquivo YAML do agente.

### "Sandbox denied read access"

O agente tentou ler um arquivo fora dos limites permitidos. Builtin tools só acessam dentro do workspace.

### "File too large (N bytes). Use offset/limit params."

Arquivos maiores que 1 MB precisam ser lidos com `offset` e `limit`. O agente deve usar esses parâmetros.

### "grep not found on system"

O tool `search_codebase` requer `grep` instalado. Disponível nativamente em macOS/Linux. No Windows, instale Git for Windows.

### API key não encontrada

```bash
# Verificar keys configuradas
miniautogen doctor

# Verificar engines descobertos
miniautogen engine discover
```

### Testes não passam após instalação

```bash
# Verificar ambiente completo
miniautogen doctor --format json

# Validar projeto
miniautogen check
```

---

## Próximos passos

- **MCP integration** — Conectar tools via Model Context Protocol (em desenvolvimento)
- **LiteLLM driver** — Suporte a proxy multi-provider unificado
- **Composite flows** — Encadear sub-flows de modos diferentes
- **Durable execution** — Persistência de estado para flows de longa duração

---

*MiniAutoGen v0.1.0 — "O agente é commodity. O runtime é o produto."*
