# Wave 4: Events, Policies, and Hardening

## Entregas

- Completar a taxonomia canônica de eventos em `miniautogen.core.events`.
- Publicar eventos de início, fim e timeout no `PipelineRunner`.
- Introduzir `EventSink` em memória e sink nulo.
- Adicionar baseline de logging estruturado em `miniautogen.observability`.
- Introduzir categorias explícitas de policy em `miniautogen.policies`.
- Expor marcadores de estabilidade pública em `miniautogen.compat.public_api`.
- Endurecer a wave com property tests e baseline adicional de `mypy`.

## Definição de pronto

- `ExecutionEvent` aceita os campos canônicos e os aliases legados.
- `PipelineRunner` publica eventos operacionais sem quebrar a API existente.
- Logging estruturado existe sem acoplar o runtime a OpenTelemetry.
- Policies permanecem declarativas e fora do core operacional.
- Marcadores `stable`, `experimental` e `internal` estão disponíveis e testados.
- Property tests e verificações estáticas passam na superfície tocada.

## Verificação

- `ruff check miniautogen tests/core/events tests/core/runtime tests/observability tests/policies tests/compat tests/properties`
- `PYTHONPATH=. pytest tests/core/events tests/core/runtime tests/observability tests/policies tests/compat tests/properties -q`
- `PYTHONPATH=. pytest tests/regression -q`
- `python -m mypy miniautogen/core/contracts/events.py miniautogen/core/events miniautogen/core/runtime/pipeline_runner.py miniautogen/observability miniautogen/policies miniautogen/compat`
