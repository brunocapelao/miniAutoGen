# MiniAutoGen Production Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** levar o MiniAutoGen do estado atual de MVP técnico funcional na nova arquitetura para um estado com requisitos mínimos de segurança operacional para primeiro deploy em produção.

**Architecture:** este plano não muda a direção arquitetural principal. Ele endurece a nova estrutura já implantada com typing verificável, tratamento de falhas operacionais reais, concorrência controlada do runtime, observabilidade mínima útil e critérios explícitos de configuração, deploy e rollback.

**Tech Stack:** Python 3.10+, Pydantic v2, AnyIO, SQLAlchemy 2.x, pytest, pytest-asyncio, Ruff, MyPy, structlog

---

## Objetivo de Produção

O projeto só pode ser considerado minimamente pronto para um primeiro ambiente de produção quando:

- `mypy` fecha no escopo principal da nova arquitetura ou existe baseline residual explícito e pequeno
- o runtime trata falhas operacionais previsíveis com estado terminal consistente
- concorrência do runner é validada com execuções simultâneas
- logs e eventos do caminho principal são suficientes para diagnóstico básico
- configuração e rollout têm contrato claro de ambiente, migração e rollback

## Fora do Escopo

- observabilidade enterprise completa com OpenTelemetry exporters
- auto-healing ou circuit breaker avançado
- policy engine sofisticado
- multi-tenant hardening profundo
- benchmarks formais de throughput em escala

## Exit Criteria

- typing da nova arquitetura está validado
- testes de falha operacional e concorrência passam
- checklist de produção está documentada e verificável
- há um procedimento explícito de configuração, startup e rollback

### Task 1: Fechar o baseline real de `mypy`

**Files:**
- Modify: `pyproject.toml`
- Create: `docs/plans/backlog/production-readiness-typing-baseline.md`
- Modify: arquivos tocados por erros reais de typing

**Step 1: Rodar o type-check do escopo novo**

Run:

```bash
python -m mypy miniautogen/core miniautogen/adapters miniautogen/stores miniautogen/compat miniautogen/policies miniautogen/observability
```

Expected: lista objetiva dos erros ou hang reproduzível.

**Step 2: Se houver travamento, isolar por pacote**

Run:

```bash
python -m mypy miniautogen/core
python -m mypy miniautogen/adapters
python -m mypy miniautogen/stores
python -m mypy miniautogen/compat
python -m mypy miniautogen/policies
python -m mypy miniautogen/observability
```

Expected: localizar o ponto exato que trava ou falha.

**Step 3: Corrigir somente erros reais e documentar o residual**

Criar `docs/plans/backlog/production-readiness-typing-baseline.md` com:

- comandos executados
- erros corrigidos
- pacotes verdes
- eventual residual aceito com justificativa curta

**Step 4: Reexecutar o baseline**

Run:

```bash
python -m mypy miniautogen/core miniautogen/adapters miniautogen/stores miniautogen/compat miniautogen/policies miniautogen/observability
```

Expected: PASS ou residual explicitamente documentado.

**Step 5: Commit**

```bash
git add pyproject.toml miniautogen docs/plans/backlog/production-readiness-typing-baseline.md
git commit -m "chore: establish typing baseline for production readiness"
```

### Task 2: Cobrir falhas operacionais do runtime

**Files:**
- Modify: `miniautogen/core/runtime/pipeline_runner.py`
- Create: `tests/core/runtime/test_runner_operational_failures.py`

**Step 1: Escrever testes que falham para falhas reais**

Cobrir:

- erro de persistência no `RunStore`
- erro de persistência no `CheckpointStore`
- falha do pipeline após evento `run_started`
- garantia de estado terminal consistente

**Step 2: Rodar os testes**

Run:

```bash
PYTHONPATH=. pytest tests/core/runtime/test_runner_operational_failures.py -q
```

Expected: FAIL se o runner ainda deixar estado inconsistente.

**Step 3: Implementar o mínimo seguro**

Regras mínimas:

- nunca deixar run “pendurado” em `started`
- em falha operacional, persistir estado terminal coerente
- emitir evento terminal coerente
- não mascarar exceção original

**Step 4: Rodar os testes do runtime**

Run:

```bash
PYTHONPATH=. pytest tests/core/runtime -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_runner_operational_failures.py
git commit -m "fix: harden pipeline runner against operational failures"
```

### Task 3: Validar concorrência mínima do runner

**Files:**
- Create: `tests/core/runtime/test_runner_concurrency.py`
- Modify: `miniautogen/core/runtime/pipeline_runner.py` se necessário

**Step 1: Escrever o teste que falha**

Cobrir execuções concorrentes com:

- `run_id` distintos
- stores distintos por execução
- eventos sem colisão de `correlation_id`

**Step 2: Rodar o teste**

Run:

```bash
PYTHONPATH=. pytest tests/core/runtime/test_runner_concurrency.py -q
```

Expected: FAIL se houver estado compartilhado indevido.

**Step 3: Corrigir o mínimo**

Não adicionar infraestrutura complexa.
Só eliminar shared state indevido no runner.

**Step 4: Rodar a suíte de runtime**

Run:

```bash
PYTHONPATH=. pytest tests/core/runtime -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_runner_concurrency.py
git commit -m "test: validate concurrent execution safety for pipeline runner"
```

### Task 4: Endurecer observabilidade mínima

