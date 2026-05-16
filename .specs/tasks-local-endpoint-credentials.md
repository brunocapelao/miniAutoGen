# Tarefas: Local Endpoint Credentials

| Campo      | Valor       |
|------------|-------------|
| Spec ID    | 010         |
| Data       | 2026-05-16  |
| Total      | 6 tarefas   |

---

## Legenda

- **Status:** TODO / IN_PROGRESS / DONE / BLOCKED
- **P:** Paralelizável (sim/não)
- **Deps:** IDs de tarefas das quais esta depende

---

## Tarefas

### T001 — Escrever testes falhando para tabela de decisão

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Criar `tests/backends/openai_sdk/test_factory.py` com 6 testes, um por linha da tabela de decisão do plano. Usar `pytest.raises(BackendConfigurationError)` para casos de falha; verificar que `AsyncOpenAI` recebe `api_key="sk-noauth-local"` nos casos de injeção via `unittest.mock.patch`.

**Critério de conclusão:**
- [ ] 6 testes presentes e nomeados pelo cenário (`test_local_endpoint_no_key_injects_sentinel`, `test_openai_host_no_key_raises`, etc.)
- [ ] `pytest tests/backends/openai_sdk/test_factory.py` falha com 6 erros (esperado — implementação ausente)
- [ ] Nenhum teste é parametrizado em excesso (cada cenário fica legível isoladamente)

---

### T002 — Adicionar `BackendConfigurationError`

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | —     |

**Descrição:** Em `miniautogen/backends/errors.py`, declarar `BackendConfigurationError(BackendError)` com `error_category = "configuration"` (categoria canônica do CLAUDE.md §4.2). Se a classe já existir, pular esta tarefa e marcar DONE.

**Critério de conclusão:**
- [ ] `from miniautogen.backends.errors import BackendConfigurationError` funciona
- [ ] `BackendConfigurationError.error_category == "configuration"`
- [ ] Adicionada ao `__all__` do módulo se existir

---

### T003 — Implementar `_is_openai_host` e refatorar factory

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T001, T002 |

**Descrição:** Em `miniautogen/backends/openai_sdk/factory.py`, adicionar `_is_openai_host(endpoint)` (privada) e a constante `_LOCAL_SENTINEL = "sk-noauth-local"`. Reescrever a resolução de `api_key` conforme o plano:
1. Se já há `api_key`, usar.
2. Senão, se `_is_openai_host(config.endpoint)`, raise `BackendConfigurationError` com mensagem citando `auth.token_env`.
3. Senão, definir `api_key = _LOCAL_SENTINEL` e emitir `structlog.warning("openai_sdk.using_local_sentinel", endpoint=...)`.

**Critério de conclusão:**
- [ ] Suite `pytest tests/backends/openai_sdk/test_factory.py` → 6/6 verdes
- [ ] `ruff check miniautogen/backends/openai_sdk/factory.py` limpo
- [ ] `mypy miniautogen/backends/openai_sdk/factory.py` sem erros

---

### T004 — Regressão completa

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | não   |
| Deps     | T003  |

**Descrição:** Rodar `pytest` completo. Garantir 0 regressões em integrações que usam `OpenAISDKDriver` (ex: testes de pipeline com engine `openai-compat`).

**Critério de conclusão:**
- [ ] `pytest` passa 100%
- [ ] Nenhum teste pré-existente alterado para acomodar a mudança

---

### T005 — Smoke test manual contra endpoint local

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T003  |

**Descrição:** Em um workspace com `miniautogen.yaml` apontando para `http://localhost:11434/v1` (Ollama), com `OPENAI_API_KEY` **não** exportada, rodar `miniautogen run main --verbose`. Confirmar que: (a) execução prossegue, (b) warning estruturado aparece em stderr.

**Critério de conclusão:**
- [ ] Comando executa sem `Missing credentials`
- [ ] Log `openai_sdk.using_local_sentinel` aparece exatamente 1× por sessão de driver
- [ ] Reverter para endpoint `api.openai.com` sem chave reproduz erro claro

---

### T006 — Atualizar documentação de onboarding

| Campo    | Valor |
|----------|-------|
| Status   | TODO  |
| P        | sim   |
| Deps     | T003  |

**Descrição:** Adicionar uma nota em `docs/getting-started.md` (ou seção equivalente do `README.md`) sob "Usando LLMs locais": "Quando `endpoint` aponta para um host que não é `*.openai.com`, o framework usa um token sentinela e não exige `OPENAI_API_KEY`. Para autenticar contra OpenAI real, configure `auth.token_env`."

**Critério de conclusão:**
- [ ] Seção existe e cita o sentinela explicitamente
- [ ] Exemplo de `miniautogen.yaml` com endpoint Ollama incluído
- [ ] PR review aprova

---

## Grafo de Dependências

```
T001 ─┐
T002 ─┴─> T003 ─┬─> T004
                ├─> T005
                └─> T006
```

---

## Resumo

| Paralelizáveis | Sequenciais | Bloqueadas | Total |
|----------------|-------------|------------|-------|
| 4              | 2           | 0          | 6     |
