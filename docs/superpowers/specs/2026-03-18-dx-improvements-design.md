# DX Improvements: 8 Melhorias de Developer Experience para Agentes

> **Status:** Approved
> **Data:** 2026-03-18
> **Referência:** `docs/dx-comparison-noviuz.md`

---

## Contexto

Análise comparativa entre miniAutoGen e noviuz-app revelou 8 gaps no setup de DX com agentes. O miniAutoGen é superior em orquestração multi-modelo e skills processuais, mas inferior em enforcement automatizado — invariantes existem no CLAUDE.md mas não há gates programáticos. Este spec define as 8 melhorias a implementar.

## Objetivo

Transformar enforcement verbal (CLAUDE.md) em enforcement programático (CI gates, linters AST, hooks automáticos) sem perder as vantagens existentes (delegação multi-modelo, skills processuais, memória semântica).

---

## 1. Sistema de Specs (`.specs/`)

### Problema
O CLAUDE.md exige spec-driven development (`/.specs/template.md`), mas o diretório não existe. O agente ignora porque não há infraestrutura.

### Solução

**Estrutura de diretórios:**
```
.specs/
├── template.md            # Template de especificação
├── plan-template.md       # Template de plano técnico
└── tasks-template.md      # Template de decomposição em tasks
```

**Slash commands em `.claude/commands/`:**
```
.claude/commands/
├── spec-create.md         # Cria branch + diretório + spec a partir do template
├── spec-plan.md           # Gera plano técnico a partir de spec existente
└── spec-tasks.md          # Decompõe plano em tasks numeradas
```

**Script de automação:**
```
scripts/specs/
└── create-feature.sh      # Cria branch feat/NNN-name + .specs/NNN-name/
```

### Templates

**`template.md`** deve conter:
- Goal / Constraint / Failure Condition (alinhado com o Contrato de Prompt do CLAUDE.md)
- User Stories (formato: como X, quero Y, para que Z)
- Critérios de aceitação (checkboxes)
- Invariantes afetadas (referência às 4 regras de ouro)
- Dependências

**`plan-template.md`** deve conter:
- Arquitetura proposta (quais módulos serão tocados)
- Contratos/interfaces novos ou alterados
- Riscos e mitigações
- Estimativa de complexidade

**`tasks-template.md`** deve conter:
- Tasks numeradas (T001, T002...)
- Dependências entre tasks
- Flag de paralelizabilidade (P)
- Critério de done por task

### Critérios de sucesso
- `.specs/` existe com 3 templates funcionais
- Slash commands criam specs a partir dos templates
- Script bash cria branch + diretório automaticamente

---

## 2. Linters Arquiteturais (Scripts Standalone)

### Problema
4 invariantes no CLAUDE.md são enforcement verbal — dependem do agente respeitar. Não há validação programática.

### Solução

**Arquivo:** `scripts/check_arch.py`

**4 validações AST:**

| Check | Invariante | O que valida |
|-------|-----------|--------------|
| `check_adapter_isolation()` | Isolamento de Adapters | `core/**/*.py` não importa de `adapters/`, `backends/` nem bibliotecas externas de LLM (litellm, openai, google, anthropic) |
| `check_runner_exclusivity()` | PipelineRunner único | Nenhuma classe fora de `core/runtime/` define um método `run`/`execute` que contenha loop infinito (`while True`/`while not done`) E instancie `RunContext` ou `RunResult`. O check procura a combinação de ambos os padrões — loops genéricos (retry, polling) são permitidos. |
| `check_anyio_compliance()` | AnyIO canônico | `core/**/*.py` não importa `threading`, `asyncio.run`, `multiprocessing`, `concurrent.futures` |
| `check_event_emission()` | Event emission | Classes em `core/runtime/` que herdam de `CoordinationMode` (protocol) ou contêm método `run`/`execute` devem conter pelo menos uma referência a `ExecutionEvent` (instanciação ou chamada a `emit`/`publish`/`send_event`). O check faz AST scan por esses padrões. |

**Interface:**
```bash
$ python scripts/check_arch.py
[PASS] adapter_isolation: core/ has no adapter imports
[PASS] runner_exclusivity: no parallel executors found
[FAIL] anyio_compliance: core/runtime/foo.py:42 imports threading
[PASS] event_emission: all runtime classes emit events

Result: 1 FAILED, 3 PASSED
```

