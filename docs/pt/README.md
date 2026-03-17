# MiniAutoGen

## Sumário executivo

MiniAutoGen é um framework Python de orquestração de pipelines e agentes assíncronos, projetado para aplicações de IA em ambiente corporativo. Diferente de frameworks que delegam o controle de fluxo inteiramente ao LLM -- criando caixas-pretas imprevisíveis --, o MiniAutoGen adota uma Arquitetura Microkernel onde a lógica de negócio, a integração com ferramentas externas e as regras operacionais (falhas, orçamentos, timeouts) são rigorosamente separadas.

O sistema oferece três modos de coordenação nativos: WorkflowRuntime para execução sequencial e fan-out, DeliberationRuntime para ciclos de contribuição, revisão por pares e consolidação, e AgenticLoopRuntime para turnos conversacionais dirigidos por roteador. Esses modos são composíveis via CompositeRuntime, que encadeia múltiplos modos em sequência dentro de uma única execução.

A arquitetura event-driven do MiniAutoGen emite 42 tipos de evento distribuídos em 10 categorias, garantindo observabilidade completa do ciclo de vida de execução. Oito políticas transversais (budget, approval, retry, timeout, validation, permission, execution, policy chain) operam lateralmente ao kernel, reagindo a eventos sem acoplar-se à lógica central. O resultado é um sistema determinista, tolerante a falhas e auditável em produção.

---

## Como funciona

A aplicação hospedeira define agentes com identidades e capacidades tipadas (AgentSpec). Cada agente é equipado com um plano de coordenação (WorkflowPlan, DeliberationPlan ou AgenticLoopPlan) que determina o modo exato de raciocínio. O Microkernel, através do PipelineRunner, executa o plano de coordenação utilizando concorrência estruturada via AnyIO, compartilhando estado mutável tipado (RunContext) entre os componentes e aplicando cancelamento estruturado, controle de custo e limites de tempo. Integrações externas -- provedores de LLM, ferramentas, backend drivers -- são isoladas nas bordas do sistema através de protocolos tipados, sem acesso direto ao domínio interno.

---

## Navegação da documentação

- [Arquitetura](architecture/README.md) -- visão geral das camadas, módulos e diagramas do sistema
- [Referência rápida dos módulos](quick-reference.md) -- índice compacto de todos os pacotes e suas responsabilidades
- [Guia do Gemini CLI Gateway](guides/gemini-cli-gateway.md) -- configuração e uso do backend driver para Gemini CLI

---

## Leitura recomendada

Para compreensão completa da arquitetura, recomenda-se a leitura na seguinte ordem:

1. [Contexto do sistema](architecture/01-contexto.md) -- posicionamento do MiniAutoGen e suas fronteiras externas
2. [Camadas e containers](architecture/02-containers.md) -- decomposição lógica em camadas e agrupamentos executáveis
3. [Componentes internos](architecture/03-componentes.md) -- detalhamento dos módulos, contratos e protocolos
4. [Fluxos de execução](architecture/04-fluxos.md) -- sequências de execução dos modos de coordenação
5. [Invariantes e taxonomias](architecture/05-invariantes.md) -- regras invioláveis e classificação canônica de erros
6. [Decisões arquiteturais](architecture/06-decisoes.md) -- registro das decisões técnicas e suas justificativas

---

## API pública

O módulo `miniautogen/api.py` exporta 54 tipos e constitui o ponto de entrada único para consumidores da biblioteca. Toda integração deve importar exclusivamente a partir deste módulo.

```python
from miniautogen.api import WorkflowRuntime, DeliberationRuntime, AgenticLoopRuntime
```
