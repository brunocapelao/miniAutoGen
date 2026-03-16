# Arquitetura Alvo

## Objetivo

Descrever a forma desejada do MiniAutoGen após a evolução arquitetural recomendada, preservando sua filosofia minimalista e aumentando sua maturidade para uso corporativo.

## Síntese

O MiniAutoGen deve evoluir para uma biblioteca orientada a microkernel, em que:

- o núcleo controla contratos e execução;
- bordas resolvem provedores, transporte e persistência;
- observabilidade e políticas operacionais entram lateralmente;
- capacidades avançadas são plugins ou adapters opcionais.

## Kernel mínimo obrigatório

O termo microkernel só é útil se houver uma fronteira concreta. Para o MiniAutoGen, o kernel mínimo obrigatório deve ser entendido como o menor conjunto de elementos sem os quais o framework deixa de ser ele mesmo.

### Entra no kernel mínimo

- `Message`: unidade de troca conversacional;
- `RunContext`: contexto de execução de um run;
- `Component`: unidade mínima de processamento;
- `Pipeline`: composição ordenada de componentes;
- `PipelineRunner`: executor disciplinado do pipeline;
- `ExecutionEvent`: evento canônico do domínio de execução.

### Pode fazer parte do core, mas não do kernel mínimo

- `AgentSpec`;
- `RunResult`;
- `ToolInvocation`;
- `ToolResult`;
- contratos de stores;
- contratos de providers.

### É adapter, plugin ou borda por definição

- providers de LLM concretos;
- clients HTTP;
- engines de template;
- stores concretos;
- exporters de observabilidade;
- policies específicas;
- integrações MCP;
- frameworks de structured output.

## Leitura do kernel mínimo

Essa delimitação tem dois objetivos:

- impedir que o termo microkernel vire slogan vago;
- proteger o núcleo contra acoplamento com capacidades laterais antes da hora.

## Metamodelo arquitetural

### 1. Core de contratos

Responsável por:

- modelos públicos;
- envelopes de execução;
- tipos de eventos;
- contratos de ferramenta;
- resultados de run.

Componentes alvo:

- `Message`
- `AgentSpec`
- `RunContext`
- `RunResult`
- `ExecutionEvent`
- `ToolInvocation`
- `ToolResult`

### 2. Microkernel de execução

Responsável por:

- ciclo de vida de runs;
- execução de pipelines;
- gestão de estado de execução;
- timeouts e cancelamento;
- propagação de contexto operacional.

Características desejadas:

- runtime AnyIO;
- cancelamento estruturado;
- execução previsível;
- isolamento de responsabilidades entre run, component e adapter.

### Regra de adoção do runtime

AnyIO deve entrar primeiro como capacidade interna do `PipelineRunner`. A API pública não deve ser redesenhada em torno do runtime antes que a compatibilidade transitória esteja definida.

### 3. Kernel de composição

Responsável por:

- registrar componentes;
- compor pipelines;
- coordenar hooks e policies;
- permitir extensão sem modificar o core.

Capacidades desejadas:

- pipeline declarativo;
- contratos claros entre etapas;
- hooks de observabilidade e retry fora do domínio;
- superfície pequena para plugins.

### 4. Camada de adapters

Responsável por:

- adapters de LLM;
- adapters HTTP;
- adapters de template;
- adapters de tool;
- adapters de parsing estruturado;
- integrações tardias de protocolo, quando fizer sentido.

Princípio:

nenhum adapter deve se tornar a linguagem interna do domínio.

### 5. Camada de stores

Responsável por:

- store de mensagens;
- store de runs;
- store de checkpoints;
- store de eventos persistidos, quando aplicável.

Princípio:

o domínio fala com protocolos de store; a infraestrutura implementa os detalhes.

### Pré-condição de modelagem

A camada de stores só deve ser aprofundada depois que o projeto tiver:

- modelo canônico de persistência;
- semântica de checkpoint;
- definição de replay;
- unidade transacional por tipo de dado persistido.

### 6. Camada de policy

Responsável por:

- retry;
- circuit-breaking futuro, se necessário;
- limites operacionais;
- budgets e quotas, se forem adicionados;
- validações laterais.

Princípio:

policies não pertencem às entidades centrais.

### Delimitação da policy layer

Para evitar uma `policy blob`, a camada de policy deve ser fracionada conceitualmente em tipos de policy:

- `ExecutionPolicy`: timeout, cancelamento e limites de execução;
- `RetryPolicy`: regras de repetição para falhas transitórias;
- `ValidationPolicy`: validações laterais e gates de saída;
- `BudgetPolicy`: custos, quotas e limites de uso;
- `PermissionPolicy`: autorização e restrições de capability, se existirem.

### O que uma policy pode fazer

- observar contexto e eventos;
- enriquecer decisão operacional;
- decidir retry, skip, block ou fail em pontos permitidos;
- produzir eventos de policy aplicada.

### O que uma policy não pode fazer

- reescrever semântica do domínio;
- falar diretamente a linguagem de um vendor no core;
- se tornar o segundo runtime informal do sistema;
- acumular comportamentos desconexos apenas porque são transversais.

### 7. Camada de observabilidade

Responsável por:

