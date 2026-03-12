# Matriz Tecnológica

## Objetivo

Esta matriz organiza as principais escolhas tecnológicas candidatas para a evolução do MiniAutoGen, relacionando cada tecnologia à camada do framework, seu papel arquitetural e os trade-offs relevantes.

## Legenda de decisão

- `Adotar`: recomendação principal para a arquitetura alvo.
- `Adotar opcionalmente`: recomendado apenas em casos específicos ou em etapa posterior.
- `Avaliar`: promissor, mas depende de experimento ou benchmark interno.
- `Evitar no core`: pode ser útil, mas não como fundação do núcleo.

## Matriz resumida

| Camada | Tecnologia | Decisão | Papel principal |
| --- | --- | --- | --- |
| Contratos e modelos | Pydantic v2 | Adotar | Contratos públicos, validação e schemas |
| Serialização de hot path | msgspec | Adotar opcionalmente | Eventos e payloads internos de alto volume |
| Runtime assíncrono | AnyIO | Adotar | Cancelamento, task groups, timeouts |
| HTTP e adapters | HTTPX | Adotar | Cliente HTTP sync/async e integrações externas |
| HTTP de baixo nível | HTTPCore | Evitar como default | Casos especiais de transporte |
| LLM abstraction | LiteLLM | Adotar | Adapter provider-agnostic para LLM |
| Structured output | Instructor | Adotar opcionalmente | Parsing estruturado validado por Pydantic |
| Reliability layer | Guardrails | Evitar no core | Policy opcional de validação e governança |
| Persistência | SQLAlchemy 2.x + Psycopg 3 | Adotar | Stores duráveis e async |
| Retry | Tenacity | Adotar | Retry lateral por policy |
| Observabilidade | OpenTelemetry | Adotar em fase posterior | Exportação padrão de telemetria após estabilização de eventos |
| Logging estruturado | structlog | Adotar | Logs com contexto e integração com stdlib |
| DX local e CLI | Rich | Adotar opcionalmente | Tracebacks e logging local |
| Templates | Jinja | Adotar | Renderização textual via adapter |
| Protocolos de tools | MCP Python SDK | Adotar opcionalmente | Integração tardia de tools/resources por protocolo |
| Testes | pytest | Adotar | Base de testes |
| Async tests | pytest-asyncio | Adotar | Testes assíncronos |
| Testes baseados em propriedades | Hypothesis | Adotar | Invariantes e stateful testing |
| Cobertura | coverage.py | Adotar | Medição de cobertura |
| Mocking | unittest.mock | Adotar | Mocking padrão e estável |
| Lint/format | Ruff | Adotar | Lint e formatação integrados |
| Type checking | MyPy | Adotar | Baseline madura para typing avançado |
| Type checking | ty | Avaliar | Candidato futuro por performance e DX |
| Gestão de projeto | uv | Adotar | Ambiente, lockfile e workflow moderno |
| Documentação | MkDocs Material + mkdocstrings | Adotar | Docs técnicas e referência |

## Análise detalhada por camada

### 1. Contratos e modelos

#### Tecnologia recomendada: `Pydantic v2`

**Papel no framework**

- definir contratos públicos do core;
- modelar envelopes de execução;
- gerar JSON Schema;
- validar entrada e saída de APIs internas e adapters.

**Por que encaixa**

- já existe uso de Pydantic no projeto;
- combina com contracts-first;
- reduz ambiguidade na superfície pública;
- ajuda na futura evolução para structured outputs, eventos e configuração.

**Onde aplicar**

- `Message`, `ChatState`, `AgentConfig`;
- futuros `AgentSpec`, `RunContext`, `ExecutionEvent`, `ToolInvocation`, `RunResult`;
- settings e configuração externa.

**Riscos**

- adoção parcial pode manter duas linguagens de contrato no projeto;
- excesso de modelos pode aumentar atrito se não houver disciplina de fronteira;
- o time pode confundir “ter modelos” com “ter contratos bons”.

**Restrições de uso**

- usar preferencialmente na fronteira pública;
- separar entidades de domínio, envelopes de execução e DTOs de borda;
- evitar transformar toda estrutura interna em `BaseModel` sem ganho claro;
- definir invariantes antes de proliferar classes.

**Alternativas**

- dataclasses puras;
- TypedDict;
- attrs;
- `msgspec.Struct` para uso mais interno e performance-critical.

**Decisão sugerida**

Adotar `Pydantic v2` como linguagem padrão dos contratos públicos do framework.

