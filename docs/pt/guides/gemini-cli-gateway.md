# Gemini CLI Gateway

Este guia descreve a forma suportada de usar o Gemini CLI com o MiniAutoGen sem acoplar o framework a subprocessos.

## Visão geral

A integração usa duas peças:

- `gemini_cli_gateway/`: serviço local compatível com `POST /v1/chat/completions`
- `OpenAICompatibleProvider`: adapter HTTP do MiniAutoGen para consumir esse gateway

## Pré-requisitos

- binário `gemini` instalado e autenticado
- Python com dependências do projeto instaladas
- variáveis de ambiente do MiniAutoGen configuradas

## Variáveis do gateway

- `GEMINI_GATEWAY_BINARY`: binário a executar. Default: `gemini`
- `GEMINI_GATEWAY_TIMEOUT_SECONDS`: timeout do comando. Default: `60`
- `GEMINI_GATEWAY_MAX_CONCURRENT_PROCESSES`: limite local de concorrência. Default: `2`

## Variáveis do MiniAutoGen

- `MINIAUTOGEN_DEFAULT_PROVIDER=gemini-cli-gateway`
- `MINIAUTOGEN_DEFAULT_MODEL=gemini-2.5-pro`
- `MINIAUTOGEN_GATEWAY_BASE_URL=http://127.0.0.1:8000`
- `MINIAUTOGEN_GATEWAY_API_KEY=` opcional

## Como subir o gateway

Exemplo local com Uvicorn:

```bash
uvicorn gemini_cli_gateway.app:app --host 127.0.0.1 --port 8000
```

## Como apontar o MiniAutoGen para o gateway

```bash
export MINIAUTOGEN_DEFAULT_PROVIDER=gemini-cli-gateway
export MINIAUTOGEN_DEFAULT_MODEL=gemini-2.5-pro
export MINIAUTOGEN_GATEWAY_BASE_URL=http://127.0.0.1:8000
```

## Notas operacionais

- o gateway envia prompts por `stdin`, não por `-p`
- o executor CLI é tratado como solução transitória; a borda HTTP permite troca futura por SDK/API nativa
- o limite de concorrência deve permanecer baixo no início para evitar saturação da máquina host
- o runner do gateway já suporta retry/backoff local para falhas transitórias do CLI

## Notebooks e demos longas

Workflows deliberativos e notebooks com múltiplas rodadas tendem a ser mais sensíveis à instabilidade do CLI do que exemplos curtos.

Prática recomendada:
- manter Gemini CLI como motor real;
- ativar cache de respostas por etapa para reexecução;
- tratar a primeira execução como `cold run`;
- tratar reexecuções como `warm run`.

Na prática:
- `cold run`: consulta o Gemini CLI e grava respostas reutilizáveis;
- `warm run`: reaproveita respostas válidas já persistidas no cache e reduz custo/instabilidade operacional.

Esse cache não muda o contrato do framework. Ele existe apenas para estabilizar demos, notebooks e ciclos repetidos de pesquisa.

## Integração via AgentAPIDriver (Recomendado)

A forma preferencial de usar o Gemini CLI no MiniAutoGen é via `AgentAPIDriver`:

```python
from gemini_cli_gateway.app import app as gateway_app
import httpx
from miniautogen.backends.agentapi import AgentAPIClient, AgentAPIDriver
from miniautogen.backends.models import SendTurnRequest, StartSessionRequest

client = AgentAPIClient(
    base_url="http://gemini-gateway",
    transport=httpx.ASGITransport(app=gateway_app),
    health_endpoint=None,
    max_retry_attempts=3,
)
driver = AgentAPIDriver(client=client, model="gemini-2.5-flash")
session = await driver.start_session(StartSessionRequest(backend_id="gemini"))

async for event in driver.send_turn(
    SendTurnRequest(session_id=session.session_id, messages=[...])
):
    if event.type == "message_completed":
        print(event.get_payload("text"))
```

Este padrão substitui o uso direto do `OpenAICompatibleProvider` e oferece:
- Sessões lógicas com state machine
- Eventos canónicos (`turn_started`, `message_completed`, `turn_completed`)
- Retry com tenacity e health check configurável
- Integração com `BackendResolver` para configuração declarativa
