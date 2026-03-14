# Production Rollout Checklist

- Validar `DATABASE_URL` e demais variáveis obrigatórias antes do deploy
- Garantir que o backend persistente de `RunStore` e `CheckpointStore` esteja acessível
- Inicializar tabelas necessárias (`init_db`) antes de tráfego real
- Subir a nova versão e executar smoke test do caminho oficial
- Confirmar emissão de logs estruturados com `run_id` e `correlation_id`
- Confirmar persistência de run e checkpoint em uma execução real
- Confirmar ausência de erros de autenticação/configuração de provider
- Só liberar tráfego após smoke test e logs básicos verdes