#### Tecnologia complementar: `msgspec`

**Papel no framework**

- otimizar serialização e validação em hot paths;
- representar eventos internos muito frequentes;
- melhorar checkpointing ou envelopes de execução de alto volume.

**Por que encaixa**

- é pequena, rápida e muito especializada;
- ajuda quando o gargalo deixa de ser domínio e passa a ser transporte ou serialização.

**Riscos**

- introduz uma segunda linguagem de modelagem;
- aumenta custo cognitivo se usada cedo demais.

**Decisão sugerida**

Manter fora do core por enquanto e introduzir apenas mediante benchmark.

### 2. Runtime assíncrono e concorrência

#### Tecnologia recomendada: `AnyIO`

**Papel no framework**

- runtime estruturado do pipeline;
- gestão de task groups;
- timeouts;
- cancelamento;
- shutdown coordenado.

**Por que encaixa**

- corrige um ponto estrutural do projeto atual: o runtime ainda depende diretamente de `asyncio` e espalha a disciplina operacional;
- melhora robustez sem empurrar o projeto para um framework pesado;
- conversa bem com mentalidade corporativa minimalista.

**Onde aplicar**

- `PipelineRunner`;
- execução concorrente de ferramentas;
- timeouts por execução;
- cancel scopes por run, por component e por tool.

**Riscos**

- requer reorganizar o runtime e as APIs de execução;
- exige que o time entenda cancelamento estruturado;
- não é substituição neutra de `asyncio`, e sim mudança de disciplina operacional.

**Escopo recomendado de introdução**

1. primeiro no `PipelineRunner`;
2. depois na execução concorrente de tools;
3. só depois em superfícies secundárias.

**Cuidados de migração**

- evitar expor AnyIO desnecessariamente na API pública inicial;
- manter wrappers ou facades quando necessário para preservar compatibilidade;
- revisar testes e shutdown antes de expandir seu uso.

**Alternativas**

- `asyncio` puro;
- Trio diretamente, o que reduziria interoperabilidade com o ecossistema predominante.

**Decisão sugerida**

Adotar como fundação do runtime assíncrono.

### 3. HTTP, adapters e integrações externas

#### Tecnologia recomendada: `HTTPX`

**Papel no framework**

- cliente HTTP oficial para adapters;
- base de integração com LLMs, webhooks e ferramentas externas.

**Por que encaixa**

- API coesa;
- suporte sync/async;
- bom modelo de timeouts e clients reutilizáveis;
- ótimo equilíbrio entre ergonomia e controle.

**Onde aplicar**

- providers internos próprios;
- adapters de tools;
- comunicação com endpoints corporativos;
- integrações HTTP do framework.

**Riscos**

- uso descuidado de clients por request pode degradar performance;
- adapters mal desenhados podem vazar semântica HTTP para o domínio.

**Decisão sugerida**

Adotar como cliente HTTP padrão do framework.

#### Tecnologia complementar: `HTTPCore`

**Papel no framework**

- base de transporte muito baixo nível para casos especiais.

**Decisão sugerida**

Não usar como escolha padrão. Só considerar em necessidades avançadas de transporte customizado.

### 4. Camada LLM

#### Tecnologia recomendada: `LiteLLM`

**Papel no framework**

- adapter provider-agnostic para modelos;
- redução de acoplamento com vendors.

**Por que encaixa**

- já está presente no projeto;
- alinha com a visão de borda adaptável;
- evita que o core fale com APIs de fornecedor diretamente.

**Onde aplicar**

- `LLMProviderProtocol`;
- adapter oficial padrão para múltiplos providers;
- políticas de retry e observabilidade na borda.

**Riscos**

- confiar demais na semântica da lib e deixar de definir um contrato próprio do domínio;
- permitir que modelos e argumentos de vendor vazem para o core.

**Restrições de uso**

- exceções LiteLLM não devem atravessar a fronteira do adapter;
- argumentos específicos de provider não devem se tornar contrato do domínio;
- o core deve falar com um `LLMProviderProtocol`, não com a API da biblioteca.

**Decisão sugerida**

Manter e fortalecer como adapter de LLM, não como fundamento conceitual do domínio.

#### Tecnologia complementar: `Instructor`

**Papel no framework**

- structured outputs validados por modelos declarativos.

**Por que encaixa**

- combina fortemente com Pydantic;
- ajuda a endurecer contratos de saída sem inflar o core.

**Riscos**

- uso indiscriminado pode misturar parsing estruturado com a própria semântica de execução.