**Exit code:** 0 se todos passam, 1 se qualquer falha. Compatível com CI.

**Dependências:** Apenas `ast` e `pathlib` (stdlib). Zero dependências externas.

### Critérios de sucesso
- Script roda sem instalar o miniautogen
- 4 checks implementados e passando no código atual
- Exit code correto para CI

---

## 3. CI Pipeline (GitHub Actions Minimal)

### Problema
Sem CI no repositório. PRs podem ser mergeados sem validação.

### Solução

**Arquivo:** `.github/workflows/ci.yml`

**Trigger:** Push e PR para `main`.

**Jobs:**

```
lint ──────→ ci-passed
test ──────→ ci-passed
arch-check → ci-passed
```

| Job | Comandos | Dependências |
|-----|----------|-------------|
| `lint` | `ruff check miniautogen/ tests/` + `mypy miniautogen/` | Nenhuma (fast) |
| `test` | `pytest tests/ --cov=miniautogen --cov-report=json` | Nenhuma |
| `arch-check` | `python scripts/check_arch.py` | Nenhuma (stdlib) |
| `ci-passed` | Echo "gates passed" | Todos os anteriores |

**Python version:** 3.11 (single version, sem matrix — projeto requer `python >3.10, <3.12`).

**Caching:** `pip cache` para acelerar instalação.

### Critérios de sucesso
- CI roda em push/PR para main
- 3 jobs independentes + gate final
- Todos passando no estado atual do código

---

## 4. Hooks de Ciclo de Vida

### Problema
Apenas `SessionStart` via ring-dev-team. Sem hooks de SessionEnd (perde contexto), sem hooks de UserPromptSubmit (sem injeção de estado).

### Solução

**Scripts:**
```
scripts/hooks/
├── session-end.sh         # Auto-resume de decisões
└── pre-prompt.sh          # Injeta estado atual do projeto
```

**`session-end.sh`** deve:
- Capturar branch atual, últimos commits da sessão
- Gerar resumo de mudanças (git diff --stat)
- Salvar como memória tipo `project` no sistema existente (se houve mudanças significativas)

**`pre-prompt.sh`** deve:
- Mostrar branch atual
- Status de tests (último resultado se disponível)
- Arquivos modificados não commitados

**Pré-requisito:** O diretório `.claude/` do projeto deve existir. Criar se necessário.

**Configuração em `.claude/settings.json`** (merge com configuração existente):
```json
{
  "hooks": {
    "SessionEnd": [{
      "matcher": "",
      "hooks": [{"type": "command", "command": "scripts/hooks/session-end.sh"}]
    }],
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{"type": "command", "command": "scripts/hooks/pre-prompt.sh"}]
    }]
  }
}
```

**Nota:** O schema de hooks do Claude Code usa `hooks` como chave top-level, com eventos como sub-chaves, cada um contendo um array de objetos `{matcher, hooks}`. Verificar compatibilidade com a versão instalada do Claude Code antes de mergear na settings existente.

### Critérios de sucesso
- Hooks executam sem erro nos eventos corretos
- **Validação:** Adicionar `echo "[HOOK] session-end fired"` no script e verificar que aparece ao encerrar sessão
- `session-end.sh` gera output útil (branch, diff stat)
- `pre-prompt.sh` injeta estado sem ser verboso

---

## 5. Whitelist Granular de Permissões

### Problema
Whitelist atual: apenas `ls` e `python`. O agente pede aprovação para TUDO, gerando friction.

### Solução

**Arquivo:** `.claude/settings.local.json`

```json
{
  "permissions": {
    "allow": [
      "Bash(cat:*)",
      "Bash(git:*)",
      "Bash(find:*)",
      "Bash(tree:*)",
      "Bash(grep:*)",
      "Bash(ls:*)",
      "Bash(wc:*)",
      "Bash(python:*)",
      "Bash(pytest:*)",
      "Bash(ruff:*)",
      "Bash(mypy:*)",
      "Bash(pip:*)",
      "Bash(make:*)"
    ]
  }
}
```

**Princípio:** Permitir operações de leitura e ferramentas de desenvolvimento. Não permitir operações destrutivas (rm, git push, docker).

### Critérios de sucesso
- Agente executa git, pytest, ruff, mypy sem pedir aprovação
- Operações destrutivas continuam requerendo aprovação

---

## 6. Multi-Agent Awareness

