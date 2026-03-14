# Production Configuration Contract

## Variáveis obrigatórias

- `DATABASE_URL`
  - backend persistente principal para stores operacionais
  - ausência deve falhar na inicialização de settings

## Variáveis com default

- `MINIAUTOGEN_DEFAULT_PROVIDER`
  - default: `litellm`

- `MINIAUTOGEN_DEFAULT_MODEL`
  - default: `gpt-4o-mini`

- `MINIAUTOGEN_DEFAULT_TIMEOUT_SECONDS`
  - default: `30.0`

- `MINIAUTOGEN_DEFAULT_RETRY_ATTEMPTS`
  - default: `1`

## Regras

- defaults existem só para boot mínimo controlado
- produção deve explicitar ao menos `DATABASE_URL`
- valores inválidos devem falhar cedo via validação de settings