**Files:**
- Modify: `miniautogen/observability/logging.py`
- Modify: `miniautogen/chat/chatadmin.py`
- Modify: `miniautogen/pipeline/components/components.py`
- Create: `tests/observability/test_runtime_logging_context.py`

**Step 1: Escrever o teste que falha**

Cobrir:

- logger com contexto mínimo (`run_id`, `correlation_id` quando aplicável)
- logs coerentes nos pontos principais de runtime

**Step 2: Rodar o teste**

Run:

```bash
PYTHONPATH=. pytest tests/observability/test_runtime_logging_context.py -q
```

Expected: FAIL se o contexto ainda não for consistente.

**Step 3: Implementar o mínimo**

Garantir:

- binding de contexto onde o runtime cria execução
- logging útil sem inflar a camada

**Step 4: Rodar testes de observabilidade**

Run:

```bash
PYTHONPATH=. pytest tests/observability -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add miniautogen/observability miniautogen/chat/chatadmin.py miniautogen/pipeline/components/components.py tests/observability/test_runtime_logging_context.py
git commit -m "feat: enrich runtime logging context for production diagnostics"
```

### Task 5: Formalizar configuração e startup mínimos

**Files:**
- Create: `miniautogen/app/settings.py`
- Create: `tests/app/test_settings.py`
- Create: `docs/plans/backlog/production-config-contract.md`

**Step 1: Escrever o teste que falha**

Cobrir `settings` mínimos:

- `DATABASE_URL`
- provider/model default
- timeout default
- retry default

**Step 2: Rodar o teste**

Run:

```bash
PYTHONPATH=. pytest tests/app/test_settings.py -q
```

Expected: FAIL porque o contrato ainda não existe.

**Step 3: Implementar o contrato mínimo**

Usar `pydantic-settings` se já estiver disponível; se não, usar Pydantic simples com leitura explícita de `os.environ`.

**Step 4: Documentar o contrato**

Criar `docs/plans/backlog/production-config-contract.md` com:

- variáveis obrigatórias
- defaults aceitáveis
- comportamento quando ausentes

**Step 5: Rodar testes focados**

Run:

```bash
PYTHONPATH=. pytest tests/app/test_settings.py -q
```

Expected: PASS

**Step 6: Commit**

```bash
git add miniautogen/app/settings.py tests/app/test_settings.py docs/plans/backlog/production-config-contract.md
git commit -m "feat: define minimal production configuration contract"
```

### Task 6: Documentar rollout e rollback

**Files:**
- Create: `docs/plans/backlog/production-rollout-checklist.md`
- Create: `docs/plans/backlog/production-rollback-checklist.md`

**Step 1: Documentar rollout mínimo**

Checklist de rollout com:

- validação de config
- migração/init de stores persistentes
- smoke test pós-start
- verificação de logs/eventos

**Step 2: Documentar rollback mínimo**

Checklist de rollback com:

- critérios de abortar deploy
- voltar para versão anterior
- validar stores e logs após rollback

**Step 3: Revisar coerência com a arquitetura**

Garantir que os checklists reflitam o caminho novo, não as facades legadas.

**Step 4: Commit**

```bash
git add docs/plans/backlog/production-rollout-checklist.md docs/plans/backlog/production-rollback-checklist.md
git commit -m "docs: add rollout and rollback checklists for production readiness"
```

### Task 7: Hardening final de produção

**Files:**
- Modify: `docs/plans/backlog/production-readiness-typing-baseline.md`
- Modify: `docs/plans/backlog/production-config-contract.md`
- Create: `docs/plans/backlog/production-readiness-exit-checklist.md`

**Step 1: Criar a checklist final**

Registrar:

- typing
- runtime failures
- concorrência
- observabilidade
- config
- rollout
- rollback

**Step 2: Rodar verificação final**

Run:

```bash
ruff check miniautogen tests
PYTHONPATH=. pytest tests/test_core.py tests/regression tests/core tests/runtime tests/adapters tests/stores tests/compat tests/observability tests/policies tests/properties tests/pipeline tests/app -q
python -m mypy miniautogen/core miniautogen/adapters miniautogen/stores miniautogen/compat miniautogen/policies miniautogen/observability miniautogen/app
```

Expected:

- `ruff`: PASS
- `pytest`: PASS
- `mypy`: PASS ou residual pequeno documentado

**Step 3: Atualizar o status final**

Criar `docs/plans/backlog/production-readiness-exit-checklist.md` com:

- blockers fechados
- riscos aceitos
- itens conscientemente adiados

**Step 4: Commit**

```bash
git add docs/plans/backlog/production-readiness-* miniautogen tests/app
git commit -m "chore: finalize production readiness baseline"
```

## Verificação Final

Run:

```bash
ruff check miniautogen tests
PYTHONPATH=. pytest tests/test_core.py tests/regression tests/core tests/runtime tests/adapters tests/stores tests/compat tests/observability tests/policies tests/properties tests/pipeline tests/app -q
python -m mypy miniautogen/core miniautogen/adapters miniautogen/stores miniautogen/compat miniautogen/policies miniautogen/observability miniautogen/app
```

## Resultado Esperado

- o projeto mantém a nova arquitetura como caminho principal
- a operação mínima de produção fica documentada e verificável
- typing, falhas operacionais e concorrência têm evidência concreta
- o primeiro deploy passa a ter critérios objetivos de go/no-go
