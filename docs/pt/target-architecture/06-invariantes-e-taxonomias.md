# Invariantes e Taxonomias

## Objetivo

Definir a base normativa de invariantes e taxonomias do framework antes da expansão das classes e integrações.

Sem isso, modelos novos tendem a virar apenas novos nomes para semânticas ainda ambíguas.

## 1. Invariantes canônicos por objeto

### `Message`

Invariantes mínimos:

- deve possuir identificador lógico ou posição determinável no histórico;
- deve possuir origem explícita;
- deve possuir conteúdo ou payload semanticamente válido;
- não deve depender da estrutura interna de um vendor de LLM;
- deve ser serializável de forma estável.

### `RunContext`

Invariantes mínimos:

- identifica unicamente um run em andamento;
- carrega contexto operacional e não apenas payload livre;
- deve ser suficiente para correlação de eventos;
- não deve depender de adapter específico;
- seu ciclo de vida deve ser delimitado do início ao término do run.

Mini-spec inicial:

- campos obrigatórios recomendados:
  - `run_id`
  - `started_at`
  - `correlation_id`
  - `execution_state`
  - `input_payload` ou referência equivalente
- campos operacionais recomendados:
  - timeout efetivo
  - tenant ou namespace quando aplicável
  - metadados de policy aplicável
- não deve carregar payload arbitrário ilimitado como substituto de contrato;
- deve ter mutabilidade controlada e observável;
- deve coexistir temporariamente com `ChatPipelineState` por adaptação explícita, não por fusão informal.

### `RunResult`

Invariantes mínimos:

- deve representar estado terminal ou parcialmente terminalizado com motivo explícito;
- deve distinguir sucesso, falha, cancelamento e timeout;
- deve referenciar o run correspondente;
- não deve esconder falhas em texto não estruturado.

### `ExecutionEvent`

Invariantes mínimos:

- deve ter tipo canônico;
- deve ter timestamp e correlação;
- deve apontar o escopo relevante do evento;
- não deve ser um saco genérico de payloads sem taxonomia;
- deve ser serializável e versionável.

### `ToolInvocation`

Invariantes mínimos:

- deve identificar a ferramenta alvo;
- deve ter argumentos validados;
- deve poder ser correlacionado com resultado, erro ou timeout;
- deve ser independente do protocolo concreto de transporte.

### `Checkpoint`

Invariantes mínimos:

- deve pertencer a um run;
- deve ter versão de schema;
- deve ser restaurável ou explicitamente marcado como não restaurável;
- deve ser completo no nível prometido pela arquitetura.

## 2. Taxonomia canônica de erros

### `TransientError`

Falha potencialmente recuperável, elegível a retry sob policy explícita.

### `PermanentError`

Falha que não melhora com repetição e deve encerrar a etapa.

### `ValidationError`

Falha em contrato, schema, regra semântica ou conteúdo estruturado.

### `TimeoutError`

Falha causada por tempo excedido em escopo conhecido.

### `CancellationError`

Interrupção causada por cancelamento deliberado do run ou subescopo.

### `AdapterError`

Falha ocorrida na borda de integração externa.

### `ConfigurationError`

Falha de configuração ausente, inválida ou inconsistente.

### `StateConsistencyError`

Falha que indica violação de invariantes ou estado impossível.

## Regra de uso

Essas categorias devem orientar:

- retry policy;
- logging;
- telemetria;
- retorno estruturado;
- compatibilidade pública de erros.

## 3. Taxonomia canônica de eventos

### Eventos de run

- `run_started`
- `run_finished`
- `run_cancelled`
- `run_timed_out`

### Eventos de component

- `component_started`
- `component_finished`
- `component_skipped`
- `component_retried`

### Eventos de tool

- `tool_invoked`
- `tool_succeeded`
- `tool_failed`

### Eventos de adapter

- `adapter_called`
- `adapter_failed`

### Eventos de checkpoint

- `checkpoint_saved`
- `checkpoint_restored`

### Eventos de validação e policy

- `validation_failed`
- `policy_applied`
- `budget_exceeded`

## 4. Entidade, envelope e DTO

Para conter crescimento caótico de modelos, o time deve diferenciar:

### Entidade

Objeto com identidade e semântica de domínio persistente.

Exemplos:

- `Message`
- `Run`

### Envelope

Objeto que transporta contexto ou resultado entre partes do runtime.

Exemplos:

- `RunContext`
- `RunResult`
- `ExecutionEvent`

### DTO de borda

Objeto voltado a integração externa, serialização ou adapter.

Exemplos:

- payload de provider;
- request de tool;
- resposta HTTP adaptada.

## 5. Mutabilidade recomendada

- entidades persistidas devem favorecer imutabilidade lógica;
- envelopes de runtime podem ter mutabilidade controlada;
- DTOs de borda podem ser transformacionais, mas não devem vazar para o core.

## 6. Compatibilidade pública

Para qualquer modelo exposto publicamente, o time deve definir:

- se é estável, experimental ou interno;
- o que constitui breaking change;
- política de depreciação;
- estratégia de versionamento de schema quando persistido.
