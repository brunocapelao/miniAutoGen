# Web Console — Guia do Utilizador

O Web Console e a interface grafica do MiniAutoGen para gestao de workspaces, agentes, flows e runs via browser.

---

## Iniciar o Console

```bash
# Modo producao (build estatico)
miniautogen console --port 8080

# Modo desenvolvimento (hot reload)
miniautogen console --dev

# Com workspace especifico
miniautogen console --workspace /path/to/project
```

---

## Paginas

### Dashboard (/)

- Resumo do workspace: contagem de agentes, flows, runs
- Trigger de runs via seletor de flow

### Agents (/agents)

- Tabela com todos os agentes configurados
- Botao "New Agent" para criar
- Links Edit/Delete por agente
- Pagina de detalhe (`/agents/detail?name=X`)

### Flows (/flows)

- Cards com flows configurados (modo, participantes)
- Botao "New Flow" para criar
- Links Edit/Delete por flow
- Pagina de detalhe (`/flows/detail?name=X`)

### Runs (/runs)

- Tabela paginada de execucoes
- Status badges (running, completed, failed)
- Auto-refresh a cada 3 segundos
- Detalhe com FlowCanvas + EventFeed + ApprovalList

### Logs (/logs)

- Stream de eventos em tempo real via WebSocket
- Filtro por tipo de evento
- Auto-scroll (toggle on/off)
- Botoes Clear e Export JSON
- Indicador de conexao (verde/vermelho)

### Settings (/settings)

- Tabelas de engines com CRUD
- Resumo da configuracao do workspace
- Gestao de engine profiles (provider, model, kind, temperatura)

---

## API Endpoints

### Leitura

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/v1/workspace` | Config resumida |
| GET | `/api/v1/agents` | Listar agentes |
| GET | `/api/v1/flows` | Listar flows |
| GET | `/api/v1/engines` | Listar engines |
| GET | `/api/v1/config/detail` | Config detalhada |
| GET | `/api/v1/runs` | Listar runs (paginado) |
| GET | `/api/v1/events` | Eventos recentes |

### Escrita

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST | `/api/v1/agents/{name}` | Criar agente |
| PUT | `/api/v1/agents/{name}` | Atualizar agente |
| DELETE | `/api/v1/agents/{name}` | Eliminar agente |
| POST | `/api/v1/flows/{name}` | Criar flow |
| PUT | `/api/v1/flows/{name}` | Atualizar flow |
| DELETE | `/api/v1/flows/{name}` | Eliminar flow |
| POST | `/api/v1/engines/{name}` | Criar engine |
| PUT | `/api/v1/engines/{name}` | Atualizar engine |
| DELETE | `/api/v1/engines/{name}` | Eliminar engine |
| POST | `/api/v1/runs` | Trigger run |

### WebSocket

| Endpoint | Descricao |
|----------|-----------|
| `WS /ws/runs/{run_id}` | Eventos por run |
| `WS /ws/events` | Stream global de eventos |

---

## Autenticacao

```bash
# Opcional: definir API key
export MINIAUTOGEN_API_KEY=my-secret-key
miniautogen console
```

Quando configurada, todas as requisicoes exigem o header `X-API-Key`.

---

## Rate Limiting

60 requisicoes por minuto por IP (via slowapi).

---

## Troubleshooting

### Console nao abre

Verifique se o build estatico existe:

```bash
ls console/out/
```

Se nao existir, execute o build:

```bash
cd console && npm ci && npm run build
```

### WebSocket nao conecta

Verifique se o servidor esta a correr:

```bash
miniautogen server status
```

### Erro de autenticacao

Se definiu `MINIAUTOGEN_API_KEY`, todas as requisicoes precisam do header `X-API-Key`. Remova a variavel para desativar autenticacao.
