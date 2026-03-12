# Mapa Físico de Módulos

## Objetivo

Traduzir a arquitetura alvo para um recorte físico de código, reduzindo interpretações divergentes entre times de engenharia.

## Princípio

Camadas conceituais precisam de um mapeamento físico suficientemente claro para orientar refatoração, ownership e revisão de código.

## Estrutura alvo sugerida

```text
miniautogen/
  core/
    contracts/
    runtime/
    pipeline/
    events/
  adapters/
    llm/
    http/
    templates/
    tools/
  stores/
    memory/
    sqlite/
    postgres/
  policies/
  observability/
  compat/
  app/
```

## Papel por pacote

### `core/contracts/`

- modelos públicos;
- envelopes de execução;
- protocolos estáveis.

### `core/runtime/`

- `PipelineRunner`;
- lifecycle de run;
- timeout, cancelamento e execução estruturada.

### `core/pipeline/`

- `Component`;
- `Pipeline`;
- composição declarativa;
- helpers de execução internos ao kernel.

### `core/events/`

- `ExecutionEvent`;
- correlação;
- taxonomia de eventos e erros.

### `adapters/llm/`

- integração com LiteLLM;
- adapters por provider quando necessário;
- normalização de entrada e saída.

### `adapters/http/`

- clients e helpers HTTP;
- timeout e retry nas bordas.

### `adapters/templates/`

- `TemplateRenderer`;
- adapter Jinja;
- sandboxing futuro, se necessário.

### `adapters/tools/`

- contracts e adapters de tool;
- integração protocolar tardia, como MCP, quando fizer sentido.

### `stores/`

- stores concretos por backend;
- separação entre memória, SQLite e Postgres.

### `policies/`

- execution, retry, validation, budget e permission policies;
- nunca como segundo runtime implícito.

### `observability/`

- sinks de evento;
- logging estruturado;
- exporters e mapeamentos para OTel.

### `compat/`

- facades legadas;
- adapters de compatibilidade;
- shims temporários de migração.

### `app/`

- pontos de entrada de alto nível;
- facades públicas preservadas para ergonomia.

## Observações de migração

- a estrutura física não precisa nascer toda de uma vez;
- `compat/` existe para tornar a transição explícita, não para perpetuar legado;
- pacotes só devem ser criados quando houver responsabilidade real, não por antecipação vazia.
