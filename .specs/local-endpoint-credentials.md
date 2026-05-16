# Spec: Local Endpoint Credentials — Desacoplar `OPENAI_API_KEY` de endpoints customizados

| Campo      | Valor                                          |
|------------|------------------------------------------------|
| Data       | 2026-05-16                                     |
| Autor      | DX Sprint 3                                    |
| Status     | Rascunho                                       |
| Spec ID    | 010                                            |
| Origem     | `docs/plans/AVALIACAO-MINIAUTOGEN.md` §3 e §7.1 |

---

## Contrato de Prompt (G/C/FC)

### 🎯 Goal

Permitir que o `openai_sdk_factory` construa o `AsyncOpenAI` apontado para um endpoint local (gateway OpenAI-compatible, Ollama, LM Studio, Gemini CLI Gateway, vLLM, etc.) **sem exigir** que o usuário exporte `OPENAI_API_KEY=dummy`. Quando o `endpoint` for declarado e o host não for `api.openai.com`, o driver deve injetar um token sentinela seguro automaticamente e prosseguir.

### 🚧 Constraint

1. **Isolamento de Adapters intacto:** a lógica nasce e morre em `miniautogen/backends/openai_sdk/factory.py` (camada de adapter). O `core/` continua sem conhecimento de OpenAI/host strings.
2. **Zero regressão para uso normal:** quando o endpoint apontar para `api.openai.com` (ou for omitido), a falha por chave ausente **deve continuar acontecendo** com mensagem clara. O sentinela só vale para endpoints customizados.
3. **Não introduzir auth bypass implícito:** o sentinela é literal e auditável (`sk-noauth-local`); nunca uma string vazia ou `None`.

### 🛑 Failure Condition

- `pytest tests/backends/openai_sdk/test_factory.py` falha em qualquer cenário.
- Rodar `miniautogen run` contra um endpoint `http://localhost:11434/v1` sem `OPENAI_API_KEY` no ambiente ainda dispara `OpenAIError: api_key missing`.
- Rodar `miniautogen run` contra `api.openai.com` (ou endpoint vazio) **sem** chave passa silenciosamente — isso seria um regression de segurança.
- O sentinela vaza para logs estruturados (structlog/observability) sem ser mascarado.

---

## User Stories

- Como **engenheiro experimentando com LLMs locais**, quero apontar `endpoint` no `miniautogen.yaml` e rodar imediatamente, para que não precise descobrir o "hack" de exportar uma variável de ambiente falsa.
- Como **usuário corporativo com OpenAI real**, quero que esquecer a `OPENAI_API_KEY` ainda falhe com mensagem clara, para que minha integração de produção não seja silenciosamente desabilitada.
- Como **auditor de segurança**, quero que o token sentinela seja literal e logado, para conseguir grepar por instâncias de uso em ambientes errados.

---

## Critérios de Aceitação

- [ ] `openai_sdk_factory` injeta `sk-noauth-local` quando: `config.endpoint` é não-vazio **E** host extraído de `endpoint` não é `api.openai.com` **E** `api_key` resolvido é `None`.
- [ ] Quando `config.endpoint` aponta para `api.openai.com` (ou subdomínio `*.openai.com`) e `api_key` é `None`, o factory levanta `BackendConfigurationError` com mensagem acionável apontando para a env var esperada.
- [ ] Quando `api_key` é fornecido (auth bearer + token_env preenchido), o sentinela **não** é injetado, mesmo para endpoints locais.
- [ ] Um warning estruturado (`structlog.warning("openai_sdk.using_local_sentinel", endpoint=...)`) é emitido sempre que o sentinela for usado.
- [ ] Pelo menos 6 casos de teste cobrindo a tabela de decisão (endpoint × api_key × host).
- [ ] `ruff` e `mypy --strict` passam.
- [ ] Nenhum teste existente regride.

---

## Invariantes Afetadas

- [x] **Isolamento de Adapters** — a lógica fica em `backends/openai_sdk/`; nenhum import novo no `core/`.
- [ ] **Microkernel / PipelineRunner**
- [ ] **Assincronismo Canônico (AnyIO)**
- [ ] **Policies Event-Driven**

> A spec preserva o isolamento ao restringir a heurística de detecção de host ao adapter. O domínio recebe apenas o `OpenAISDKDriver` já configurado.

---

## Dependências

| Dependência                                       | Tipo       | Estado                                |
|---------------------------------------------------|------------|---------------------------------------|
| `openai` SDK >= 1.3.9                             | Externa    | Já em `pyproject.toml`                |
| `miniautogen/backends/config.py::BackendConfig`   | Interna    | Sem alteração                         |
| `miniautogen/backends/errors.py`                  | Interna    | Adicionar `BackendConfigurationError` (se ainda não existir) |
| Taxonomia de erros (`configuration`)              | Interna    | Já existe; reusar                     |

---

## Notas Adicionais

- Spec correlata: `agent-driver-protocol.md` (não bloqueia, mas é coerente — ambos reforçam isolamento de adapter).
- O usuário sugeriu chamar o sentinela de `dummy`; preferimos `sk-noauth-local` por ser auto-explicativo em logs.
- Tabela de decisão deve ser explicitada no plano técnico (não na spec).
