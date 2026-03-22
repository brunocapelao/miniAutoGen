# AgentRuntime Agnóstico + Invariantes Reforçadas

> **Data:** 2026-03-21
> **Status:** Aprovado
> **Motivação:** O AgentRuntime atual viola o pilar 2 ("o agente é o que ele já é") ao hardcodar prompts de coordenação e forçar formato JSON em todas as interações. Isto limita o framework a um único padrão de uso e contradiz a missão de runtime genérico multi-provider.

---

## Princípio Arquitetural

**O AgentRuntime é compositor, não instrutor.**

O AgentRuntime enriquece o prompt com contexto local (memória, tools, system prompt) e delega ao backend driver. Nunca dita ao agente o formato de resposta nem constrói prompts de coordenação. A coordenação (como os agentes interagem) é responsabilidade do Coordination Runtime. O formato de resposta é propriedade do Flow.

---

## Camadas de Customização

Resolução em cascata — primeiro match vence:

```
InteractionStrategy (Python) → YAML prompt templates → Built-in defaults
```

### 1. InteractionStrategy Protocol

Protocol runtime-checkable em `core/contracts/` com dois métodos:

```python
@runtime_checkable
class InteractionStrategy(Protocol):
    async def build_prompt(self, action: str, context: dict[str, Any]) -> str:
        """Construct the prompt for a coordination action (contribute, review, etc.)."""
        ...

    async def parse_response(self, action: str, raw: str) -> Any:
        """Parse the agent's response into the expected structure."""
        ...
```

Injetável via Python para casos avançados (multi-modal, tool calling nativo, custom parsing).

### 2. YAML Prompt Templates

Definidos no Flow config (preferido) ou no agent YAML:

```yaml
flows:
  review:
    mode: deliberation
    response_format: free_text
    prompts:
      contribute: "Review {topic} from your perspective as {role}."
      review: "Evaluate {target}'s contribution: {content}"
      consolidate: "Synthesize all reviews on {topic}."
```

Templates suportam variáveis: `{topic}`, `{role}`, `{target}`, `{content}`, `{agent_id}`.

### 3. Built-in Defaults

Os prompts hardcoded atuais tornam-se fallback de último recurso. Garantem que o framework funciona out-of-the-box sem configuração explícita.

---

## response_format no FlowConfig

Propriedade do Flow, não do Agent. O mesmo agente pode participar em flows com formatos diferentes.

| Formato | Comportamento | Quando usar |
|---------|-------------|-------------|
| `free_text` | Resposta crua, sem parsing | Agentes CLI, brainstorming, creative |
| `json` | Tenta parsear JSON, fallback para texto livre | Structured outputs, decisões |
| `structured` | Valida contra Pydantic schema definido no flow | Contratos tipados, integração |

O **Coordination Runtime** (WorkflowRuntime, DeliberationRuntime, etc.) é responsável pelo parsing conforme o `response_format`. O AgentRuntime devolve a resposta crua.

---

## Mudanças no AgentRuntime

### Remove (prompts hardcoded)

Os métodos `contribute()`, `review()`, `consolidate()`, `produce_final_document()` deixam de construir prompts internamente. Passam a:

1. Receber o prompt pronto do Coordination Runtime
2. Enriquecer com contexto local (memória, system prompt, tools)
3. Enviar ao backend driver via `_execute_turn()`
4. Devolver resposta crua

### Mantém (compositor)

- `_build_messages()` — constrói lista de mensagens com system prompt e memória
- `_execute_turn()` — executa chamada ao backend driver
- Lifecycle (init, close, memory load/save)
- Tool registry, delegation, permissions

### Novo método genérico

```python
async def execute(self, prompt: str) -> str:
    """Execute a prompt and return raw response. No parsing, no format assumptions."""
    self._check_closed()
    messages = self._build_messages(prompt)
    result = await self._execute_turn(messages)
    return result.text
```

Os métodos `contribute()`, `review()`, etc. tornam-se convenience wrappers que:
1. Resolvem o prompt via InteractionStrategy → YAML → default
2. Chamam `execute(prompt)`
3. Devolvem resposta crua (parsing é do Coordination Runtime)

---

## Mudanças nos Coordination Runtimes

### WorkflowRuntime

Passa a construir prompts para cada step e parsear respostas conforme `response_format` do flow.

### DeliberationRuntime

Passa a:
- Construir prompts de contribute, review, consolidate, produce_final_document
- Parsear respostas conforme `response_format`
- Usar `InteractionStrategy` se fornecida, senão YAML templates, senão defaults

