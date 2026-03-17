# Especificação funcional E2E -- MiniAutoGen

Documento de especificação funcional end-to-end do framework MiniAutoGen, descrevendo a jornada completa do utilizador desde a criação do projeto até à operação e observabilidade em produção.

**Versão:** 2.0.0
**Data:** 2026-03-17
**Escopo:** Jornada E2E do desenvolvedor no MiniAutoGen SDK + CLI

---

## Índice

- [Parte 1: Story Map -- Jornada E2E no MiniAutoGen](#parte-1-story-map----jornada-e2e-no-miniautogen)
- [Parte 2: Especificação BDD dos fluxos E2E](#parte-2-especificação-bdd-dos-fluxos-e2e)
- [Parte 3: Especificação funcional](#parte-3-especificação-funcional)

---

# Parte 1: Story Map -- Jornada E2E no MiniAutoGen

O Story Map a seguir descreve a jornada completa de um desenvolvedor que utiliza o MiniAutoGen para orquestrar pipelines multiagente. Cada etapa representa um "Job to be Done" concreto, mapeado a ações técnicas reais do framework.

---

## Etapa 1: Setup e inicialização (Descoberta)

**User Story:**
> Como desenvolvedor, quero criar rapidamente a estrutura de um projeto multiagente para não precisar configurar manualmente diretórios, arquivos YAML e templates.

### Ações técnicas

O desenvolvedor executa o comando CLI `miniautogen init` para gerar o scaffold completo do projeto.

**Comando:**

```
miniautogen init meu-projeto --model gpt-4o-mini --provider litellm
```

**O que acontece:**

1. O CLI cria o diretório do projeto com a estrutura padrão.
2. Gera o arquivo `miniautogen.yml` com a configuração base (modelo, provider, pipelines).
3. Cria os diretórios `agents/`, `skills/`, `tools/` e `templates/`.
4. Se a flag `--no-examples` não estiver presente, inclui um agente de exemplo, uma skill e uma tool de referência.

**Resultado esperado:**

```
meu-projeto/
  miniautogen.yml
  agents/
  skills/
  tools/
  templates/
```

**Entidades envolvidas:** CLI `init_command`.

---

## Etapa 2: Definição de contratos e domínio (Implementação)

**User Story:**
> Como desenvolvedor, quero definir meus agentes de forma declarativa e escolher o modo de coordenação adequado ao meu caso de uso, para que o framework orquestre a interação entre eles automaticamente.

### 2.1 Definição de agentes via AgentSpec

O desenvolvedor cria arquivos YAML no diretório `agents/`, cada um seguindo o schema `AgentSpec`. Um AgentSpec declara:

- **Identidade:** `id`, `name`, `description`, `role`, `goal`, `backstory`
- **Capacidades:** `skills` (referências a skills anexadas), `tool_access` (modo allowlist/denylist/all), `mcp_access` (servidores MCP permitidos)
- **Políticas:** `memory` (perfil de memória, contexto máximo), `delegation` (se pode delegar, para quem), `runtime` (max_turns, timeout, retry_policy), `permissions` (shell, network, filesystem)
- **Motor de execução:** `engine_profile` (referência ao perfil de backend)

### 2.2 Escolha do modo de coordenação

O MiniAutoGen oferece quatro modos de coordenação, cada um com seu contrato (plan) tipado:

#### Modo 1: Workflow (WorkflowPlan)

Execução estruturada e disciplinada de etapas sequenciais com suporte a paralelismo (fan-out) e síntese opcional.

- `steps`: lista de `WorkflowStep`, cada um com `component_name` e `agent_id`
- `fan_out`: quando `True`, o sistema deve orquestrar a execução em paralelo, garantindo isolamento de falhas
- `synthesis_agent`: agente opcional que consolida os outputs de todas as etapas

**Caso de uso típico:** pipelines de processamento de dados, workflows de ETL, cadeia de transformação.

#### Modo 2: Deliberação (DeliberationPlan)

Ciclo de deliberação multi-round com peer review e convergência:

1. **Contribuição** -- cada participante produz um `ResearchOutput` estruturado
2. **Peer Review** -- cada participante revisa os outputs dos demais (produz `PeerReview`)
3. **Consolidação** -- o líder (leader_agent) sintetiza contribuições e reviews
4. **Verificação de suficiência** -- o líder decide se outra rodada é necessária (`is_sufficient`)
5. **Documento final** -- o líder produz um `FinalDocument` com sumário executivo, factos aceites, conflitos abertos e recomendações

Parâmetros do plano:
- `topic`: tema da deliberação
- `participants`: lista de IDs de agentes participantes
- `max_rounds`: número máximo de rodadas (1-50, padrão 3)
- `leader_agent`: agente líder (se omitido, usa o primeiro participante)
- `policy`: `ConversationPolicy` com limites de turns, budget e timeout

**Caso de uso típico:** pesquisa colaborativa, análise de decisões, revisão técnica multiagente.

#### Modo 3: Agentic loop (AgenticLoopPlan)

Loop conversacional dirigido por um router que decide dinamicamente qual agente fala a seguir.

- `router_agent`: agente que emite `RouterDecision` (próximo agente, sinal de terminação, risco de estagnação)
- `participants`: lista de agentes conversacionais
- `policy`: `ConversationPolicy` com `max_turns`, `budget_cap`, `timeout_seconds`, `stagnation_window`
- `goal`: objetivo da conversa
- `initial_message`: mensagem inicial opcional

O loop para quando:
- O router emite `terminate: true` (`ROUTER_TERMINATED`)
- Estagnação é detetada (`STAGNATION`)
- `max_turns` é atingido (`MAX_TURNS`)
- Timeout expira (`TIMEOUT`)

**Caso de uso típico:** chatbots multiagente, resolução colaborativa de problemas, brainstorming.

#### Modo 4: Composição (CompositeRuntime)

Encadeia múltiplos modos em sequência via `CompositionStep`. O output de cada etapa alimenta a próxima através de `RunContext.with_previous_result()`.

- `mode`: qualquer `CoordinationMode` (workflow, deliberação, agentic loop)
- `plan`: o plano tipado correspondente ao modo
- `label`: rótulo descritivo para rastreabilidade
- `input_mapper`: transformação opcional do `RunResult` anterior em novo `RunContext`
- `output_mapper`: transformação opcional do `RunResult` antes de passar adiante

Se qualquer etapa retorna `RunStatus.FAILED`, a composição para imediatamente (fail-fast).

**Caso de uso típico:** workflow de pesquisa -> deliberação -> workflow de publicação.

### 2.3 Configuração de políticas

O desenvolvedor configura políticas laterais que operam de forma event-driven, sem invadir o core:

| Política | Classe | Função |
|----------|--------|--------|
| Orçamento | `BudgetPolicy` / `BudgetTracker` | Rastreamento de custo por tokens; levanta `BudgetExceededError` quando o limite é excedido |
| Aprovação | `ApprovalPolicy` / `ApprovalGate` | Human-in-the-loop; pausa a execução até receber `ApprovalResponse` |
| Retry | `RetryPolicy` | Backoff exponencial para erros transientes |
| Timeout | `TimeoutScope` | O executor central deve impor ativamente o limite de tempo estipulado |
| Validação | `ValidationPolicy` | Validação de input/output com `Validator` |
| Permissão | `PermissionPolicy` | Controle de acesso; levanta `PermissionDeniedError` |
| Execução | `ExecutionPolicy` | Configurações globais de execução (timeout padrão) |
| Composição | `PolicyChain` | Compõe múltiplas políticas em cadeia via `PolicyEvaluator` |

---

## Etapa 3: Validação de contratos (Quality Assurance)

**User Story:**
> Como desenvolvedor, quero validar a integridade do meu projeto antes de gastar tokens com chamadas a LLMs, para detetar erros de configuração antecipadamente.

### Ações técnicas

O desenvolvedor executa o comando CLI `miniautogen check` para validar:

```
miniautogen check
miniautogen check --format json
```

**O que acontece:**

1. O CLI carrega o `miniautogen.yml`.
2. Executa uma bateria de validações:
   - Validação de sintaxe YAML
   - Resolução de agentes referenciados nos pipelines
   - Validação de integridade de pipelines (agentes existentes, planos válidos)
   - Verificação de dependências e configurações de backend
3. Retorna uma lista de `CheckResult` com status (PASS/FAIL), nome e mensagem.

**Resultado esperado:**

Se tudo estiver correto:
```
| Status | Check              | Message            |
|--------|--------------------|--------------------|
| PASS   | yaml_syntax        | Valid YAML         |
| PASS   | agent_resolution   | All agents found   |
| PASS   | pipeline_integrity | Pipeline valid     |

All 3 check(s) passed
```

Se houver erros, o CLI retorna exit code 1 com a lista de falhas.

---

## Etapa 4: Orquestração e execução (Ação)

**User Story:**
> Como desenvolvedor, quero submeter meus planos ao microkernel e acompanhar a execução via eventos, para ter controle total sobre o ciclo de vida de cada run.

### 4.1 Ciclo de vida do PipelineRunner

O `PipelineRunner` é o executor central do MiniAutoGen. O ciclo de vida de uma execução segue esta sequência:

1. **Geração do run_id** -- identificador único para a execução
2. **Persistência do estado inicial** -- o sistema persiste o estado com status `started`
3. **Emissão de `RUN_STARTED`** -- evento publicado via `EventSink`
4. **Verificação de ApprovalGate** (se configurado):
   - Emite `APPROVAL_REQUESTED`
   - Pausa e aguarda `ApprovalResponse`
   - Se `denied`: emite `APPROVAL_DENIED`, salva status `cancelled`, levanta `RuntimeError`
   - Se `granted`: emite `APPROVAL_GRANTED`, prossegue
5. **Execução do pipeline** -- o executor central deve impor ativamente o limite de tempo estipulado (se configurado)
6. **Tratamento de erros:**
   - `TimeoutError` -> salva status `timed_out`, emite `RUN_TIMED_OUT`
   - Qualquer outra `Exception` -> salva status `failed`, emite `RUN_FAILED`
7. **Sucesso:** salva status `finished`, salva checkpoint, emite `RUN_FINISHED`

### 4.2 Execução via CLI

```
miniautogen run main --timeout 300 --format json --verbose
```

O CLI resolve o pipeline pelo nome no `miniautogen.yml`, invoca a execução e exibe o resultado.

### 4.3 Sub-fluxos por modo de coordenação

#### Workflow (WorkflowRuntime)

1. Valida que todos os `agent_id` existem no registo
2. Emite `RUN_STARTED`
3. Se `fan_out=False`: executa steps sequencialmente, encadeando outputs
4. Se `fan_out=True`: o sistema deve orquestrar a execução em paralelo, garantindo isolamento de falhas
5. Se `synthesis_agent` definido: invoca o agente de síntese com os outputs coletados
6. Emite `RUN_FINISHED` com `RunResult(status=FINISHED)`

#### Deliberação (DeliberationRuntime)

1. Valida participantes e líder no registo
2. Emite `DELIBERATION_STARTED` com topic e participants
3. Para cada rodada (até `max_rounds`):
   a. Fase de contribuição: cada participante produz `ResearchOutput`
   b. Fase de peer review: cada participante revisa os outputs dos demais (produz `PeerReview`)
   c. Fase de consolidação: o líder consolida contribuições e reviews em `DeliberationState`
   d. Verificação de suficiência: se `is_sufficient=True`, encerra as rodadas
4. Produção do documento final: líder gera `FinalDocument` renderizado em Markdown
5. Emite `DELIBERATION_FINISHED`
6. Retorna `RunResult(status=FINISHED)` com metadata contendo o documento final e follow-up tasks

#### Agentic loop (AgenticLoopRuntime)

1. Valida router e participantes no registo
2. Emite `AGENTIC_LOOP_STARTED`
3. Inicializa `Conversation` com mensagem inicial (se configurada)
4. Para cada turno (até `max_turns`):
   a. Verifica condições de paragem contra a `ConversationPolicy`
   b. Router emite `RouterDecision` -> evento `ROUTER_DECISION`
   c. Se `terminate=True`: para com `ROUTER_TERMINATED`
   d. Se estagnação detetada: emite `STAGNATION_DETECTED`, para com `STAGNATION`
   e. Agente selecionado responde -> evento `AGENT_REPLIED`
   f. Atualiza `AgenticLoopState` (turn_count, active_agent, accepted_output)
5. Se timeout: para com `TIMEOUT`, emite `RUN_TIMED_OUT`
6. Emite `AGENTIC_LOOP_STOPPED` com `stop_reason` e `turns`
7. Retorna `RunResult(status=FINISHED)` com histórico da conversa

#### Composição (CompositeRuntime)

1. Para cada `CompositionStep` na sequência:
   a. Aplica `input_mapper` (se presente) ou `RunContext.with_previous_result()`
   b. Executa o runtime correspondente ao modo da etapa
   c. Aplica `output_mapper` (se presente)
   d. Se `RunStatus.FAILED`: retorna imediatamente (fail-fast)
2. Retorna o `RunResult` da última etapa

---

## Etapa 5: Integração com backends externos (Ação)

**User Story:**
> Como desenvolvedor, quero conectar meus agentes a provedores LLM externos e endpoints HTTP compatíveis com OpenAI, para que o MiniAutoGen gerencie a comunicação de forma transparente.

### 5.1 Camada de drivers

O MiniAutoGen abstrai backends externos através da interface `AgentDriver` (ABC), com seis métodos obrigatórios:

| Método | Função |
|--------|--------|
| `start_session(request)` | Inicia sessão com o backend, retorna `StartSessionResponse` |
| `send_turn(request)` | Envia turno e retorna `AsyncIterator[AgentEvent]` (async generator) |
| `cancel_turn(request)` | Cancela turno em andamento (pode levantar `CancelNotSupportedError`) |
| `list_artifacts(session_id)` | Lista artefatos produzidos na sessão |
| `close_session(session_id)` | Fecha e limpa a sessão |
| `capabilities()` | Reporta capacidades do driver (`BackendCapabilities`) |

### 5.2 AgentAPIDriver

O `AgentAPIDriver` é a implementação concreta para endpoints HTTP compatíveis com `/v1/chat/completions` (OpenAI API). Funciona com:

- Gemini CLI gateway
- LiteLLM proxy
- vLLM
- Ollama
- Qualquer endpoint OpenAI-compatible

O driver converte respostas do backend em `AgentEvent` canónico e aplica ativamente o limite de tempo estipulado na configuração.

### 5.3 BackendResolver

O `BackendResolver` é responsável pela resolução config-driven de drivers:

1. Recebe configurações via `add_backend(BackendConfig)`
2. Regista factories por `DriverType` via `register_factory()`
3. Resolve drivers sob demanda via `get_driver(backend_id)` com cache

Tipos de driver suportados (`DriverType`): `acp`, `agentapi`, `pty`.

### 5.4 SessionManager

O `SessionManager` gere o ciclo de vida de sessões com uma máquina de estados de 7 estados:

```
CREATED -> ACTIVE -> BUSY -> ACTIVE (loop) -> COMPLETED/FAILED -> CLOSED
```

Estados: `CREATED`, `ACTIVE`, `BUSY`, `INTERRUPTED`, `COMPLETED`, `FAILED`, `CLOSED`.

Transições são validadas pela máquina de estados. O estado `CLOSED` é acessível a partir de qualquer estado não-terminal.

### 5.5 Eventos de backend

O sistema emite 11 tipos de eventos específicos para backends:

`BACKEND_SESSION_STARTED`, `BACKEND_TURN_STARTED`, `BACKEND_MESSAGE_DELTA`, `BACKEND_MESSAGE_COMPLETED`, `BACKEND_TOOL_CALL_REQUESTED`, `BACKEND_TOOL_CALL_EXECUTED`, `BACKEND_ARTIFACT_EMITTED`, `BACKEND_WARNING`, `BACKEND_ERROR`, `BACKEND_TURN_COMPLETED`, `BACKEND_SESSION_CLOSED`.

---

## Etapa 6: Recuperação e Retomada (Durable Execution)

**User Story:**
> Como operador, quero retomar execuções que foram interrompidas por falhas de infraestrutura, para que o sistema continue do último ponto válido sem duplicar trabalho já realizado.

### Ações técnicas

Quando uma execução longa é interrompida, o sistema deve ser capaz de restaurar o estado a partir do último checkpoint transacional válido. O operador solicita a retomada da sessão, e o sistema:

1. Identifica o último checkpoint válido persistido no `CheckpointStore`
2. Restaura o `RunContext` exato desse ponto, incluindo outputs parciais e metadata
3. Marca a sessão como retomada via `mark_resumed()`
4. Retoma a execução a partir da etapa pendente, sem re-executar etapas já concluídas
5. Emite `CHECKPOINT_RESTORED` com o identificador do checkpoint utilizado

**Entidades envolvidas:** `SessionRecovery`, `CheckpointStore`, `RunContext`.

---

## Etapa 7: Operação, estado e observabilidade (Pós-Ação)

**User Story:**
> Como desenvolvedor, quero auditar execuções anteriores, gerir sessões e ter visibilidade completa sobre o que aconteceu em cada run, para operar o sistema com confiança.

### 7.1 Persistência de estado

O MiniAutoGen persiste estado em três stores, cada um com duas implementações (em memória e relacional):

| Store | Protocolo | Função |
|-------|-----------|--------|
| `RunStore` | `save_run()`, `get_run()` | Persiste metadados de cada execução (status, correlation_id, timestamps) |
| `CheckpointStore` | `save_checkpoint()`, `get_checkpoint()` | Persiste o resultado final de execuções bem-sucedidas |
| `MessageStore` | Herdado de `StoreProtocol` | Persiste mensagens trocadas durante conversas |

Adicionalmente, o `StoreProtocol` define a interface genérica key-value: `save()`, `get()`, `exists()`, `delete()`.

### 7.2 Sistema de eventos

O MiniAutoGen emite 42 tipos de eventos canónicos em 10 categorias, todos modelados como `ExecutionEvent`:

| Categoria | Quantidade | Exemplos |
|-----------|------------|----------|
| Run lifecycle | 5 | `RUN_STARTED`, `RUN_FINISHED`, `RUN_FAILED`, `RUN_CANCELLED`, `RUN_TIMED_OUT` |
| Component | 4 | `COMPONENT_STARTED`, `COMPONENT_FINISHED`, `COMPONENT_SKIPPED`, `COMPONENT_RETRIED` |
| Tool | 3 | `TOOL_INVOKED`, `TOOL_SUCCEEDED`, `TOOL_FAILED` |
| Storage | 2 | `CHECKPOINT_SAVED`, `CHECKPOINT_RESTORED` |
| Policies | 3 | `VALIDATION_FAILED`, `POLICY_APPLIED`, `BUDGET_EXCEEDED` |
| Adapters | 1 | `ADAPTER_FAILED` |
| Agentic loop | 5 | `AGENTIC_LOOP_STARTED`, `ROUTER_DECISION`, `AGENT_REPLIED`, `AGENTIC_LOOP_STOPPED`, `STAGNATION_DETECTED` |
| Deliberation | 4 | `DELIBERATION_STARTED`, `DELIBERATION_ROUND_COMPLETED`, `DELIBERATION_FINISHED`, `DELIBERATION_FAILED` |
| Backend drivers | 11 | `BACKEND_SESSION_STARTED`, `BACKEND_TURN_STARTED`, `BACKEND_MESSAGE_DELTA`, etc. |
| Approval | 4 | `APPROVAL_REQUESTED`, `APPROVAL_GRANTED`, `APPROVAL_DENIED`, `APPROVAL_TIMEOUT` |

Cada `ExecutionEvent` contém: `type`, `timestamp`, `run_id`, `correlation_id`, `scope`, `payload`.

### 7.3 Gestão de sessões via CLI

**Listar execuções:**

```
miniautogen sessions list
miniautogen sessions list --status finished --limit 10
miniautogen sessions list --format json
```

**Limpar execuções antigas:**

```
miniautogen sessions clean --older-than 30
miniautogen sessions clean --yes
```

O comando `clean` remove runs com status `completed`, `failed` ou `cancelled`. Exige `--older-than N` (dias) ou `--yes` para confirmação.

---

# Parte 2: Especificação BDD dos fluxos E2E

Os cenários a seguir descrevem os fluxos end-to-end em formato Gherkin, utilizando palavras-chave em português.

---

## Cenário 1: Execução E2E de workflow com sucesso

```gherkin
Funcionalidade: Execução completa de um workflow multiagente

  Cenário: Workflow sequencial com três agentes executa com sucesso
    Dado que o desenvolvedor executou "miniautogen init meu-projeto"
    E que o projeto contém um "miniautogen.yml" válido com um pipeline "main"
    E que três agentes estão definidos no diretório "agents/" implementando WorkflowAgent
    E que um WorkflowPlan está configurado com três WorkflowStep sequenciais
    Quando o desenvolvedor executa "miniautogen check"
    Então todos os checks devem passar com status PASS
    Quando o desenvolvedor executa "miniautogen run main"
    Então o PipelineRunner gera um run_id único
    E o evento RUN_STARTED é emitido via EventSink
    E o WorkflowRuntime executa cada step sequencialmente
    E cada agente recebe o output do agente anterior como input
    E o evento RUN_FINISHED é emitido
    E o RunResult retorna com status FINISHED
    E o estado é persistido no RunStore com status "finished"
```

---

## Cenário 2: Deliberação multiagente com convergência

```gherkin
Funcionalidade: Deliberação multiagente com peer review e convergência

  Cenário: Três especialistas deliberam e convergem em duas rodadas
    Dado que três agentes implementando DeliberationAgent estão registados
    E que um DeliberationPlan está configurado com topic "Arquitetura de microsserviços"
    E que max_rounds está definido como 5
    E que um leader_agent está designado
    Quando o DeliberationRuntime inicia a execução
    Então o evento DELIBERATION_STARTED é emitido com o topic e participants
    E na rodada 1, cada participante produz um ResearchOutput
    E cada participante revisa os outputs dos demais gerando PeerReview
    E o líder consolida contribuições e reviews em DeliberationState
    E o líder avalia a suficiência e determina is_sufficient=False
    E na rodada 2, o ciclo se repete com follow-up tasks
    E o líder determina is_sufficient=True
    Então o líder produz um FinalDocument com executive_summary e recommendations
    E o evento DELIBERATION_FINISHED é emitido
    E o RunResult retorna com status FINISHED
    E o metadata contém final_document e rendered_markdown
```

---

## Cenário 3: Agentic loop com terminação controlada

```gherkin
Funcionalidade: Loop agêntico com terminação pelo router

  Cenário: Router direciona conversa e termina após atingir objetivo
    Dado que um router_agent e dois participantes implementando ConversationalAgent estão registados
    E que um AgenticLoopPlan está configurado com max_turns=10 e goal definido
    E que uma initial_message está configurada
    Quando o AgenticLoopRuntime inicia a execução
    Então o evento AGENTIC_LOOP_STARTED é emitido
    E a Conversation é inicializada com a mensagem inicial
    E no turno 1, o router emite RouterDecision com next_agent="agente-a"
    E o evento ROUTER_DECISION é emitido
    E agente-a responde e o evento AGENT_REPLIED é emitido
    E no turno 2, o router emite RouterDecision com next_agent="agente-b"
    E agente-b responde
    E no turno 3, o router emite RouterDecision com terminate=True
    Então o loop para com stop_reason ROUTER_TERMINATED
    E o evento AGENTIC_LOOP_STOPPED é emitido com stop_reason e turns=3
    E o RunResult retorna com status FINISHED e o histórico da conversa

  Cenário: Loop agêntico para por estagnação
    Dado que um router_agent e dois participantes estão registados
    E que a ConversationPolicy define stagnation_window=2
    Quando o router emite RouterDecision com o mesmo next_agent em 2 turnos consecutivos
    Então o sistema deteta estagnação na conversa
    E o evento STAGNATION_DETECTED é emitido
    E o loop para com stop_reason STAGNATION

  Cenário: Loop agêntico para por max_turns
    Dado que a ConversationPolicy define max_turns=5
    Quando o loop atinge 5 turnos sem terminação pelo router
    Então o loop para com stop_reason MAX_TURNS
```

---

## Cenário 4: Composição de modos em sequência

```gherkin
Funcionalidade: Composição de workflow e deliberação via CompositeRuntime

  Cenário: Workflow de pesquisa seguido de deliberação seguido de workflow de publicação
    Dado que um CompositeRuntime está configurado com três CompositionStep:
      | label           | mode               | plan            |
      | pesquisa        | WorkflowRuntime    | WorkflowPlan    |
      | deliberação     | DeliberationRuntime| DeliberationPlan|
      | publicação      | WorkflowRuntime    | WorkflowPlan    |
    Quando o CompositeRuntime inicia a execução
    Então a etapa "pesquisa" executa o WorkflowRuntime e produz RunResult
    E o output é injetado no RunContext da próxima etapa via with_previous_result()
    E a etapa "deliberação" executa o DeliberationRuntime com o contexto atualizado
    E o output da deliberação é injetado no RunContext da etapa seguinte
    E a etapa "publicação" executa o WorkflowRuntime final
    E o RunResult final retorna com status FINISHED

  Cenário: Composição com falha na segunda etapa causa fail-fast
    Dado que a etapa "deliberação" falha com RunStatus.FAILED
    Quando o CompositeRuntime deteta o status FAILED
    Então a etapa "publicação" não é executada
    E o RunResult retorna com status FAILED e o erro da etapa que falhou
```

---

## Cenário 5: Execução com aprovação humana

```gherkin
Funcionalidade: Human-in-the-loop via ApprovalGate

  Cenário: Execução pausa para aprovação e prossegue após autorização
    Dado que o PipelineRunner está configurado com um ApprovalGate
    Quando o PipelineRunner inicia a execução do pipeline
    Então o evento RUN_STARTED é emitido
    E um ApprovalRequest é criado com action="run_pipeline"
    E o evento APPROVAL_REQUESTED é emitido com request_id e action
    E a execução pausa aguardando ApprovalResponse
    Quando o operador humano concede aprovação com decision="granted"
    Então o evento APPROVAL_GRANTED é emitido
    E a execução do pipeline prossegue normalmente
    E o RunResult retorna com status FINISHED

  Cenário: Execução é negada pelo operador
    Dado que o PipelineRunner está configurado com um ApprovalGate
    Quando o operador humano nega a aprovação com decision="denied" e reason="Custo excessivo"
    Então o evento APPROVAL_DENIED é emitido com o motivo
    E o estado do run é salvo com status "cancelled"
    E um RuntimeError é levantado com a mensagem de negação
```

---

## Cenário 6: Execução com falha e retry

```gherkin
Funcionalidade: Retry automático para erros transientes

  Cenário: Erro transiente é recuperado via RetryPolicy
    Dado que o PipelineRunner está configurado com uma RetryPolicy
    E que o pipeline falha na primeira tentativa com um erro classificado como transient
    Quando o sistema reescalona a execução automaticamente aplicando backoff exponencial
    Então o evento COMPONENT_RETRIED é emitido antes da nova tentativa
    E na segunda tentativa o pipeline executa com sucesso
    E o RunResult retorna com status FINISHED
    E o estado final no RunStore é "finished"

  Cenário: Erro permanente não é recuperável
    Dado que o pipeline falha com um erro classificado como permanent
    Quando o sistema identifica que o erro não é transiente
    Então o evento RUN_FAILED é emitido com error_type no payload
    E o estado do run é salvo com status "failed"
    E a exceção é propagada ao chamador
```

---

## Cenário 7: Timeout e cancelamento

```gherkin
Funcionalidade: Timeout estruturado na execução de pipelines

  Cenário: Pipeline excede o timeout configurado
    Dado que o PipelineRunner está configurado com timeout_seconds=60
    E que o pipeline demora mais de 60 segundos para executar
    Quando o executor central impõe ativamente o limite de tempo estipulado
    Então um TimeoutError é capturado pelo PipelineRunner
    E o estado do run é salvo com status "timed_out"
    E o evento RUN_TIMED_OUT é emitido
    E o TimeoutError é propagado ao chamador

  Cenário: Timeout herdado da ExecutionPolicy
    Dado que nenhum timeout explícito é passado à execução
    E que a ExecutionPolicy define timeout_seconds=120
    Quando o PipelineRunner resolve o timeout efetivo
    Então o timeout da ExecutionPolicy é utilizado (120 segundos)
```

---

## Cenário 8: Orçamento excedido

```gherkin
Funcionalidade: Controle de orçamento via BudgetPolicy

  Cenário: Custo acumulado excede o limite configurado
    Dado que um BudgetTracker está configurado com BudgetPolicy(max_cost=10.0)
    E que a execução acumula custos durante o processamento
    Quando o custo acumulado ultrapassa 10.0
    Então o sistema levanta BudgetExceededError
    E o evento BUDGET_EXCEEDED é emitido
    E a execução é interrompida

  Cenário: Verificação preventiva de orçamento
    Dado que o BudgetTracker registou 9.50 de custo com limite de 10.00
    Quando o saldo restante é consultado
    Então o valor retornado é 0.50
    E o sistema confirma que a execução ainda está dentro do orçamento
```

---

## Cenário 9: Gestão do ciclo de vida de sessões

```gherkin
Funcionalidade: Gestão de sessões via CLI

  Cenário: Listar runs recentes com filtro de status
    Dado que existem runs persistidos no RunStore com status "finished" e "failed"
    Quando o desenvolvedor executa "miniautogen sessions list --status finished --limit 5"
    Então uma tabela é exibida com colunas Run ID, Status e Created
    E apenas runs com status "finished" são exibidos
    E no máximo 5 resultados são retornados

  Cenário: Limpar runs antigos
    Dado que existem runs com mais de 30 dias com status "completed", "failed" ou "cancelled"
    Quando o desenvolvedor executa "miniautogen sessions clean --older-than 30"
    E confirma a deleção quando solicitado
    Então os runs correspondentes são removidos do RunStore
    E uma mensagem de sucesso exibe a quantidade de runs deletados

  Cenário: Limpeza requer confirmação ou flag --yes
    Dado que o desenvolvedor executa "miniautogen sessions clean" sem --older-than e sem --yes
    Então o CLI retorna erro solicitando "--older-than N ou --yes para confirmar deleção"
    E o exit code é 1
```

---

## Cenário 10: Execução durável e retomada de falhas

```gherkin
Funcionalidade: Execução durável e retomada de falhas

  Cenário: Retomada de execução a partir do último checkpoint válido
    Dado que um workflow longo foi interrompido por falha de infraestrutura externa
    E que o sistema salvou um checkpoint transacional da etapa anterior
    Quando o operador solicita a retomada da sessão
    Então o sistema deve recarregar o estado exato do último checkpoint
    E a execução deve continuar da etapa pendente sem duplicar efeitos colaterais anteriores
```

---

## Cenário 11: Integração com Gemini CLI via gateway local

```gherkin
Funcionalidade: Integração com backends via gateway local

  Cenário: Integração com Gemini CLI via gateway local
    Dado que o BackendResolver está configurado com um endpoint local do gemini_cli_gateway
    E que o gateway está a responder em formato OpenAI-compatible
    Quando o sistema submete um turno via AgentAPIDriver
    Então a resposta deve ser mapeada para AgentEvent canónico
    E os eventos BACKEND_TURN_STARTED e BACKEND_TURN_COMPLETED devem ser emitidos
```

---

# Parte 3: Especificação funcional

## 1. Título e contexto

### Título

Especificação Funcional E2E -- MiniAutoGen Framework

### Visão do produto

O MiniAutoGen é um framework Python orientado a Microkernel para orquestração de pipelines e agentes assíncronos. Permite que desenvolvedores definam agentes de forma declarativa, escolham modos de coordenação tipados e executem pipelines multiagente com observabilidade completa, políticas laterais e integração a backends LLM externos.

O framework está em evolução de uma "simples biblioteca de agentes" para um **microkernel de execução agêntica rigoroso**, incorporando progressivamente capacidades de **execução durável** (durable execution) -- incluindo interrupção, retomada e time travel de pipelines. Este posicionamento diferencia o MiniAutoGen de alternativas como o LangGraph, ao priorizar isolamento de contratos, observabilidade canónica e governança por políticas laterais sobre conveniência de prototipagem rápida.

### Objetivo estratégico

Fornecer uma plataforma de orquestração multiagente que seja:
- **Segura por design:** tipagem forte, validação antecipada, isolamento de adapters
- **Observável:** 42 tipos de eventos canónicos em 10 categorias
- **Extensível:** arquitetura microkernel com protocolos tipados
- **Operável:** CLI completo para scaffold, validação, execução e gestão de sessões
- **Durável:** evolução progressiva rumo a execução durável com interrupt/resume, checkpointing transacional e capacidade de time travel, posicionando o framework como alternativa rigorosa ao LangGraph e similares

### Métricas de sucesso

- Cobertura de testes acima de 90% para o core
- Zero vazamento de adapters concretos para o domínio
- Todos os modos de coordenação executáveis via CLI sem código customizado
- Rastreabilidade completa de cada run via eventos e stores

---

## 2. User scenarios e testing

### User story primária

> Como desenvolvedor de sistemas multiagente, quero orquestrar pipelines de agentes com diferentes modos de coordenação (workflow, deliberação, agentic loop, composição), para que eu possa modelar interações complexas entre agentes de forma declarativa e com observabilidade completa.

### Cenários de aceitação

Os cenários BDD da Parte 2 constituem os critérios de aceitação formais desta especificação. Cada cenário deve passar como teste de integração antes de considerar a feature como completa.

---

## 3. Requisitos funcionais

### Fases de entrega

Os requisitos funcionais estão organizados em três fases de entrega progressiva:

**Fase 1 -- Runtime Base:**
FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027, FR-028, FR-029, FR-030, FR-031

**Fase 2 -- Coordenação:**
FR-010, FR-011, FR-012

**Fase 3 -- Governança e Políticas:**
FR-013, FR-014, FR-015, FR-016, FR-017, FR-018, FR-019

---

### Scaffolding e configuração

**FR-001: Scaffold de projeto via CLI**
O comando `miniautogen init <nome>` deve criar a estrutura completa do projeto incluindo `miniautogen.yml`, diretórios `agents/`, `skills/`, `tools/`, `templates/` e exemplos opcionais. Aceita parâmetros `--model`, `--provider` e `--no-examples`.

**FR-002: Configuração declarativa de agentes**
Agentes devem ser definidos via `AgentSpec` com campos de identidade (`id`, `name`, `role`, `goal`), capacidades (`skills`, `tool_access`, `mcp_access`), políticas (`memory`, `delegation`, `runtime`, `permissions`) e referência a `engine_profile`.

**FR-003: Configuração declarativa de backends**
Backends devem ser definidos via `BackendConfig` com `backend_id`, `driver` (tipo `DriverType`: acp, agentapi, pty), `endpoint`, `command`, `auth` (tipo `AuthConfig`) e `capabilities_override`. A validação semântica por tipo de driver deve ocorrer em tempo de carregamento.

### Validação

**FR-004: Validação de integridade via CLI**
O comando `miniautogen check` deve validar YAML, resolver agentes, verificar integridade de pipelines e reportar resultados como lista de `CheckResult` (PASS/FAIL). Suporta output em texto e JSON (`--format`).

**FR-005: Validação antecipada de planos**
Cada runtime (WorkflowRuntime, DeliberationRuntime, AgenticLoopRuntime) deve validar o plano antes de emitir o evento de início. Planos com agentes não encontrados no registo devem retornar `RunResult(status=FAILED)` sem emitir eventos de início.

### Ciclo de vida de execução

**FR-006: Geração de run_id e rastreabilidade**
O `PipelineRunner` deve gerar um `run_id` e `correlation_id` únicos para cada execução. Ambos devem ser incluídos em todos os eventos e registos de store.

**FR-007: Emissão de eventos de ciclo de vida**
O `PipelineRunner` deve emitir os eventos `RUN_STARTED`, `RUN_FINISHED`, `RUN_FAILED`, `RUN_CANCELLED` e `RUN_TIMED_OUT` nos pontos apropriados do ciclo de vida.

**FR-008: Resultado tipado**
Toda execução deve produzir um `RunResult` com `run_id`, `status` (enum `RunStatus`: `FINISHED`, `FAILED`, `CANCELLED`, `TIMED_OUT`), `output`, `error` e `metadata`.

### Modos de coordenação

**FR-009: Workflow sequencial e paralelo**
O `WorkflowRuntime` deve executar `WorkflowStep` sequencialmente por padrão, ou em paralelo quando `fan_out=True`. Deve suportar `synthesis_agent` para consolidação de outputs paralelos.

**FR-010: Deliberação com peer review**
O `DeliberationRuntime` deve executar o ciclo completo: contribuição -> peer review -> consolidação -> suficiência -> documento final. Deve respeitar `max_rounds` e emitir eventos `DELIBERATION_STARTED`, `DELIBERATION_ROUND_COMPLETED`, `DELIBERATION_FINISHED`, `DELIBERATION_FAILED`.

**FR-011: Agentic loop com router**
O `AgenticLoopRuntime` deve executar um loop dirigido pelo router com quatro condições de paragem: `ROUTER_TERMINATED`, `STAGNATION`, `MAX_TURNS`, `TIMEOUT`. Deve emitir eventos `AGENTIC_LOOP_STARTED`, `ROUTER_DECISION`, `AGENT_REPLIED`, `AGENTIC_LOOP_STOPPED`, `STAGNATION_DETECTED`.

**FR-012: Composição de modos**
O `CompositeRuntime` deve encadear `CompositionStep` em sequência, propagando output via `RunContext.with_previous_result()`. Deve suportar `input_mapper` e `output_mapper` customizados. Deve implementar fail-fast em caso de `RunStatus.FAILED`.

### Políticas

**FR-013: Aprovação human-in-the-loop**
O `PipelineRunner` deve suportar `ApprovalGate` opcional. Quando configurado, deve emitir `APPROVAL_REQUESTED`, pausar execução e aguardar `ApprovalResponse`. Se `denied`, deve emitir `APPROVAL_DENIED`, salvar status `cancelled` e levantar `RuntimeError`.

**FR-014: Controle de orçamento**
O `BudgetTracker` deve rastrear custos e levantar `BudgetExceededError` quando o limite `max_cost` for excedido. O evento `BUDGET_EXCEEDED` deve ser emitido.

**FR-015: Retry com backoff exponencial**
O `PipelineRunner` deve suportar `RetryPolicy` opcional. Quando configurado, o sistema deve reescalonar a execução automaticamente aplicando backoff exponencial. O evento `COMPONENT_RETRIED` deve ser emitido antes de cada nova tentativa.

A `RetryPolicy` atua exclusivamente sobre falhas classificadas como `transient` ou `adapter` (quando configurado). Falhas do tipo `state_consistency`, `validation` ou `permanent` causam interrupção imediata sem repetição. A taxonomia canónica de erros compreende 8 tipos: `transient`, `permanent`, `validation`, `timeout`, `cancellation`, `adapter`, `configuration`, `state_consistency`.

**FR-016: Timeout estruturado**
O executor central deve impor ativamente o limite de tempo estipulado. O timeout pode vir do parâmetro `timeout_seconds` ou da `ExecutionPolicy`. Em caso de `TimeoutError`, deve salvar status `timed_out` e emitir `RUN_TIMED_OUT`.

**FR-017: Validação de input/output**
A `ValidationPolicy` deve permitir validação customizada via `Validator`. Erros de validação devem emitir `VALIDATION_FAILED`.

**FR-018: Controle de permissões**
A `PermissionPolicy` deve verificar permissões antes da execução. Violações devem levantar `PermissionDeniedError`.

**FR-019: Composição de políticas**
A `PolicyChain` deve compor múltiplas políticas em cadeia, avaliadas sequencialmente via `PolicyEvaluator`.

### Persistência

**FR-020: Persistência de estado de execução**
O `RunStore` deve persistir metadados de cada run (status, correlation_id). Implementações disponíveis: em memória e relacional.

**FR-021: Persistência de checkpoints**
O `CheckpointStore` deve persistir o resultado final de execuções bem-sucedidas. Implementações disponíveis: em memória e relacional.

**FR-022: Persistência de mensagens**
O `MessageStore` deve persistir mensagens trocadas em conversas. Implementações disponíveis: em memória e relacional.

### Observabilidade

**FR-023: Sistema de eventos canónicos**
O framework deve emitir 42 tipos de eventos em 10 categorias via `EventSink`. Cada evento deve ser modelado como `ExecutionEvent` com `type`, `timestamp`, `run_id`, `correlation_id`, `scope` e `payload`.

**FR-024: Filtragem de eventos**
O módulo de eventos deve permitir filtragem de eventos por tipo, categoria e critérios customizados.

### CLI e operações

**FR-025: Execução headless via CLI**
O comando `miniautogen run <pipeline>` deve executar o pipeline nomeado sem interação, com suporte a `--timeout`, `--format` (text/json) e `--verbose`.

**FR-026: Listagem de sessões**
O comando `miniautogen sessions list` deve listar runs com filtros opcionais `--status` e `--limit` (1-1000, padrão 20). Suporta output em texto (tabela) e JSON.

**FR-027: Limpeza de sessões**
O comando `miniautogen sessions clean` deve remover runs com status terminal. Exige `--older-than N` (dias) ou `--yes` para confirmação.

### Integração com backends

**FR-028: Interface AgentDriver**
Todos os drivers de backend devem implementar a ABC `AgentDriver` com os seis métodos: `start_session`, `send_turn`, `cancel_turn`, `list_artifacts`, `close_session`, `capabilities`.

**FR-029: Driver HTTP para endpoints OpenAI-compatible**
O `AgentAPIDriver` deve conectar a endpoints `/v1/chat/completions`, converter respostas em `AgentEvent` canónico e impor ativamente o limite de tempo estipulado na configuração.

**FR-030: Resolução config-driven de backends**
O `BackendResolver` deve resolver `backend_id` para instâncias de `AgentDriver` com cache. Deve levantar `BackendUnavailableError` se o backend não estiver configurado ou a factory não estiver registada.

**FR-031: Gestão de ciclo de vida de sessões**
O `SessionManager` deve gerir sessões com máquina de estados de 7 estados, validar transições e suportar listagem por estado.

---

## 4. Requisitos não funcionais

**NFR-001 (Observabilidade):** 100% dos 42 tipos de eventos emitidos devem conter `correlation_id` e `timestamp` preenchidos.

**NFR-002 (Performance de Policies):** Políticas transversais devem operar lateralmente sem latência bloqueante significativa (< 10ms de overhead por componente).

**NFR-003 (Isolamento de Erros):** Falhas do tipo `adapter` (fronteira externa) não devem corromper o `RunContext` interno.

**NFR-004 (Serialização):** Todo estado persistido em stores deve ser serializável de forma estável e versionável.

**NFR-005 (Determinismo):** Dado o mesmo input e estado inicial, a execução do pipeline deve produzir a mesma sequência de eventos canónicos.

---

## 5. Entidades-chave

| Entidade | Módulo | Papel no fluxo E2E |
|----------|--------|---------------------|
| `AgentSpec` | `core.contracts.agent_spec` | Definição declarativa de um agente (identidade, capacidades, políticas) |
| `WorkflowPlan` | `core.contracts.coordination` | Plano de execução para workflow (steps, fan_out, synthesis_agent) |
| `DeliberationPlan` | `core.contracts.coordination` | Plano de deliberação (topic, participants, max_rounds, leader_agent) |
| `AgenticLoopPlan` | `core.contracts.coordination` | Plano de agentic loop (router_agent, participants, policy, goal) |
| `CompositionStep` | `core.runtime.composite_runtime` | Etapa de composição (mode, plan, label, mappers) |
| `RunContext` | `core.contracts.run_context` | Contexto tipado de execução (run_id, correlation_id, input_payload) |
| `RunResult` | `core.contracts.run_result` | Resultado terminal (run_id, status, output, error, metadata) |
| `ExecutionEvent` | `core.contracts.events` | Evento canónico (type, timestamp, run_id, correlation_id, scope, payload) |
| `PipelineRunner` | `core.runtime.pipeline_runner` | Executor central do microkernel |
| `WorkflowRuntime` | `core.runtime.workflow_runtime` | Coordenador de workflows sequenciais/paralelos |
| `DeliberationRuntime` | `core.runtime.deliberation_runtime` | Coordenador de deliberação multiagente |
| `AgenticLoopRuntime` | `core.runtime.agentic_loop_runtime` | Coordenador de loops conversacionais |
| `CompositeRuntime` | `core.runtime.composite_runtime` | Compositor de modos de coordenação |
| `AgentDriver` | `backends.driver` | Interface ABC para drivers de backend |
| `AgentAPIDriver` | `backends.agentapi.driver` | Driver HTTP para endpoints OpenAI-compatible |
| `BackendResolver` | `backends.resolver` | Resolução config-driven de drivers com cache |
| `SessionManager` | `backends.sessions` | Máquina de estados para ciclo de vida de sessões |
| `RouterDecision` | `core.contracts.agentic_loop` | Decisão do router (next_agent, terminate, stagnation_risk) |
| `ConversationPolicy` | `core.contracts.agentic_loop` | Limites da conversa (max_turns, budget_cap, timeout, stagnation_window) |
| `FinalDocument` | `core.contracts.deliberation` | Documento final de deliberação (sumário executivo, factos, recomendações) |
| `BudgetTracker` | `policies.budget` | Rastreador de custo com limite via BudgetPolicy |
| `ApprovalGate` | `policies.approval` | Gate de aprovação human-in-the-loop |
| `PolicyChain` | `policies.chain` | Composição de políticas em cadeia |
| `SubrunRequest` | `core.contracts` | **Contrato experimental** -- não é consumido pelos runtimes no estado atual; sujeito a alterações sem aviso |
| `SessionRecovery` | `core.contracts` | **Contrato com integração incompleta** -- exportada na API pública mas a integração com os runtimes é incompleta |

---

## 6. Dependências e pressupostos

### Dependências externas

- **Python 3.10+** -- versão mínima suportada
- **AnyIO** -- concorrência assíncrona (obrigatório; asyncio ou trio como backend)
- **Click** -- framework CLI
- **httpx** (opcional) -- cliente HTTP para comunicação com backends

### Pressupostos

- O desenvolvedor possui credenciais configuradas para o provider LLM escolhido (variáveis de ambiente ou token_env no AuthConfig)
- Para persistência relacional, o banco de dados deve estar acessível e migrado
- O endpoint do backend (para `AgentAPIDriver`) deve estar disponível e compatível com `/v1/chat/completions`
- O ambiente de execução suporta AnyIO (asyncio ou trio)

### Pressupostos técnicos (limitações da Fase 1)

- O `SessionManager` não é concurrency-safe na Fase 1; race conditions são possíveis em cenários de alta concorrência. Será corrigido em fase posterior.
- O `SessionManager` não tem limite máximo de sessões ativas, o que pode levar a crescimento ilimitado de memória em cenários prolongados.

---

## 7. Fora de escopo

Esta especificação **não** cobre:

- **Lógica interna de agentes** -- como um agente decide o que responder, qual prompt utilizar ou como processar inputs. Isso é responsabilidade da implementação do agente.
- **Detalhes de implementação de adapters** -- a conversão interna entre formatos de providers LLM e o formato canónico do MiniAutoGen.
- **Interface gráfica** -- o MiniAutoGen opera exclusivamente via SDK Python e CLI.
- **Deploy e infraestrutura** -- configuração de servidores, containers, CI/CD ou ambientes cloud.
- **Segurança de rede** -- TLS, firewalls, VPNs ou isolamento de rede entre agentes e backends.
- **Migração de banco de dados** -- schemas e migração para stores relacionais.

---

## 8. Riscos conhecidos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| `ApprovalGate` é fail-open por design no SDK | Execuções sem gate configurado procedem sem aprovação | Comportamento documentado e intencional para flexibilidade |
| `AgentAPIDriver` não suporta streaming nem cancelamento | Perda de latência percebida e impossibilidade de cancelar chamadas HTTP em andamento | Capacidades declaradas como `False` em `BackendCapabilities`; streaming planejado para fases futuras |
| Contratos experimentais (`SubrunRequest`) podem mudar sem aviso | Código dependente pode quebrar em atualizações | Marcado explicitamente como experimental; não é consumido pelos runtimes no estado atual |
| `SessionRecovery` tem integração incompleta com runtimes | A funcionalidade de retomada pode não funcionar em todos os cenários | Exportada na API pública com documentação explícita sobre limitações; integração plena planejada para fases futuras |
| Evolução para durable execution ainda é incremental | Expectativas de interrupt/resume podem exceder capacidades atuais | Roadmap claro com fases definidas; funcionalidades avançadas de time travel em fases posteriores |

---

## 9. Clarificações necessárias

Para esta versão, não há pendências críticas de regras de negócio. As questões em aberto referem-se a fluxos experimentais e evolução futura:

- **SubrunRequest no CLI:** Como o `SubrunRequest` será rastreado e exibido no CLI na próxima versão? Atualmente o contrato existe mas não é consumido pelos runtimes.
- **Versionamento de checkpoints:** Qual o comportamento esperado quando um checkpoint é restaurado com uma versão de schema diferente da atual? É necessário definir uma política de compatibilidade ou migração automática.
- **Limites de SessionRecovery:** Até que ponto a retomada de sessão deve reconstruir o estado de policies laterais (budget acumulado, contagem de retries)?

---

## 10. Fontes consultadas

- **Código-fonte do MiniAutoGen** -- módulos `core/`, `backends/`, `policies/`, `stores/`, `cli/`, `observability/`
- Contratos de coordenação: `WorkflowPlan`, `DeliberationPlan`, `AgenticLoopPlan`
- Modelo de eventos: `ExecutionEvent`, enum `EventType` (42 tipos)
- Enums de domínio: `RunStatus`, `LoopStopReason`
- Runtimes: `PipelineRunner`, `WorkflowRuntime`, `DeliberationRuntime`, `AgenticLoopRuntime`, `CompositeRuntime`
- Backends: `AgentDriver` (ABC), `AgentAPIDriver`, `BackendResolver`, `SessionManager`
- Políticas: módulo de políticas (`BudgetPolicy`, `ApprovalGate`, `RetryPolicy`, etc.)
- CLI: comandos `init`, `check`, `run`, `sessions`

---

## 11. Review e acceptance checklist (GATE)

- [ ] Todos os cenários BDD descrevem fluxos verificáveis como comportamento observável (caixa-preta)
- [ ] Cada requisito funcional (FR-001 a FR-031) é rastreável a um contrato ou comportamento do sistema
- [ ] Os quatro modos de coordenação estão documentados com seus contratos tipados
- [ ] Os 42 tipos de eventos estão contabilizados e categorizados
- [ ] Os valores do enum `RunStatus` (`FINISHED`, `FAILED`, `CANCELLED`, `TIMED_OUT`) estão corretos
- [ ] Os valores do enum `LoopStopReason` (`MAX_TURNS`, `ROUTER_TERMINATED`, `STAGNATION`, `TIMEOUT`) estão corretos
- [ ] Os 7 estados do `SessionManager` (`CREATED`, `ACTIVE`, `BUSY`, `INTERRUPTED`, `COMPLETED`, `FAILED`, `CLOSED`) estão corretos
- [ ] As 8 políticas estão documentadas com seus nomes de classe corretos
- [ ] Os comandos CLI correspondem à implementação real (init, check, run, sessions list, sessions clean)
- [ ] Dependências externas e pressupostos estão documentados
- [ ] Riscos conhecidos refletem limitações reais e incluem contratos experimentais
- [ ] Requisitos não funcionais (NFR-001 a NFR-005) estão definidos e mensuráveis
- [ ] O documento não contém referências a funções ou bibliotecas de implementação
- [ ] Todos os nomes de classes e enums correspondem ao vocabulário de domínio verificado
- [ ] Contratos experimentais (`SubrunRequest`, `SessionRecovery`) estão explicitamente sinalizados
- [ ] A taxonomia canónica de 8 tipos de erro está referenciada no FR-015