**Decisão sugerida**

Oferecer como plugin ou adapter opcional.

#### Tecnologia a evitar no centro: `Guardrails`

**Papel adequado**

- camada opcional de policy, validação ou governança.

**Por que evitar no core**

- desloca o projeto para uma fundação mais pesada de AI reliability;
- eleva o custo conceitual do núcleo;
- pode inverter a prioridade do microkernel para um framework de governança.

**Decisão sugerida**

Permitir integração futura, mas evitar como fundação do runtime.

### 5. Persistência e stores

#### Tecnologia recomendada: `SQLAlchemy 2.x + Psycopg 3`

**Papel no framework**

- sustentar stores duráveis e modernos;
- permitir SQLite local e Postgres corporativo;
- separar domínio de infraestrutura de persistência.

**Por que encaixa**

- já existe um passo inicial em SQLAlchemy async;
- amadurece o projeto para cenários reais sem impor ORM ao domínio;
- permite desenho baseado em `StoreProtocol`.

**Onde aplicar**

- `MessageStore`;
- `RunStore`;
- `CheckpointStore`;
- `EventStore`, quando necessário.

**Riscos**

- usar ORM como linguagem do core;
- acoplar queries de infraestrutura à lógica de domínio;
- introduzir abstrações de store cedo demais sem modelo conceitual suficiente.

**Pré-condições arquiteturais**

- definir antes as entidades persistidas;
- definir semântica de append-only, replay e checkpoint;
- explicitar unidades transacionais;
- separar persistência operacional de auditoria.

**Alternativas**

- drivers bare-metal;
- ORMs mais opinionados;
- document stores específicos, se houver caso real.

**Decisão sugerida**

Adotar SQLAlchemy 2.x como toolkit de infra e Psycopg 3 como driver padrão para Postgres.

### 6. Retry e políticas operacionais

#### Tecnologia recomendada: `Tenacity`

**Papel no framework**

- retry lateral para chamadas externas e falhas transitórias.

**Por que encaixa**

- mantém policy fora do domínio;
- compõe bem com adapters;
- reduz repetição de lógica de retry.

**Onde aplicar**

- chamadas HTTP;
- adapters LLM;
- operações transitórias de store.

**Riscos**

- retry mal parametrizado pode mascarar erro estrutural;
- retry no lugar errado pode duplicar efeitos colaterais.

**Decisão sugerida**

Adotar como camada de policy, não como comportamento embutido em `Agent` ou `ChatAdmin`.

### 7. Observabilidade e logging

#### Tecnologia recomendada: `OpenTelemetry`

**Papel no framework**

- modelo padrão de telemetria corporativa;
- traces, métricas e logs exportáveis.

**Por que encaixa**

- resolve observabilidade de forma aberta e vendor-neutral;
- combina com arquitetura lateral;
- prepara o projeto para produção séria.

**Onde aplicar**

- spans de execução;
- métricas por run, pipeline, tool e provider;
- correlation IDs e causalidade entre etapas.

**Riscos**

- observabilidade invasiva demais no domínio;
- sobrecarga desnecessária se instrumentação nascer antes dos eventos do core.

**Pré-condição**

OpenTelemetry deve entrar depois da taxonomia canônica de eventos e do modelo de correlação de execução.

**Decisão sugerida**

Tornar obrigatórios primeiro `ExecutionEvent`, `EventSink` e correlação de execução. Adotar OpenTelemetry como adapter recomendado depois da estabilização desse modelo.

#### Tecnologia recomendada: `structlog`

**Papel no framework**

- logging estruturado com contexto consistente.

**Por que encaixa**

- mantém boa convivência com stdlib logging;
- permite logs corporativos sem abandonar simplicidade operacional.

**Decisão sugerida**

Adotar em conjunto com `logging`, priorizando saída estruturada e contexto por execução.

#### Tecnologia opcional: `Rich`

**Papel no framework**

- melhorar experiência local, CLI e debugging.

**Decisão sugerida**

Usar apenas em contexto de DX local, não como base da observabilidade corporativa.

### 8. Templates e renderização

#### Tecnologia recomendada: `Jinja`

**Papel no framework**

- engine padrão de templates para prompts e renderizações textuais.

**Por que encaixa**

- madura, extensível e bem entendida;
- mantém camada de renderização simples e desacoplada.

**Onde aplicar**

- `PromptTemplate`;
- renderização de mensagens de contexto;
- futuros templates de tools ou system prompts.

**Riscos**

