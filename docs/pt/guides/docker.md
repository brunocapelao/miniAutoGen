# Docker — Guia de Deployment

O MiniAutoGen suporta deployment via Docker com build multi-stage.

---

## Quick Start

```bash
docker compose up -d
```

---

## Dockerfile

Build multi-stage:

1. **Stage 1 (Node.js):** Build do frontend Next.js
2. **Stage 2 (Python):** Runtime com miniautogen instalado

---

## docker-compose.yml

```yaml
services:
  miniautogen:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./workspace:/workspace
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
    working_dir: /workspace
```

---

## Variaveis de Ambiente

| Variavel | Descricao |
|----------|-----------|
| `OPENAI_API_KEY` | Chave OpenAI |
| `ANTHROPIC_API_KEY` | Chave Anthropic |
| `GOOGLE_API_KEY` | Chave Google Gemini |
| `MINIAUTOGEN_API_KEY` | Autenticacao da API (opcional) |

---

## Comandos

```bash
# Build
docker compose build

# Start
docker compose up -d

# Logs
docker compose logs -f

# Stop
docker compose down
```

---

## Uso directo com Docker run

```bash
docker run -v $(pwd):/workspace \
  -e OPENAI_API_KEY=sk-... \
  -p 8080:8080 \
  miniautogen/miniautogen console --host 0.0.0.0
```

---

## Volumes

| Volume | Descricao |
|--------|-----------|
| `/workspace` | Workspace do projecto (montado do host) |

O volume `/workspace` deve conter o `miniautogen.yaml` e os ficheiros do projecto. Todas as operacoes do MiniAutoGen (agentes, flows, memoria) operam dentro deste directorio.

---

## Portas

| Porta | Servico |
|-------|---------|
| `8080` | Servidor REST + Web Console |

---

## Troubleshooting

### Build falha no stage Node.js

Verifique que o directorio `console/` existe e contem `package.json`:

```bash
ls console/package.json
```

### Container nao arranca

Verifique os logs:

```bash
docker compose logs miniautogen
```

### API keys nao detectadas

As variaveis de ambiente devem ser passadas no `docker-compose.yml` ou via ficheiro `.env` na raiz do projecto:

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```
