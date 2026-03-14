# Production Rollback Checklist

- Interromper liberação de tráfego ao detectar falha estrutural do runtime novo
- Registrar `run_id`, erro e janela temporal afetada
- Voltar para a versão anterior conhecida como estável
- Confirmar startup da versão revertida
- Validar acesso ao backend persistente após rollback
- Executar smoke test mínimo do fluxo principal
- Verificar logs estruturados e ausência de nova cascata de falhas
- Documentar causa, impacto e condição para novo rollout