- logs estruturados;
- traces;
- métricas;
- correlação de execução.

Princípio:

eventos do domínio primeiro, exporters depois.

## Diagrama da arquitetura alvo

```mermaid
flowchart TB
    App["Aplicação hospedeira"] --> API["API pública do MiniAutoGen"]
    API --> Contracts["Core de contratos"]
    API --> Kernel["Microkernel de execução"]
    API --> Compose["Kernel de composição"]

    Kernel --> Runtime["Runtime AnyIO"]
    Kernel --> Policy["Policies operacionais"]
    Kernel --> Events["Eventos de domínio"]

    Compose --> Adapters["Camada de adapters"]
    Compose --> Stores["Camada de stores"]

    Adapters --> LLM["Adapters de LLM"]
    Adapters --> HTTP["Adapters HTTP"]

## Modo agentic como capability

O diálogo livre entre agentes não deve voltar como centro do sistema. Ele deve existir como capability encapsulada do runtime:

- `DynamicChatPipeline`: pipeline especializado em interação dinâmica;
- `AgenticLoopComponent`: componente de loop injetável;
- `RouterDecision`: passagem de bastão tipada;
- `ConversationPolicy`: camada de contenção.

Esse desenho preserva a arquitetura nova e reintroduz experimentação conversacional de forma auditável.
    Adapters --> Template["Adapters de template"]
    Adapters --> Tools["Adapters de tools"]

    Events --> Obs["Observabilidade\nOpenTelemetry + structlog"]
    Stores --> DB["SQLite / Postgres"]
```

## Superfícies arquiteturais recomendadas

### Contratos

Interfaces ou modelos que devem se tornar estáveis:

- `LLMProviderProtocol`
- `StoreProtocol`
- `ToolProtocol`
- `TemplateRenderer`
- `ExecutionPolicy`
- `EventSink`

### Entidades centrais

Objetos que o core deve entender sem conhecer integrações específicas:

- agente;
- run;
- message;
- pipeline;
- component;
- tool invocation;
- execution event.

### Eventos do domínio

Exemplos de eventos que o core deve emitir:

- `run_started`
- `run_finished`
- `run_cancelled`
- `run_timed_out`
- `component_started`
- `component_finished`
- `component_skipped`
- `component_retried`
- `tool_invoked`
- `tool_succeeded`
- `tool_failed`
- `checkpoint_saved`
- `checkpoint_restored`
- `llm_request_started`
- `llm_request_finished`
- `adapter_failed`
- `validation_failed`
- `policy_applied`
- `budget_exceeded`

### Taxonomia canônica de erros

Além da taxonomia de eventos, o framework deve reconhecer classes semânticas de falha:

- `transient`: falhas potencialmente recuperáveis por retry;
- `permanent`: falhas que não devem ser repetidas;
- `validation`: falha em contrato, schema ou regra semântica;
- `timeout`: tempo excedido;
- `cancellation`: execução interrompida por cancelamento;
- `adapter`: falha de integração externa;
- `configuration`: configuração ausente, inválida ou inconsistente;
- `state_consistency`: estado impossível, corrompido ou fora de invariantes.

## Diferença entre arquitetura atual e alvo

### Estado atual

- `Chat`, `Agent` e `ChatAdmin` concentram boa parte da semântica operacional;
- a disciplina de runtime ainda é simples;
- a persistência é inicial;
- observabilidade é básica;
- contratos são úteis, mas ainda limitados em abrangência;
- a extensão por pipeline já existe e é o principal ativo arquitetural do projeto.

### Estado alvo

- o runtime passa a ser uma capacidade central estruturada;
- contratos públicos cobrem execução, tools, eventos e resultados;
- providers e stores entram por interfaces mais definidas;
- observabilidade deixa de ser incidental e passa a ser arquitetura lateral;
- o projeto continua pequeno, mas muito mais explícito, versionável e previsível.

## Decisões de desenho

### Decisão 1: preservar a composição por pipeline

Essa é a principal virtude do projeto atual e deve ser mantida.

### Decisão 2: endurecer contratos antes de expandir features

Não faz sentido ampliar o número de capacidades sem estabilizar o vocabulário do sistema.

### Decisão 3: centralizar o runtime

Sem isso, timeout, cancelamento e controle concorrente continuarão distribuídos.

### Decisão 4: formalizar bordas

LLMs, tools, templates e stores precisam de protocolos claros.

### Decisão 5: tornar observabilidade uma capacidade arquitetural

Mas sempre fora do domínio central.

### Decisão 6: versionar compatibilidade pública explicitamente

Uma biblioteca corporativa precisa definir o que é estável, o que é experimental e o que constitui breaking change.

## Compatibilidade e versionamento

O desenho alvo pressupõe:

- política de versionamento semântico;
- marcação explícita de APIs experimentais;
- janela de depreciação para APIs públicas;
- versionamento de schemas persistidos;
- versionamento da taxonomia de eventos quando exposta externamente.

## Resultado esperado

Ao final da evolução, o MiniAutoGen deve ser:

- pequeno na superfície;
- forte em contratos;
- previsível em runtime;
- extensível por adapters;
- rastreável operacionalmente;
- adequado para times de engenharia validarem, integrarem e operarem em ambientes corporativos.
