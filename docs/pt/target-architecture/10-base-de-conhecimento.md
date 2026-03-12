# Base de Conhecimento

## Objetivo

Consolidar os conceitos, técnicas e tecnologias modernas que devem servir de referência para decisões futuras no MiniAutoGen.

Este documento não é um catálogo exaustivo do ecossistema Python. Ele funciona como base de conhecimento curada para este projeto.

## 1. Contratos fortes como fundamento

Em frameworks orientados a execução dinâmica, a ausência de contratos explícitos costuma gerar:

- acoplamento acidental;
- fronteiras ambíguas;
- dificuldade de observabilidade;
- erros tardios;
- baixa capacidade de versionar a API.

Para o MiniAutoGen, a lição prática é simples:

- tipos devem ser parte do desenho;
- modelos devem ser estáveis na superfície pública;
- schemas devem ser produzíveis a partir desses modelos;
- a validação deve acontecer na fronteira.

## 2. Runtime estruturado importa mais do que parece

Projetos assíncronos pequenos costumam começar bem com `asyncio` direto, mas crescem mal quando:

- cada componente define seu próprio timeout;
- cancelamento não é propagado de forma consistente;
- tasks são disparadas sem supervisão;
- shutdown não tem semântica clara.

Técnica recomendada:

- centralizar o runtime;
- usar task groups;
- definir scopes de cancelamento;
- tratar timeout como regra arquitetural, não como detalhe local.

## 3. Adapters finos preservam o core

Um dos riscos clássicos em sistemas com integrações é o domínio passar a falar a língua do fornecedor.

Isso aparece quando:

- o core conhece payloads específicos de um vendor;
- exceptions externas vazam para toda a aplicação;
- argumentos de provider passam a ser o contrato da biblioteca.

Técnica recomendada:

- introduzir protocolos internos;
- adaptar fornecedores na borda;
- normalizar entrada e saída antes de tocar o domínio.

## 4. Observabilidade deve nascer de eventos, não de prints

Logs simples ajudam no início, mas não escalam para validação operacional e debug em ambiente corporativo.

Boa prática para o MiniAutoGen:

- emitir eventos de domínio;
- associar contexto de execução a cada evento;
- mapear esses eventos para tracing, métricas e logs estruturados;
- manter correlação entre pipeline, component, tool e provider.

## 5. Persistência não é detalhe tardio

Quando persistência é tratada cedo como protocolo, o sistema ganha:

- maior testabilidade;
- melhor separação de responsabilidades;
- evolução mais limpa para SQLite e Postgres;
- possibilidade futura de auditoria, replay e checkpointing.

Quando persistência é tratada tardiamente, ela tende a contaminar o domínio com detalhes de infra.

## 6. Retry deve ser policy, não reflexo

Retry automático em todo lugar é uma forma de acoplamento operacional oculto.

Boas práticas:

- retry só em operações idempotentes ou tratadas;
- policy explícita por adapter;
- taxonomia clara de erros transitórios e permanentes;
- nenhuma entidade central deve decidir retry por conta própria.

## 7. Toolchain enxuta aumenta qualidade

Uma stack moderna não precisa de vinte ferramentas com sobreposição funcional.

Para este projeto, a direção recomendada é:

- `Ruff` para lint e formatter;
- `uv` para ambiente e lock;
- `pytest` para testes;
- `Hypothesis` para propriedades;
- `coverage.py` para visibilidade de cobertura.

O ganho aqui não é apenas velocidade. É redução de custo cognitivo.

## 8. Structured outputs devem ser capacidade opcional

Saídas estruturadas são valiosas, mas não devem definir a semântica inteira do runtime.

Técnica recomendada:

- manter outputs estruturados atrás de contrato ou plugin;
- usar Pydantic como linguagem dos schemas;
- encaixar parsing estruturado na borda de adapters, não no coração do kernel.

## 9. Protocolos abertos aumentam longevidade

Adoção de protocolos como MCP deve ser vista como forma de:

- externalizar capacidades;
- reduzir necessidade de plugins acoplados ao código;
- facilitar interoperabilidade.

Mas há uma regra importante:

protocolos abertos ajudam mais depois que o núcleo já está estável.

## 10. Arquitetura moderna não é sinônimo de maximalismo

Uma armadilha frequente em projetos de IA é adotar:

- framework de agents;
- framework de reliability;
- framework de observabilidade;
- framework de workflows;
- framework de tools;

Tudo ao mesmo tempo.

Isso quase sempre gera:

- stack inchada;
- contratos confusos;
- runtime imprevisível;
- dificuldade de manutenção.

Para o MiniAutoGen, arquitetura moderna significa:

- poucas peças;
- boas peças;
- interfaces claras;
- crescimento controlado.

## Base recomendada de referência contínua

### Fundamentos

- contracts-first
- microkernel
- adapters finos
- runtime estruturado
- observabilidade lateral
- persistência por protocolos
- adoção incremental

### Stack de referência

- `Pydantic v2`
- `AnyIO`
- `HTTPX`
- `LiteLLM`
- `SQLAlchemy 2.x`
- `Psycopg 3`
- `Tenacity`
- `structlog`
- `Jinja`
- `pytest`
- `pytest-asyncio`
- `Hypothesis`
- `coverage.py`
- `Ruff`
- `uv`
- `MyPy`

### Stack tardia ou opcional

- `OpenTelemetry`
- `Instructor`
- `msgspec`
- `MCP Python SDK`
- `Rich`
- `ty`

## Regras de decisão para o futuro

Sempre que o time avaliar nova tecnologia, deve perguntar:

1. ela resolve uma responsabilidade única e clara?
2. ela reduz ou aumenta a complexidade total?
3. ela fortalece contratos ou introduz informalidade?
4. ela preserva o core como núcleo vendor-neutral?
5. ela melhora operação, qualidade ou extensibilidade real?
6. ela pode entrar como adapter, e não como semântica do domínio?

Se a resposta a essas perguntas não for forte, a dependência provavelmente não deve entrar.