- espalhar Jinja diretamente pelo runtime;
- transformar template engine em parte do domínio.

**Decisão sugerida**

Adotar por trás de um adapter explícito.

### 9. Protocolos de tools e capacidades externas

#### Tecnologia recomendada: `MCP Python SDK`

**Papel no framework**

- integrar tools, resources e prompts externos de forma protocolar.

**Por que encaixa**

- é unix-like no sentido de externalizar capacidades;
- pode ajudar o MiniAutoGen a conversar com um ecossistema crescente de ferramentas interoperáveis;
- evita que toda capability precise virar plugin interno nativo.

**Riscos**

- adoção prematura antes de o core estar estabilizado;
- aumento de superfície operacional;
- distração arquitetural antes da estabilização do vocabulário interno.

**Decisão sugerida**

Manter como integração oficial tardia e opcional, fora do horizonte ativo das primeiras fases de transformação.

### 10. Testes e qualidade

#### Tecnologias recomendadas: `pytest`, `pytest-asyncio`, `Hypothesis`, `coverage.py`

**Papel no framework**

- sustentar confiabilidade e evolução segura;
- testar invariantes do runtime;
- validar state machines e fluxos concorrentes.

**Por que encaixam**

- `pytest` continua sendo a base mais prática;
- `pytest-asyncio` cobre a superfície assíncrona;
- `Hypothesis` é especialmente valioso em pipelines, contratos e estados;
- `coverage.py` mantém mensuração madura para CI.

**Decisão sugerida**

Adotar o conjunto completo como baseline de qualidade.

**Observação de execução**

Parte dessa baseline deve entrar antes das refatorações pesadas, e não apenas no fim do roadmap.

#### Tecnologia recomendada: `unittest.mock`

**Papel no framework**

- mocking padrão, simples e estável.

**Decisão sugerida**

Usar como padrão inicial. Evitar dependências extras de mocking sem necessidade demonstrada.

### 11. Lint, typing, build e workflow

#### Tecnologia recomendada: `Ruff`

**Papel no framework**

- linting, organização e formatação com toolchain reduzida.

**Por que encaixa**

- simplifica o setup;
- acelera feedback;
- reduz multiplicidade de ferramentas.

**Decisão sugerida**

Adotar como base de lint e formatter.

#### Tecnologias de typing: `MyPy` e `ty`

**Papel no framework**

- reforçar contratos estáticos e manter saúde arquitetural.

**Leitura recomendada**

- `MyPy` continua sendo referência madura para typing avançado e deve servir de baseline inicial;
- `ty` é promissor pela velocidade e ergonomia moderna.

**Decisão sugerida**

Adotar `MyPy` no curto prazo. Avaliar `ty` por benchmark interno no médio prazo, com critério explícito de troca baseado em performance, cobertura dos patterns reais do projeto e estabilidade operacional.

#### Tecnologia recomendada: `uv`

**Papel no framework**

- gestão moderna de ambiente, lockfile e workflow.

**Por que encaixa**

- reduz atrito operacional;
- simplifica CI;
- se alinha à toolchain moderna baseada em `pyproject.toml`.

**Decisão sugerida**

Adotar como direção preferencial de workflow e gerenciamento de projeto.

**Observação**

A migração para `uv` não deve bloquear estabilização arquitetural do core. Ela deve entrar quando trouxer ganho operacional líquido.

### 12. Documentação

#### Tecnologia recomendada: `MkDocs Material + mkdocstrings`

**Papel no framework**

- produzir documentação de engenharia navegável e verificável;
- aproximar referência de código e documentação escrita.

**Decisão sugerida**

Adotar quando a documentação do projeto sair do estágio atual de Markdown distribuído para um portal técnico estruturado.

## Parecer final por prioridade

### Núcleo obrigatório

- `Pydantic v2`
- `AnyIO`
- `HTTPX`
- `LiteLLM`
- `SQLAlchemy 2.x + Psycopg 3`
- `Tenacity`
- `structlog`
- `pytest`
- `pytest-asyncio`
- `Hypothesis`
- `coverage.py`
- `Ruff`
- `uv`
- `Jinja`

### Opcional, mas muito promissor

- `Instructor`
- `msgspec`
- `Rich`
- `ty`

### Tardio e opcional

- `OpenTelemetry`
- `MCP Python SDK`

### Evitar no centro da arquitetura

- `Guardrails` como fundação do runtime;
- `HTTPCore` como escolha padrão;
- toolchain redundante de mocking ou HTTP sem necessidade real.
