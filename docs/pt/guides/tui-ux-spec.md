# MiniAutoGen Dash -- Especificacao UX Completa

> **Versao:** 1.0.0 | **Data:** 2026-03-20
> **Escopo:** Documentacao exaustiva da interface TUI (Terminal User Interface) do MiniAutoGen Dash, construida com Textual.
> **Publico-alvo:** Designers UI/UX para revisao de usabilidade, fluxos e hierarquia visual.

---

## Indice

1. [Visao Geral da Arquitetura de Informacao](#1-visao-geral-da-arquitetura-de-informacao)
2. [Mapa de Telas e Navegacao](#2-mapa-de-telas-e-navegacao)
3. [Fluxos de Usuario](#3-fluxos-de-usuario)
4. [Inventario Tela-a-Tela](#4-inventario-tela-a-tela)
5. [Padroes de Interacao](#5-padroes-de-interacao)
6. [Sistema de Temas e Cores](#6-sistema-de-temas-e-cores)
7. [Vocabulario de Status (7 Estados)](#7-vocabulario-de-status-7-estados)
8. [Sistema de Notificacoes](#8-sistema-de-notificacoes)
9. [Comportamento Responsivo](#9-comportamento-responsivo)
10. [Lacunas e Recomendacoes](#10-lacunas-e-recomendacoes)

---

## 1. Visao Geral da Arquitetura de Informacao

### 1.1 Estrutura de Camadas

O Dash possui 3 camadas de navegacao:

| Camada | Tipo | Exemplos |
|--------|------|----------|
| **L0 -- Workspace** | Tela principal (App Shell) | TeamSidebar + WorkPanel + Footer |
| **L1 -- Views Secundarias** | Screens empilhadas via command palette | `:agents`, `:pipelines`, `:runs`, `:events`, `:engines`, `:config` |
| **L2 -- Modais** | ModalScreens sobrepostas | InitWizard, CreateForm, AgentCardScreen, DiffView |

### 1.2 Hierarquia de Componentes

```
MiniAutoGenDash (App)
|
+-- Header (titulo + subtitulo com status do servidor)
|
+-- TeamSidebar (dock: left, 28 colunas)
|   +-- Static "The Team" (titulo)
|   +-- VerticalScroll #agent-list
|       +-- AgentCard (por agente)
|           +-- Static #agent-info (simbolo + nome + role)
|
+-- WorkPanel (area principal, 1fr)
|   +-- InteractionLog
|   |   +-- RichLog #log (auto-scroll, markup, highlight)
|   +-- Vertical #progress-section (dock: bottom, 3 linhas)
|       +-- ProgressBar #step-progress
|       +-- Static #step-label ("Ready")
|
+-- Footer (key hints do Textual)
```

### 1.3 Pontos de Entrada

| Ponto de Entrada | Descricao |
|------------------|-----------|
| `python -m miniautogen.tui` | Entrada direta standalone |
| `miniautogen dash` | Via CLI (comando registrado) |
| Programatico | `MiniAutoGenDash(project_root=...)` |

### 1.4 Pontos de Saida

| Acao | Tecla | Resultado |
|------|-------|-----------|
| Quit | `q` | Encerra a aplicacao |
| Escape (tela L0) | `Esc` | Noop (action_back vazio) |
| Escape (tela L1/L2) | `Esc` | Volta para tela anterior (pop_screen) |

---

## 2. Mapa de Telas e Navegacao

### 2.1 Diagrama de Navegacao

```
                        +------------------+
                        |   INIT WIZARD    |  (auto se !has_project)
                        |   (ModalScreen)  |
                        +--------+---------+
                                 | dismiss(True/False)
                                 v
+================================================================+
|                    WORKSPACE (L0)                               |
|                                                                |
|  +----------+  +--------------------------------------------+  |
|  | Team     |  | WorkPanel                                  |  |
|  | Sidebar  |  |                                            |  |
|  |          |  |  InteractionLog (RichLog)                  |  |
|  | AgentCard|  |    - Step headers                          |  |
|  | AgentCard|  |    - Agent messages                        |  |
|  | AgentCard|  |    - Tool call cards                       |  |
|  |          |  |    - Streaming indicators                  |  |
|  |          |  |    - Approval banners (inline)             |  |
|  +----------+  |                                            |  |
|     [t]toggle  |  +--------------------------------------+  |  |
|                |  | ProgressBar + Step Label             |  |  |
|                |  +--------------------------------------+  |  |
|                +--------------------------------------------+  |
+================================================================+
        |              |              |              |
   [command palette / SCREENS dict]
        |              |              |              |
        v              v              v              v
  +-----------+  +-----------+  +-----------+  +-----------+
  | :agents   |  | :pipelines|  | :engines  |  | :events   |
  | (L1)      |  | (L1)      |  | (L1)      |  | (L1)      |
  +-----------+  +-----------+  +-----------+  +-----------+
        |              |              |
   [n] new       [n] new        [n] new
        |              |              |
        v              v              v
  +-----------+  +-----------+  +-----------+
  | CreateForm|  | CreateForm|  | CreateForm|
  | agent (L2)|  | pipeline  |  | engine    |
  +-----------+  +-----------+  +-----------+

  Outros modais:
  +-----------+  +-----------+  +-----------+
  | :runs (L1)|  | :config   |  | DiffView  |
  |           |  | (L1)      |  | (L2) [d]  |
  +-----------+  +-----------+  +-----------+

  +------------------+
  | AgentCardScreen  |  (modal slide-in from right)
  | (L2)             |  (acessivel via click no AgentCard)
  +------------------+
```

### 2.2 Registro de Telas (SCREENS)

As 6 views secundarias estao registradas no dicionario `SCREENS` do App e sao acessiveis via command palette do Textual (`:nome`):

| Chave | Classe | Descricao |
|-------|--------|-----------|
| `agents` | `AgentsView` | Roster de agentes com CRUD |
| `events` | `EventsView` | Stream de eventos com filtros |
| `pipelines` | `PipelinesView` | Lista de pipelines com CRUD + Run |
| `runs` | `RunsView` | Historico de execucoes |
| `engines` | `EnginesView` | Perfis de engine com CRUD |
| `config` | `ConfigView` | Configuracao do projeto (somente leitura) |

---

## 3. Fluxos de Usuario

### 3.1 Primeiro Uso (Sem Workspace)

**Contexto:** O usuario abre o Dash sem um `miniautogen.yaml` no diretorio corrente.

```
1. Usuario executa `miniautogen dash` ou `python -m miniautogen.tui`
2. App.on_mount() -> _init_provider()
3. DashDataProvider.from_cwd() retorna None OU has_project() = False
4. App empurra InitWizardScreen (ModalScreen[bool])
5. Wizard exibe:
   - Mensagem de boas-vindas: "Welcome to MiniAutoGen! No project found."
   - Campo: Project Name (placeholder: "my-project")
   - Campo: Default Model (valor padrao: "gpt-4o-mini")
   - Campo: Default Provider (valor padrao: "litellm")
   - Botao: "Create Project" (primary)
   - Botao: "Cancel"
6a. [Caminho feliz] Usuario preenche nome, clica "Create Project"
    -> scaffold_project() cria diretorio com miniautogen.yaml
    -> dismiss(True)
    -> App._on_init_result(True) -> recarrega provider -> notify("Project initialized!")
6b. [Cancelamento] Usuario clica "Cancel" ou pressiona Esc
    -> dismiss(False)
    -> App._on_init_result(False) -> notify("No project -- some features unavailable")
```

**Validacao:**
- Nome do projeto e obrigatorio (exibe warning se vazio)
- FileExistsError e capturado e exibido como erro

### 3.2 Criando um Engine

```
1. No Workspace, usuario acessa command palette (Ctrl+P ou :)
2. Seleciona ":engines" -> EnginesView e empurrada como Screen
3. DataTable exibe engines existentes (Name, Kind, Provider, Model, Temperature)
4. Usuario pressiona [n] -> action_new_engine()
5. CreateFormScreen(resource_type="engine") e empurrada como Modal
6. Formulario exibe:
   - Engine Name (input, obrigatorio)
   - Kind (select: api | local, padrao: "api")
   - Provider (input, obrigatorio, placeholder: "e.g. litellm, openai")
   - Model (input, obrigatorio, placeholder: "e.g. gpt-4o-mini")
   - Endpoint (input, opcional, placeholder: "https://...")
   - API Key Env Var (input, opcional, placeholder: "e.g. OPENAI_API_KEY")
   - Botao "Save" (primary) + Botao "Cancel"
7. Usuario preenche campos e clica "Save"
   -> Validacao de campos obrigatorios
   -> provider.create_engine(name, **params)
   -> notify("Engine 'nome' created")
   -> dismiss(True) -> tabela atualizada
```

**Fluxo de edicao:** Identico, mas CreateFormScreen recebe `edit_name`. O campo "Name" fica desabilitado. Dados existentes sao pre-carregados via `provider.get_engine(name)`.

**Fluxo de exclusao:** [d] no engine selecionado -> `provider.delete_engine(name)` -> notify + refresh. Sem confirmacao explicita (lacuna identificada).

### 3.3 Criando um Agent

```
1. Command palette -> ":agents" -> AgentsView
2. DataTable: Name, Role, Engine, Status
3. [n] -> CreateFormScreen(resource_type="agent")
4. Formulario:
   - Agent Name (input, obrigatorio)
   - Role (input, obrigatorio, placeholder: "e.g. planner, researcher")
   - Goal (input, obrigatorio, placeholder: "Describe what this agent does")
   - Engine Profile (select dinamico, populado com engines disponiveis)
   - Botao "Save" + "Cancel"
5. Save -> provider.create_agent(name, **params)
   -> notify + dismiss(True)
   -> tabela + sidebar atualizadas (SidebarRefresh message)
```

**Diferencial:** Ao criar/editar/deletar agentes, um `SidebarRefresh` message e postado, fazendo o TeamSidebar recarregar a lista de agentes.

### 3.4 Criando um Flow (Pipeline)

```
1. Command palette -> ":pipelines" -> PipelinesView
2. DataTable: Name, Target, Mode, Agents, Status
3. [n] -> CreateFormScreen(resource_type="pipeline")
4. Formulario:
   - Pipeline Name (input, obrigatorio)
   - Mode (select: workflow | deliberation | loop | composite, padrao: "workflow")
   - Target (input, opcional, placeholder: "module.path:callable")
   - Botao "Save" + "Cancel"
5. Save -> provider.create_pipeline(name, **params)
```

**Nota:** O formulario de pipeline nao inclui campo para selecionar participantes (agentes). O campo `participants` existe na API do provider mas nao esta exposto no formulario. Lacuna identificada.

### 3.5 Executando um Flow e Monitorando

```
1. Em PipelinesView, usuario seleciona uma pipeline na DataTable
2. Pressiona [r] -> action_run_pipeline()
3. Validacao: pipeline selecionada? provider disponivel?
4. notify("Starting pipeline 'nome'...")
5. Worker async e criado via app.run_worker()
   -> provider.run_pipeline(name, event_sink=app._event_sink)
6. Eventos fluem pelo pipeline:
   TuiEventSink.publish(event)
     -> EventBridgeWorker le do stream (batching 100ms)
     -> Posta TuiEvent message no loop do Textual
     -> App.on_tui_event() -> WorkPanel.interaction_log.handle_event(event)
7. InteractionLog renderiza eventos por tipo:
   - COMPONENT_STARTED/DELIBERATION_STARTED/AGENTIC_LOOP_STARTED
     -> add_step_header(step_number, label, agent_name)
   - AGENT_REPLIED/BACKEND_MESSAGE_COMPLETED
     -> add_agent_message(agent_id, agent_name, content)
   - TOOL_INVOKED/TOOL_SUCCEEDED/TOOL_FAILED/BACKEND_TOOL_CALL_*
     -> add_tool_call(agent_id, tool_name, status, summary, elapsed)
   - BACKEND_MESSAGE_DELTA/BACKEND_TURN_STARTED
     -> add_streaming_indicator(agent_id, "generating"/"thinking")
8. Ao concluir:
   -> RunCompleted message postada -> App.on_run_completed()
   -> Header no InteractionLog: "Pipeline 'nome' completed/failed"
   -> Run registrada no historico (run_history)
   -> Notificacao toast: sucesso ou erro com detalhes
```

**Sidebar durante execucao:** O WorkspaceScreen (alternativo ao App shell) roteia eventos para a sidebar, atualizando status dos agentes em tempo real via `EventMapper.map_agent_status()` e `sidebar.highlight_agent()`.

### 3.6 Visualizando Stream de Eventos

```
1. Command palette -> ":events" -> EventsView
2. Input de filtro no topo: "Filter events (type, run_id, agent_id)..."
3. DataTable: Timestamp, Type, Run ID, Agent, Payload (truncado 60 chars)
4. Sintaxe de filtro (tempo real, on_input_changed):
   - /tipo    -> filtra por event type (ex: /error, /approval, /tool)
   - @agente  -> filtra por agent ID (ex: @planner, @writer)
   - texto    -> busca keyword em todos os campos
5. Eventos podem ser adicionados ao vivo via add_event()
6. [r] para refresh manual
```

**Nota:** `provider.get_events()` atualmente retorna lista vazia. Eventos sao streamados ao vivo apenas durante execucao. Nao ha persistencia de eventos entre sessoes.

### 3.7 Gerenciando Ciclo de Vida do Servidor

```
1. Status do servidor exibido no subtitulo do Header:
   "Your AI Team at Work | Server: running (:8080)"
   "Your AI Team at Work | Server: stopped"
2. Acoes disponiveis (sem binding visual, via command palette):
   - action_server_start() -> provider.start_server(daemon=True)
     -> host=127.0.0.1, port=8080 (hardcoded)
     -> notify(result message) + atualiza subtitulo
   - action_server_stop() -> provider.stop_server()
     -> notify(result message) + atualiza subtitulo
```

**Nota:** As acoes de servidor nao possuem bindings de teclado visiveis. O usuario precisa saber que existem via command palette ou acao programatica.

### 3.8 Visualizando Configuracao

```
1. Command palette -> ":config" -> ConfigView
2. Exibe texto formatado com Rich markup:
   - Project Name, Version
   - Default Engine, Default Memory
   - Resource Counts (Engines, Agents, Pipelines)
   - Database URL
3. [r] para refresh
4. Estado vazio: "No project configuration found."
5. Erro de carga: "Could not load project configuration."
```

---

## 4. Inventario Tela-a-Tela

### 4.1 Workspace (L0) -- Tela Principal

**Layout:**
```
+---------------------------------------------------------------+
| Header: "MiniAutoGen Dash" / "Your AI Team at Work | Server"  |
+----------+----------------------------------------------------+
| The Team | InteractionLog (RichLog)                            |
|          |                                                     |
| [P] Ag1  |  --- Step 1: Planning (Planner) ---                |
| [A] Ag2  |  Planner                                           |
| [W] Ag3  |  Let me analyze the requirements...                |
|          |                                                     |
|          |  | tool: web_search  done 1.2s                      |
|          |                                                     |
|          |  --- Step 2: Research (Researcher) ---              |
|          |  ... thinking...                                    |
|          |                                                     |
|          |  +======================================+           |
|          |  | Approval Required                    |           |
|          |  | Agent wants to modify config.yaml    |           |
|          |  | [Approve]  [Deny]                    |           |
|          |  +======================================+           |
|          |                                                     |
+----------+----------------------------------------------------+
|          | [ProgressBar========         ] Step 2 of 5         |
+----------+----------------------------------------------------+
| Footer: q Quit  ? Help  Esc Back  f Fullscreen  t Team  / Search |
+---------------------------------------------------------------+
```

**Dados exibidos:**
- TeamSidebar: Lista de agentes com simbolo de status + nome + role
- InteractionLog: Historico de conversa com step headers, mensagens, tool calls, streaming
- ProgressBar: Progresso atual do pipeline (current/total)
- Header/subtitulo: Status do servidor

**Acoes disponiveis (Bindings globais):**

| Tecla | Acao | Visivel no Footer |
|-------|------|-------------------|
| `q` | Quit | Sim |
| `?` | Help (notify com dicas) | Sim |
| `Esc` | Back (noop no L0) | Sim |
| `f` | Fullscreen (esconde sidebar) | Sim |
| `t` | Toggle sidebar | Sim |
| `d` | Abrir DiffView | Nao |
| `/` | Search (stub, noop) | Sim |
| `Tab` | Proximo pipeline tab (stub, noop) | Nao |

**Estados vazios:**
- Sem agentes: Sidebar mostra apenas titulo "The Team"
- Sem execucao ativa: InteractionLog vazio, ProgressBar em "Ready"

### 4.2 AgentsView (L1)

**Layout:**
```
+---------------------------------------------------------------+
| Header                                                        |
+---------------------------------------------------------------+
| [bold] Agents                                                 |
| [dim] Keys: new  edit  delete  refresh                        |
+---------------------------------------------------------------+
| Name       | Role        | Engine        | Status             |
|------------|-------------|---------------|--------------------|
| planner    | planner     | default_api   | ready              |
| researcher | researcher  | gpt4_turbo    | ready              |
| writer     | writer      | default_api   | ready              |
+---------------------------------------------------------------+
| Footer: Esc Back  n New  e Edit  d Delete  r Refresh          |
+---------------------------------------------------------------+
```

**Colunas:** Name, Role, Engine, Status (fixo "ready")

**Bindings:**

| Tecla | Acao |
|-------|------|
| `Esc` | Voltar ao Workspace |
| `n` | Novo agente (abre CreateForm) |
| `e` | Editar agente selecionado |
| `d` | Deletar agente selecionado |
| `r` | Refresh da tabela |

**Estado vazio:** Tabela sem linhas (nenhum indicador visual especial)

**Estado de erro:**
- Nenhum agente selecionado ao editar/deletar: notify("No agent selected", warning)
- Erro de exclusao: notify(mensagem do erro, error)

### 4.3 PipelinesView (L1)

**Layout:** Identico ao AgentsView, com DataTable diferente.

**Colunas:** Name, Target, Mode, Agents (lista de participantes), Status (fixo "ready")

**Bindings:**

| Tecla | Acao |
|-------|------|
| `Esc` | Voltar |
| `n` | Novo pipeline |
| `e` | Editar pipeline |
| `d` | Deletar pipeline |
| `r` | Executar pipeline selecionado |
| `F5` | Refresh |

**Nota:** A tecla `r` nesta view significa "Run", nao "Refresh" como nas outras views. O refresh usa `F5`.

### 4.4 EnginesView (L1)

**Colunas:** Name, Kind, Provider, Model, Temperature

**Bindings:**

| Tecla | Acao |
|-------|------|
| `Esc` | Voltar |
| `n` | Novo engine |
| `e` | Editar engine |
| `d` | Deletar engine |
| `r` | Refresh |

**Fontes de dados:** Engines vem de 3 fontes com prioridade (yaml > env > local):
- YAML config (`miniautogen.yaml`)
- Variaveis de ambiente (OPENAI_API_KEY, etc.)
- Servidores locais (Ollama, LMStudio via EngineResolver)

### 4.5 EventsView (L1)

**Layout:**
```
+---------------------------------------------------------------+
| Header                                                        |
+---------------------------------------------------------------+
| [bold] Events                                                 |
| [dim] Filter: /type  @agent  keyword                          |
+---------------------------------------------------------------+
| [Filter events (type, run_id, agent_id)... ]  <- Input        |
+---------------------------------------------------------------+
| Timestamp | Type              | Run ID  | Agent    | Payload  |
|-----------|-------------------|---------|----------|----------|
| 10:23:01  | component_started | a1b2c3  | planner  | {"st...  |
| 10:23:02  | agent_replied     | a1b2c3  | planner  | Let m... |
+---------------------------------------------------------------+
| Footer: Esc Back  r Refresh                                   |
+---------------------------------------------------------------+
```

**Filtro em tempo real (on_input_changed):**
- `/error` -> filtra tipo contendo "error"
- `@planner` -> filtra agente contendo "planner"
- `web_search` -> busca keyword em todos os campos
- Case-insensitive

### 4.6 RunsView (L1)

**Colunas:** Run ID (truncado 8 chars), Pipeline, Status, Started, Duration, Events

**Bindings:**

| Tecla | Acao |
|-------|------|
| `Esc` | Voltar |
| `r` | Refresh |
| `Enter` | Detalhe (exibe notify com Run ID + Status) |

**Nota:** Runs sao mantidas apenas em memoria (`_run_history` do provider). Ao reiniciar o Dash, o historico e perdido.

**Estado vazio:** notify("No runs recorded yet", information) ao montar com lista vazia

### 4.7 ConfigView (L1)

**Layout:** Texto formatado com Rich markup (nao usa DataTable).

**Campos exibidos:**
- Project Name, Version
- Default Engine, Default Memory
- Resource Counts: Engines, Agents, Pipelines
- Database URL

**Bindings:** `Esc` (voltar), `r` (refresh)

**Somente leitura** -- nao ha edicao via esta view.

### 4.8 InitWizardScreen (L2 -- Modal)

**Tipo:** `ModalScreen[bool]`

**Campos:**
1. Project Name (Input, obrigatorio, placeholder: "my-project")
2. Default Model (Input, valor padrao: "gpt-4o-mini")
3. Default Provider (Input, valor padrao: "litellm")

**Botoes:** "Create Project" (primary), "Cancel"
**Dismiss:** `True` se criado, `False` se cancelado

### 4.9 CreateFormScreen (L2 -- Modal Generico)

**Tipo:** `ModalScreen[bool]`

**Configuracao por tipo de recurso:**

| Recurso | Campos | Tipos de Campo |
|---------|--------|----------------|
| **engine** | name, kind, provider, model, endpoint, api_key_env | input, select(api/local), input, input, input, input |
| **agent** | name, role, goal, engine_profile | input, input, input, engine_select (dinamico) |
| **pipeline** | name, mode, target | input, select(workflow/deliberation/loop/composite), input |

**Modo edicao:** Campo "name" desabilitado. Dados pre-carregados do provider.

**Validacao:** Campos marcados como `required` sao verificados antes do save. Exibe warning por campo ausente.

### 4.10 AgentCardScreen (L2 -- Modal)

**Tipo:** `ModalScreen[None]`

**Posicionamento:** Alinhado a direita (`align: right middle`), painel de 60 colunas com `border-left: tall $accent`.

**Secoes exibidas:**
1. Titulo com emoji robot + nome do agente
2. Role
3. Engine
4. Goal
5. Status
6. Tools (lista com bullet points)
7. Permissions (lista com bullet points)
8. Dicas de acao: `[e]dit  [h]istory  [Esc] close`

**Bindings:**

| Tecla | Acao | Status |
|-------|------|--------|
| `Esc` | Fechar modal | Funcional |
| `e` | Editar agente | Stub (notify "not yet implemented") |
| `h` | Historico do agente | Stub (notify "not yet implemented") |

### 4.11 DiffViewScreen (L2 -- Screen)

**Tipo:** `Screen` (nao modal)

**Conteudo:** RichLog com syntax highlighting para diffs:
- Linhas `+` em verde
- Linhas `-` em vermelho
- Linhas `@@` em ciano
- Separadores de arquivo em azul bold

**Bindings:** `Esc` (voltar), `c` (limpar diffs)

**Estado vazio:** "No diffs to display. Diffs appear here when tool_call results contain code changes."

---

## 5. Padroes de Interacao

### 5.1 Atalhos de Teclado -- Mapa Completo

#### Bindings Globais (App Level)

| Tecla | Acao | Footer | Funcional |
|-------|------|--------|-----------|
| `q` | Quit | Sim | Sim |
| `?` | Help (notify) | Sim | Sim |
| `Esc` | Back | Sim | Noop no L0, pop_screen em L1/L2 |
| `f` | Fullscreen (esconde sidebar) | Sim | Sim (nao restaura) |
| `t` | Toggle sidebar | Sim | Sim |
| `d` | Abrir DiffView | Nao | Sim |
| `/` | Search | Sim | Stub (noop) |
| `Tab` | Proximo pipeline tab | Nao | Stub (noop) |

#### Bindings das Views CRUD (agents, engines, pipelines)

| Tecla | AgentsView | EnginesView | PipelinesView |
|-------|------------|-------------|---------------|
| `Esc` | Back | Back | Back |
| `n` | New | New | New |
| `e` | Edit | Edit | Edit |
| `d` | Delete | Delete | Delete |
| `r` | Refresh | Refresh | **Run** |
| `F5` | -- | -- | Refresh |

#### Bindings Contextuais

| Contexto | Tecla | Acao |
|----------|-------|------|
| ApprovalBanner | `a` | Aprovar |
| ApprovalBanner | `d` | Negar |
| StepBlock | `Enter` | Toggle collapse |
| AgentCardScreen | `e` | Editar (stub) |
| AgentCardScreen | `h` | Historico (stub) |
| DiffViewScreen | `c` | Limpar diffs |
| CreateFormScreen | `Esc` | Cancelar |

### 5.2 Padrao de Formulario (CreateFormScreen)

O `CreateFormScreen` e um formulario generico parametrizado:

1. **Declaracao de campos** via dicionarios em `_FIELD_MAP`
2. **Tipos de campo suportados:**
   - `input` -- Textual Input com placeholder
   - `select` -- Textual Select com opcoes estaticas
   - `engine_select` -- Select dinamico, populado com engines do provider
3. **Modo create vs edit:** Determinado pela presenca de `edit_name`
4. **Validacao:** Apenas campos obrigatorios (presenca). Sem validacao de formato.
5. **Feedback:** Notify toast para sucesso, warning para campo obrigatorio, error para excecoes

### 5.3 Sistema de Feedback

| Tipo | Mecanismo | Exemplo |
|------|-----------|---------|
| Sucesso | `self.notify(msg)` | "Agent 'planner' created" |
| Warning | `self.notify(msg, severity="warning")` | "No agent selected" |
| Erro | `self.notify(msg, severity="error")` | "No project found" |
| Informacao | `self.notify(msg, severity="information")` | "No runs recorded yet" |
| Progresso | ProgressBar + Step Label | "Step 2 of 5" |
| Streaming | Indicadores no InteractionLog | "... thinking...", cursor |
| Status real-time | Subtitulo do Header | "Server: running (:8080)" |
| Desktop | OSC 9 escape sequences | "Pipeline Completed" (terminal) |

### 5.4 Notificacoes Desktop (Terminal)

O sistema de notificacoes desktop usa escape sequences OSC 9/99:

**Niveis:**
- `all` -- Todas as notificacoes relevantes
- `failures-only` -- Apenas falhas
- `none` -- Desabilitado

**Eventos que disparam notificacao:**
- APPROVAL_REQUESTED -> "Approval Needed: Agent needs your approval"
- RUN_FINISHED -> "Pipeline Completed: Run X finished"
- RUN_FAILED -> "Pipeline Failed: Run X failed"
- RUN_TIMED_OUT -> "Pipeline Timed Out: Run X timed out"
- RUN_CANCELLED -> "Pipeline Cancelled: Run X cancelled"

**Fallback:** Bell terminal (`\a`) quando OSC nao e suportado.

### 5.5 Padrao de Aprovacao (Human-in-the-Loop)

O `ApprovalBanner` e um widget inline no conversation flow:

```
+========================================+
| Hourglass Approval Required            |
| Descricao da acao                      |
| Action: tipo_da_acao                   |
|                                        |
| Files affected:                        |
|   - config.yaml                        |
|   - agents/planner.yaml               |
|                                        |
| [Approve]  [Deny]                      |
+========================================+
```

**Interacao:**
- Botoes clicaveis: [A]pprove, [D]eny
- Atalhos de teclado: `a` para aprovar, `d` para negar
- Resposta: Posta `ApprovalDecision` message com request_id, decision, reason

**Estilizacao:** `border: double $warning`, background surface, transicao de 200ms.

---

## 6. Sistema de Temas e Cores

### 6.1 Temas Disponiveis

4 temas pre-definidos com tokens semanticos:

| Token | tokyo-night (padrao) | catppuccin | monokai | light |
|-------|---------------------|------------|---------|-------|
| primary | #7aa2f7 | #89b4fa | #66d9ef | #4078f2 |
| secondary | #bb9af7 | #cba6f7 | #ae81ff | #a626a4 |
| accent | #7dcfff | #89dceb | #a6e22e | #0184bc |
| background | #1a1b26 | #1e1e2e | #272822 | #fafafa |
| surface | #24283b | #313244 | #3e3d32 | #f0f0f0 |
| text | #c0caf5 | #cdd6f4 | #f8f8f2 | #383a42 |
| text_muted | #565f89 | #6c7086 | #75715e | #a0a1a7 |

### 6.2 Tokens de Status (por tema)

| Status | tokyo-night | catppuccin | monokai | light |
|--------|-------------|------------|---------|-------|
| active | #9ece6a | #a6e3a1 | #a6e22e | #50a14f |
| done | #73daca | #94e2d5 | #66d9ef | #0184bc |
| working | #e0af68 | #f9e2af | #e6db74 | #c18401 |
| waiting | #ff9e64 | #fab387 | #fd971f | #e45649 |
| failed | #f7768e | #f38ba8 | #f92672 | #e45649 |
| cancelled | #db4b4b | #eba0ac | #cc6633 | #986801 |

### 6.3 Sombras e Transicoes (CSS)

| Propriedade | Widget | Valor |
|-------------|--------|-------|
| Transicao background | TeamSidebar | 200ms |
| Transicao background | AgentCard | 150ms |
| Transicao background | ApprovalBanner | 200ms |
| Transicao background | StepBlock | 200ms |
| Hover | AgentCard | background: $primary-background |
| Highlight | AgentCard.--highlighted | background: $accent 20% |

---

## 7. Vocabulario de Status (7 Estados)

Cada status possui simbolo unico (distinguivel sem cor, para acessibilidade), cor e label:

| Status | Simbolo | Cor | Label | Uso |
|--------|---------|-----|-------|-----|
| DONE | checkmark | dim green | Done | Agente/step concluiu |
| ACTIVE | filled circle | bright_green | Active | Agente/step em execucao |
| WORKING | half-filled circle | yellow | Working | Processando (tool call, delta) |
| WAITING | hourglass | dark_orange | Waiting | Aguardando aprovacao |
| PENDING | empty circle | grey50 | Pending | Ainda nao iniciou |
| FAILED | cross mark | red | Failed | Erro/falha |
| CANCELLED | circle with line | dark_red | Cancelled | Cancelado/negado |

### 7.1 Mapeamento de Eventos Core para Status TUI

O `EventMapper` traduz os 44 `EventTypes` do core para os 7 estados da TUI:

**Run-level:**
- RUN_STARTED -> ACTIVE
- RUN_FINISHED -> DONE
- RUN_FAILED, RUN_TIMED_OUT -> FAILED
- RUN_CANCELLED -> CANCELLED
- APPROVAL_REQUESTED -> WAITING
- APPROVAL_GRANTED -> ACTIVE
- APPROVAL_DENIED -> CANCELLED
- APPROVAL_TIMEOUT -> FAILED

**Component-level:**
- COMPONENT_STARTED -> ACTIVE
- COMPONENT_FINISHED -> DONE
- COMPONENT_SKIPPED -> CANCELLED
- COMPONENT_RETRIED -> WORKING

**Agent-level (20 mapeamentos):**
- AGENT_REPLIED, BACKEND_MESSAGE_COMPLETED -> DONE
- ROUTER_DECISION, BACKEND_SESSION_STARTED -> ACTIVE
- BACKEND_MESSAGE_DELTA, TOOL_INVOKED -> WORKING
- BACKEND_ERROR, TOOL_FAILED -> FAILED
- (ver event_mapper.py para lista completa)

---

## 8. Sistema de Notificacoes

### 8.1 Notificacoes In-App (Toast)

Usam o sistema nativo de `self.notify()` do Textual:

| Severidade | Cor | Exemplo |
|------------|-----|---------|
| default | -- | "Project initialized!" |
| warning | amarelo | "No agent selected" |
| error | vermelho | "No project found" |
| information | azul | "No runs recorded yet" |

### 8.2 Notificacoes Desktop

| Evento | Titulo | Corpo |
|--------|--------|-------|
| APPROVAL_REQUESTED | "Approval Needed" | "{agent} needs your approval" |
| RUN_FINISHED | "Pipeline Completed" | "Run {id} finished" |
| RUN_FAILED | "Pipeline Failed" | "Run {id} failed" |
| RUN_TIMED_OUT | "Pipeline Timed Out" | "Run {id} timed out" |
| RUN_CANCELLED | "Pipeline Cancelled" | "Run {id} cancelled" |

---

## 9. Comportamento Responsivo

### 9.1 Breakpoints

| Largura Terminal | Sidebar | Largura Sidebar |
|-----------------|---------|-----------------|
| < 100 colunas | Oculta | 0 |
| 100-119 colunas | Visivel | 6 colunas (icons-only) |
| >= 120 colunas | Visivel | 28 colunas (completa) |

### 9.2 Logica de Responsividade

- `on_mount()` e `on_resize()` disparam `_apply_responsive()`
- Sidebar usa `dock: left` com largura ajustada dinamicamente via `styles.width`
- WorkPanel ocupa `1fr` (espaco restante)
- `action_fullscreen()` esconde sidebar (`sidebar.display = False`)
- `action_toggle_sidebar()` alterna visibilidade

### 9.3 Sidebar no Modo Compacto (6 colunas)

No modo compacto, o AgentCard renderiza `simbolo + nome` em 6 colunas. Nao ha logica especifica para modo "icons-only" -- o conteudo simplesmente trunca. Potencial melhoria: renderizar apenas o simbolo de status quando compacto.

---

## 10. Lacunas e Recomendacoes

### 10.1 Funcionalidades Stub/Nao Implementadas

| Funcionalidade | Status | Impacto |
|----------------|--------|---------|
| `action_search()` | Stub (noop) | Alto -- `/` aparece no footer mas nao funciona |
| `action_back()` | Stub (noop) | Medio -- Esc nao faz nada no L0 |
| `action_next_pipeline()` | Stub (noop) | Baixo -- Tab nao muda abas |
| AgentCardScreen `[e]dit` | Stub (notify) | Medio -- Botao visivel mas inoperante |
| AgentCardScreen `[h]istory` | Stub (notify) | Baixo -- Feature futura |
| Troca de tema em runtime | Nao implementada | Medio -- 4 temas definidos mas sem switcher |

### 10.2 Lacunas vs Paridade CLI

| Feature CLI | Disponivel no TUI | Observacao |
|-------------|-------------------|------------|
| `miniautogen init` | Sim (InitWizard) | Funcional |
| `miniautogen agent create` | Sim (CreateForm) | Funcional |
| `miniautogen engine create` | Sim (CreateForm) | Funcional |
| `miniautogen flow create` | Parcial | Falta campo `participants`, `leader` |
| `miniautogen run` | Sim (PipelinesView) | Funcional, com streaming |
| `miniautogen check` | Nao | Sem view de validacao |
| `miniautogen session` | Nao | Sem gerenciamento de sessoes |
| Server start/stop | Parcial | Sem binding visual, valores hardcoded |
| Persistencia de runs | Nao | Historico apenas em memoria |
| `miniautogen flow update` | Sim | Via CreateForm edit mode |

### 10.3 Anti-padroes de UX Identificados

#### 10.3.1 Exclusao Sem Confirmacao
**Problema:** `action_delete_agent()`, `action_delete_engine()` e `action_delete_pipeline()` executam exclusao imediata sem dialogo de confirmacao.
**Risco:** Perda acidental de dados.
**Recomendacao:** Implementar `ConfirmDialog` modal com mensagem "Are you sure you want to delete '{name}'?" e botoes Confirm/Cancel.

#### 10.3.2 Inconsistencia na Tecla `r`
**Problema:** Em AgentsView e EnginesView, `r` significa "Refresh". Em PipelinesView, `r` significa "Run" (uma acao destrutiva/custosa).
**Risco:** Usuario acostumado com `r=Refresh` pode acidentalmente executar um pipeline.
**Recomendacao:** Usar `Enter` ou `x` para "Run" em PipelinesView, mantendo `r` como Refresh universal.

#### 10.3.3 Fullscreen Sem Restauracao
**Problema:** `action_fullscreen()` esconde a sidebar, mas nao ha binding para restaura-la ao estado anterior. O usuario precisa usar `t` para toggle.
**Risco:** Desorientacao (usuario nao sabe como voltar).
**Recomendacao:** `f` deveria funcionar como toggle (esconde/mostra), ou exibir uma dica de como restaurar.

#### 10.3.4 Estado Vazio Sem Orientacao Visual
**Problema:** DataTables vazias (AgentsView, EnginesView, etc.) nao exibem nenhum indicador visual. A tabela simplesmente aparece sem linhas.
**Recomendacao:** Usar o widget `EmptyState` existente nas views quando a lista esta vazia, com mensagem orientadora (ex: "No agents yet. Press [n] to create one.").

#### 10.3.5 Pipeline Form Incompleto
**Problema:** O formulario de criacao de pipeline nao inclui campos para `participants` (agentes do pipeline) nem `leader`.
**Recomendacao:** Adicionar campo multi-select para participantes (populado dinamicamente com agentes disponiveis) e campo opcional para leader.

#### 10.3.6 Search Anunciado mas Nao Funcional
**Problema:** A tecla `/` aparece no Footer como "Search" mas a acao e noop.
**Recomendacao:** Ou implementar busca global, ou remover do Footer (`show=False`) ate que seja implementada.

### 10.4 Preocupacoes de Acessibilidade

#### 10.4.1 Pontos Positivos
- Simbolos de status sao unicos e distinguiveis sem cor (checkmark, cross, circle, hourglass, etc.)
- Textual Framework fornece suporte basico a leitores de tela
- Contrast ratios dos temas dark parecem adequados para texto sobre background

#### 10.4.2 Pontos de Melhoria

| Item | Descricao | Severidade |
|------|-----------|------------|
| Sem ARIA labels | Widgets customizados (AgentCard, ApprovalBanner) nao declaram roles/labels | Alta |
| Sem focus trap | ApprovalBanner inline nao captura foco automaticamente | Alta |
| Navegacao por teclado limitada | Nao ha como navegar para um AgentCard na sidebar e abrir o detalhe via Enter | Media |
| Sem anuncio de mudanca de status | Quando status de agente muda, nao ha `aria-live` region | Media |
| Sem indicador de loading | Execucao de pipeline mostra apenas "Starting pipeline..." -- sem loading spinner persistente | Baixa |
| Tema light com cores duplicadas | `status_waiting` e `status_failed` usam a mesma cor (#e45649) no tema light | Media |

### 10.5 Recomendacoes de Melhoria Prioritizadas

#### Prioridade Alta

1. **Confirmacao de exclusao** -- Adicionar modal de confirmacao para todas as operacoes de delete
2. **Corrigir inconsistencia da tecla `r`** -- Padronizar Refresh vs Run
3. **Remover `/` do Footer** -- Ate que search esteja implementado
4. **Empty states nas DataTables** -- Usar EmptyState com orientacao
5. **Focus management no ApprovalBanner** -- Auto-focus e trap quando aparece

#### Prioridade Media

6. **Campo `participants` no form de pipeline** -- Multi-select dinamico
7. **Toggle real em `action_fullscreen()`** -- Restaurar sidebar ao estado anterior
8. **Persistencia de historico de runs** -- Salvar em arquivo/DB entre sessoes
9. **Server bindings visiveis** -- Adicionar `S` para server start/stop no footer
10. **Sidebar compacta inteligente** -- Renderizar apenas icone/simbolo no modo 6 colunas

#### Prioridade Baixa

11. **Theme switcher** -- Permitir troca de tema em runtime via command palette
12. **Check view** -- Paridade com `miniautogen check`
13. **Session management view** -- Paridade com `miniautogen session`
14. **Pipeline tabs funcionais** -- PipelineTabs widget existe mas nao esta integrado ao fluxo principal
15. **Busca global** -- Implementar `/` para filtro em todas as views

---

## Apendice A: Mapeamento de Arquivos

| Arquivo | Responsabilidade |
|---------|------------------|
| `tui/app.py` | App shell, bindings globais, ciclo de vida |
| `tui/dash.tcss` | Stylesheet CSS principal |
| `tui/data_provider.py` | Bridge TUI -> CLI services (CRUD + run) |
| `tui/event_mapper.py` | Traducao EventType -> AgentStatus |
| `tui/event_sink.py` | Stream anyio para bridge de eventos |
| `tui/messages.py` | Mensagens Textual: TuiEvent, SidebarRefresh, RunCompleted |
| `tui/notifications.py` | Notificacoes desktop via OSC 9/99 |
| `tui/status.py` | 7 estados com simbolo, cor, label |
| `tui/themes.py` | 4 temas com tokens semanticos |
| `tui/workers.py` | EventBridgeWorker (batching 100ms) |
| `tui/views/base.py` | SecondaryView base class |
| `tui/views/agents.py` | View de agentes (CRUD) |
| `tui/views/pipelines.py` | View de pipelines (CRUD + Run) |
| `tui/views/runs.py` | View de historico de runs |
| `tui/views/events.py` | View de stream de eventos com filtro |
| `tui/views/engines.py` | View de engines (CRUD) |
| `tui/views/config.py` | View de configuracao (read-only) |
| `tui/screens/init_wizard.py` | Wizard de inicializacao |
| `tui/screens/create_form.py` | Formulario generico CRUD |
| `tui/screens/agent_card.py` | Modal de detalhe do agente |
| `tui/screens/diff_view.py` | Visualizador de diffs |
| `tui/screens/workspace.py` | Tela workspace alternativa |
| `tui/widgets/team_sidebar.py` | Sidebar com roster de agentes |
| `tui/widgets/work_panel.py` | Painel principal com InteractionLog |
| `tui/widgets/interaction_log.py` | Log de conversa com eventos |
| `tui/widgets/agent_card.py` | Card de agente na sidebar |
| `tui/widgets/approval_banner.py` | Banner HITL inline |
| `tui/widgets/empty_state.py` | Estado vazio com orientacao |
| `tui/widgets/hint_bar.py` | Barra de dicas contextual |
| `tui/widgets/pipeline_tabs.py` | Abas de pipelines ativos |
| `tui/widgets/step_block.py` | Bloco de step com collapse |
| `tui/widgets/tool_call_card.py` | Card inline de tool call |

## Apendice B: Cobertura de Testes

146 testes cobrindo:
- App shell (mount, bindings, event flow, sidebar population)
- Command palette (screens registration)
- Data provider (CRUD, run, server ops)
- Event filtering (type, agent, keyword, case-insensitive)
- Event mapper (44 event types -> 7 statuses)
- Event sink (publish/receive, async iteration)
- Notifications (should_notify logic, OSC formatting)
- All widgets (team_sidebar, work_panel, interaction_log, agent_card, approval_banner, empty_state, hint_bar, pipeline_tabs, step_block, tool_call_card)
- All screens (init_wizard, create_form, agent_card, diff_view, workspace)
- Zero coupling (imports from core are protocols/models only)
