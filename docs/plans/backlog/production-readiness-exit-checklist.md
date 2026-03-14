# Production Readiness Exit Checklist

## Blockers Fechados

- baseline real de typing definido para o escopo principal da nova arquitetura
- runtime endurecido para falhas operacionais e timeout
- concorrência mínima do runner validada
- contexto básico de logs estruturados no caminho oficial
- contrato mínimo de configuração definido
- checklists de rollout e rollback documentados

## Riscos Aceitos

- a observabilidade ainda é baseline e não inclui integração completa com backends externos
- as facades legadas continuam expostas por compatibilidade

## Itens Conscientemente Adiados

- OpenTelemetry completo
- replay completo
- remoção física das facades legadas
- políticas mais sofisticadas de budget/permission

## Go/No-Go

- `ruff check miniautogen tests`
- `pytest` amplo verde
- `mypy` verde no escopo principal da nova arquitetura
- smoke test de startup e stores persistentes verde
- rollout e rollback revisados antes do deploy