### Problema
Apenas CLAUDE.md. Copilot e Gemini operam sem guardrails.

### Solução

**Arquivos:**
```
.github/
├── copilot-instructions.md
└── gemini.md
```

**Conteúdo de ambos:**
- Referência ao CLAUDE.md como source of truth para invariantes
- Resumo das 4 invariantes arquiteturais
- Resumo das 4 condições de rejeição
- Referência à taxonomia canônica de erros
- Workflow mandatório (spec → test → implement → commit)

**Princípio:** NÃO duplicar conteúdo. Ambos os arquivos referenciam o CLAUDE.md e o `docs/pt/architecture/05-invariantes.md` como fontes canônicas. Contêm apenas adaptações de formato para cada agente.

### Critérios de sucesso
- Copilot e Gemini têm instruções consistentes com CLAUDE.md
- Zero duplicação de regras — tudo referencia fonte canônica

---

## 7. Memória Automatizada

### Problema
Sistema de memória é manual — requer ação explícita para salvar. Em sessões longas, decisões se perdem.

### Solução

Integrado com o hook `session-end.sh` (item 4).

**Limitação importante:** O script bash tem acesso apenas a artefatos git (branch, commits, diffs), NÃO ao conteúdo da conversa ou raciocínio do agente. Portanto, a memória automática captura **o que mudou**, não **por que mudou**. Decisões semânticas continuam dependendo de salvamento manual (ou do agente seguir as instruções do CLAUDE.md de resumir decisões ao final de sessões complexas).

**O que o script captura:**

1. Detecta se houve mudanças significativas na sessão (commits desde o início da sessão)
2. Se sim, gera um arquivo de memória tipo `project` com:
   - Nome: `session_YYYY-MM-DD_HH-MM.md`
   - Frontmatter: name, description, type: project
   - Conteúdo: branch, lista de commits da sessão (hash + mensagem), diff stat
3. Adiciona ponteiro no `MEMORY.md`

**O que o script NÃO captura:** Raciocínio arquitetural, tradeoffs, decisões rejeitadas. Para isso, o agente deve usar o sistema manual de memória conforme instruído no CLAUDE.md.

**Não substitui** o sistema existente de 4 tipos. Complementa com auto-save de artefatos git.

### Critérios de sucesso
- Sessões com mudanças geram memória automaticamente
- Sessões sem mudanças não geram ruído
- Memória segue o formato de frontmatter existente

---

## 8. Git Workflow Formalizado

### Problema
Sem convenção de branches ou commits documentada. Features vão direto para main.

### Solução

Adicionar seção ao CLAUDE.md (não criar arquivo separado — CLAUDE.md já é o contrato):

```markdown
## 5. Convenções Git

### Branches
- `feat/nome-descritivo` — nova funcionalidade
- `fix/nome-descritivo` — correção de bug
- `chore/nome-descritivo` — manutenção, refactor, tooling
- `docs/nome-descritivo` — documentação

### Commits
Formato: `type(scope): descrição concisa`

Tipos: feat, fix, refactor, test, docs, chore, ci
Scopes: core, runtime, policies, stores, adapters, cli, tui, backends

Exemplos:
- `feat(runtime): add checkpoint recovery to PipelineRunner`
- `fix(policies): handle timeout edge case in BudgetTracker`
- `test(stores): add SQLAlchemy integration tests`

### Merge
- Squash merge para branches de feature
- Merge commit para releases
```

### Critérios de sucesso
- Convenção documentada no CLAUDE.md
- Agente segue a convenção em commits futuros

---

## Dependências entre Itens

```
1. Specs ─────────────────── independente
2. Linters ───────────────── independente
3. CI ────────────────────── depende de 2 (arch-check)
4. Hooks ─────────────────── independente
5. Permissões ────────────── independente
6. Multi-agent ───────────── independente
7. Memória automatizada ──── depende de 4 (session-end.sh)
8. Git workflow ──────────── independente
```

**Ordem sugerida de implementação:**
1. Itens independentes em paralelo: 1, 2, 4, 5, 6, 8
2. Depois: 3 (depende de 2), 7 (depende de 4)

---

## Fora de Escopo

- Não alterar o sistema de Ring teams ou Superpowers
- Não alterar o Codex MCP delegation
- Não criar Layer 3 canonical patterns
- Não migrar para monorepo ou alterar estrutura de pacotes
