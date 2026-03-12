# Arquitetura de Agentes no MiniAutoGen

Para a visão arquitetural completa, consulte [C4 Nível 3: Componentes internos](../architecture/03-componentes.md).

## Visão geral

No MiniAutoGen, um agente é uma unidade leve de execução que combina:

- identidade (`agent_id`);
- nome (`name`);
- papel (`role`);
- um pipeline opcional para geração de resposta.

## Estrutura atual

O comportamento do agente é implementado principalmente pela classe `Agent`, em `miniautogen/agent/agent.py`.

Responsabilidades principais:

- representar o participante da conversa;
- manter a configuração mínima do agente;
- delegar a geração de resposta ao pipeline associado;
- expor um construtor utilitário por JSON.

## Relação com a arquitetura geral

- `Chat` mantém os agentes registrados na conversa;
- `ChatAdmin` coordena quando um agente deve responder;
- o pipeline do agente produz a saída textual;
- essa saída é persistida no histórico pelo fluxo administrativo.

## Papel do pipeline do agente

No estado atual, o agente não implementa internamente lógica sofisticada de memória, planejamento ou ferramentas. Essas capacidades, quando desejadas, devem ser compostas no pipeline do agente por meio de componentes.
