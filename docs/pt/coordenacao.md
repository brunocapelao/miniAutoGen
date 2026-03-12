# Coordenação no MiniAutoGen

Para a visão arquitetural completa e atualizada, consulte:

- [C4 Nível 2: Containers lógicos](architecture/02-containers.md)
- [C4 Nível 3: Componentes internos](architecture/03-componentes.md)
- [Fluxos de execução](architecture/04-fluxos.md)

## Visão geral

No estado atual do MiniAutoGen, a coordenação entre agentes é feita por um ciclo assíncrono centrado em `ChatAdmin`, `Chat` e pipelines.

## Elementos envolvidos

### `Agent`

Representa um participante da conversa. Cada agente pode ter um pipeline próprio para gerar respostas.

### `Chat`

Mantém os agentes registrados, expõe acesso ao histórico e delega persistência de mensagens a um `ChatRepository`.

### `ChatAdmin`

Coordena as rodadas de execução e aciona o pipeline administrativo, que normalmente:

1. seleciona o próximo agente;
2. solicita a resposta do agente;
3. verifica a condição de encerramento.

## Modelo atual de coordenação

- o histórico da conversa é a principal base de decisão;
- a seleção de agente padrão é uma rotação simples;
- o estado compartilhado da rodada circula em `ChatPipelineState`;
- a conversa pode ser encerrada por `TERMINATE` ou por `max_rounds`.
