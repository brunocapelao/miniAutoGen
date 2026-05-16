# Specs em backlog

Specs movidas para cá ficam **pausadas**: não bloqueiam o roadmap ativo nem são pré-requisito de nada em andamento. Permanecem aqui como referência arquitetural pronta caso a demanda apareça.

| Spec | Motivo da pausa | Quando revisitar |
|---|---|---|
| `mcp-server.md` / `plan-mcp-server.md` / `tasks-mcp-server.md` (014) | Direção "mcp-out": expor o workspace MiniAutoGen como servidor MCP para **clientes externos** (Claude Code, Cursor, mcp inspector). Não é pré-requisito para o objetivo atual de transformar o sistema em CLI com agente orquestrador interno (specs 015/016/017 — Team Runtime estilo Claude Code Agent Teams), que é **peer-to-peer interno** e não usa MCP. | Quando houver demanda real de cliente MCP externo consumindo o workspace, ou quando a trilogia 015/016/017 estiver estabilizada e fizer sentido expor o orquestrador também via MCP. |

## Como reativar

1. Mover os 3 arquivos de volta para `.specs/` (raiz ou em diretório numerado).
2. Revisar o conteúdo contra o estado atual do código — a spec foi escrita em 2026-05-16 e pode estar defasada.
3. Atualizar o cabeçalho `Status` de `Rascunho` para `Ativo`.
