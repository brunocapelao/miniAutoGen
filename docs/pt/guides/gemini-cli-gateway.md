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
