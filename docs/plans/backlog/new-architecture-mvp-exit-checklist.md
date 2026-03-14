# New Architecture MVP Exit Checklist

## Contratos oficiais

- `LLMProvider` como contrato oficial de integração LLM
- `MessageStore` como contrato oficial de mensagens
- `RunStore` e `CheckpointStore` presentes na nova estrutura

## Runtime oficial

- `PipelineRunner` é o caminho principal de execução
- `ExecutionPolicy` é aplicada no runner
- eventos canônicos são publicados no caminho oficial

## Persistência mínima

- `InMemoryMessageStore` funcional
- `InMemoryRunStore` funcional
- `InMemoryCheckpointStore` funcional
- `SQLAlchemyRunStore` funcional
- `SQLAlchemyCheckpointStore` funcional

## Policies mínimas

- `RetryPolicy` aplicada apenas nos adapters
- `ExecutionPolicy` aplicada apenas no runtime

## Compatibilidade remanescente

- módulos legados continuam importáveis
- módulos legados não são o caminho principal do runtime
- remoção física do legado fica para fase posterior

## Fora do MVP

- OpenTelemetry completo
- replay completo
- MCP
- `Instructor`
- remoção física das facades legadas