### AgenticLoopRuntime

Idem — prompts de routing e decisão movidos para o runtime.

---

## Novas Invariantes

### CLAUDE.md §4 — Nova regra de rejeição

> **5.** Adicionar prompts hardcoded ou lógica de parsing de resposta no `AgentRuntime`. Prompts de coordenação pertencem ao Coordination Runtime ou ao Flow config. O AgentRuntime é compositor, não instrutor.

### architecture/09-invariantes-sistema-operacional.md

> **INV-7: Separação Prompt↔Runtime** — O AgentRuntime NUNCA dita ao agente o formato de resposta ou constrói prompts de coordenação. Prompts de coordenação (contribute, review, consolidate) são responsabilidade do Coordination Runtime. O AgentRuntime enriquece com contexto local (memória, tools, system prompt) e delega ao backend.

> **INV-8: Formato pertence ao Flow** — O `response_format` é propriedade do Flow config, não do Agent. O mesmo agente pode participar em flows que esperam JSON e flows que esperam texto livre. O Coordination Runtime adapta o parsing conforme o `response_format` do flow.

---

## Impacto nos Ficheiros

| Componente | Ficheiro | Tipo de mudança |
|-----------|---------|----------------|
| InteractionStrategy | `miniautogen/core/contracts/interaction.py` | Novo |
| FlowConfig | `miniautogen/cli/config.py` | Adicionar `response_format`, `prompts` |
| AgentRuntime | `miniautogen/core/runtime/agent_runtime.py` | Refactor (extrair prompts) |
| WorkflowRuntime | `miniautogen/core/runtime/workflow_runtime.py` | Mover prompt construction para cá |
| DeliberationRuntime | `miniautogen/core/runtime/deliberation_runtime.py` | Mover prompt construction para cá |
| CLAUDE.md | `CLAUDE.md` | Adicionar regra §4.5 |
| Invariantes SO | `docs/pt/architecture/09-invariantes-sistema-operacional.md` | INV-7, INV-8 |
| Testes | `tests/core/runtime/` | Atualizar para novo contrato |

---

## Clarificações (do spec review)

### M1: `route()` incluído no scope

O método `route()` em `agent_runtime.py` contém o mesmo padrão de prompt hardcoded E não tem fallback defensivo (ao contrário de contribute/review). Deve ser incluído na extração — o routing prompt move-se para `AgenticLoopRuntime`.

### M2: Evolução dos Protocols — Option A (backward compat)

Os convenience wrappers (`contribute()`, `review()`, etc.) **mantêm as assinaturas actuais** (`-> Contribution`, `-> Review`). Internamente:
1. Resolvem o prompt via cascade (Strategy → YAML → default)
2. Chamam `execute(prompt)` para obter resposta crua
3. Parseiam a resposta conforme `response_format` do flow (se disponível) ou default JSON

Isto preserva os protocols `DeliberationAgent`, `ConversationalAgent` existentes. Os Coordination Runtimes **podem** usar `execute()` directamente para bypass total, mas os wrappers continuam a funcionar para backward compat.

### M3: `structured` requer `response_schema`

Para `response_format: structured`, o FlowConfig ganha um campo opcional:

```yaml
flows:
  typed-review:
    mode: deliberation
    response_format: structured
    response_schema: "miniautogen.core.contracts.deliberation.Contribution"
```

Tipo Pydantic: `response_schema: str | None = None` — Python dotted path para a classe Pydantic.

### M4: Template variables para acções complexas

Actions como `consolidate` e `produce_final_document` requerem inputs estruturados que não cabem em templates simples. Estas acções:
- YAML templates podem usar `{contributions_summary}` e `{reviews_summary}` — strings pré-formatadas pelo Coordination Runtime antes da substituição
- Para controlo total, usar `InteractionStrategy` (Python)
- Documentar esta limitação: "YAML templates são suficientes para contribute/review. Para consolidate/final_document com inputs complexos, use InteractionStrategy."

---

## Critérios de Sucesso

1. O tamagotchi E2E demo funciona sem alterações no `run.py`
2. Um novo flow pode definir `response_format: free_text` e o agente devolve texto cru sem JSON parsing
3. Um utilizador pode fornecer `InteractionStrategy` customizada via Python
4. Nenhum prompt hardcoded resta no `AgentRuntime`
5. 100% dos testes existentes continuam a passar (backward compat via built-in defaults)
6. As invariantes INV-7 e INV-8 são verificáveis por grep no codebase
