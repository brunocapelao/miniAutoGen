# Análise Comparativa: miniAutoGen vs noviuz-app — DX com Agentes

> **Objetivo:** Identificar o que o noviuz-app faz de diferente (ou melhor) em termos de DX com agentes, e extrair insights de melhoria aplicáveis ao miniAutoGen.

**Data:** Março de 2026

---

## Sumário Executivo

O noviuz-app é um produto de software maduro (Patrimonial OS) com um setup de agentes denso e pragmático. O miniAutoGen é um framework SDK com um setup mais sofisticado em termos de orquestração multi-modelo, mas menos estruturado em enforcement automatizado.

**Conclusão principal:** O noviuz-app é superior em **enforcement automatizado** (CI gates, linters arquiteturais, hooks de ciclo de vida). O miniAutoGen é superior em **orquestração de agentes** (multi-modelo, skills processuais, ring teams). A combinação ideal pega o melhor dos dois.

---

## 1. Comparação Estrutural

| Dimensão | miniAutoGen | noviuz-app | Vantagem |
|----------|-------------|------------|----------|
| **CLAUDE.md** | 1 arquivo root, denso e prescritivo | Hierarquia multi-nível (~100 arquivos, mas maioria são memory logs) | mini — mais focado |
| **Multi-agent awareness** | Apenas Claude Code | Claude + Copilot + Gemini (instruções separadas para cada) | noviuz — portabilidade |
| **Spec-Driven Development** | Referenciado mas `.specs/` não existe | Implementado com `/speckit.*` commands, templates, scripts bash, 36+ specs ativas | noviuz — muito à frente |
| **Skills/Commands** | 80+ skills via Ring + Superpowers plugins | 13 slash commands via `.claude/commands/` (speckit + railway) | mini — mais variado |
| **Delegação multi-modelo** | Claude + GPT-5.2 via Codex MCP (5 especialistas) | Apenas Claude Code (sem segundo modelo) | mini — diferencial claro |
| **Memória** | Arquivos tipados em `~/.claude/projects/*/memory/` com 4 tipos semânticos | `claude-mem` plugin com injection automática em CLAUDE.md distribuídos | noviuz — mais automatizado |
| **Hooks** | Apenas SessionStart (ring-dev-team) | 7 hooks (SessionStart/End, Stop, UserPromptSubmit, Pre/PostToolUse) | noviuz — muito mais rico |
| **CI enforcement** | Sem CI visível no repo | 7 jobs (lint, security, dx-standards, architecture, test, security-test, frontend-test) | noviuz — enforcement real |
| **Linters arquiteturais** | Invariantes no CLAUDE.md (enforcement verbal) | `check-architecture`, `check-everail-readiness`, `rbac-verify`, `validate-invariants` (enforcement por código) | noviuz — programático |
| **Permissões** | Whitelist mínima (ls, python) | Whitelist granular (~40 patterns de bash, ~15 MCP tools, domínios web) | noviuz — mais prático |
| **MCP Servers** | 3 (Codex, Cloudflare, Hetzner) | Railway, Sentry, PostHog, shadcn, IDE (via allowlist) | Empate — diferentes propósitos |
| **Testes** | pytest + hypothesis + ruff + mypy | pytest + vitest + playwright + storybook + ruff + mypy + bandit + pip-audit | noviuz — mais abrangente |
| **Git workflow** | Sem convenção documentada | `feature/* → develop → staging → main` com semantic commits | noviuz — formalizado |

---

## 2. Insights de Melhoria para miniAutoGen

### 2.1 🔴 CRÍTICO: Criar o sistema de Specs (`.specs/`)

**O que o noviuz faz:** Sistema completo de spec-driven development com:
- Scripts bash que criam branch + diretório de spec automaticamente
- Templates para spec, plan, tasks, checklist
- Slash commands (`/speckit.specify`, `/speckit.plan`, `/speckit.tasks`)
- 36+ features rastreadas via specs numeradas
- Qualidade validada com checklist automático

**O que o miniAutoGen tem:** O CLAUDE.md referencia `/.specs/template.md`, mas o diretório não existe.

**Ação sugerida:**
```
.specs/
├── template.md            # Template de spec (copiar conceito do speckit)
├── plan-template.md       # Template de plano técnico
├── tasks-template.md      # Template de decomposição em tasks
└── NNN-feature-name/      # Specs ativas
    ├── spec.md
    ├── plan.md
    └── tasks.md
```

Criar slash commands em `.claude/commands/`:
```
.claude/commands/
├── spec-create.md         # Equivalente ao /speckit.specify
├── spec-plan.md           # Equivalente ao /speckit.plan
└── spec-tasks.md          # Equivalente ao /speckit.tasks
```

**Impacto:** O spec-driven development está no CLAUDE.md como mandatório, mas não existe infraestrutura. O agente ignora porque não há enforcement.

---

### 2.2 🔴 CRÍTICO: Adicionar linters arquiteturais programáticos

**O que o noviuz faz:** Validação de invariantes por código (AST analysis):
```python
# manage.py commands
check-architecture        # Valida RA-002 a RA-010
check-everail-readiness   # Pureza de domínio + emissão de eventos
rbac-verify               # Integridade RBAC
check-dx-standards        # Padrões DX (AST puro, sem DB)
validate-invariants       # 10 invariantes do kernel
```

Estes rodam no CI como jobs obrigatórios. O PR não pode ser mergeado se falhar.

**O que o miniAutoGen tem:** 4 invariantes no CLAUDE.md (isolamento de adapters, PipelineRunner único, AnyIO canônico, policies event-driven), mas enforcement é apenas verbal — depende do agente respeitar.

**Ação sugerida:**
```python
# miniautogen/cli/commands/check_arch.py (ou scripts/)
def check_adapter_isolation():
    """IV.1: core/ não pode importar de adapters/"""
    # AST scan de imports em core/**/*.py

def check_pipeline_runner_exclusivity():
    """IV.2: Não pode existir outro executor além de PipelineRunner"""
    # Grep por padrões de loop de execução fora de runtime/

def check_anyio_compliance():
    """IV.3: Não pode usar threading/asyncio direto no core"""
    # AST scan por imports de threading, asyncio.run, etc.

def check_event_emission():
    """IV.4: Novos componentes devem emitir ExecutionEvent"""
    # Validar que classes em runtime/ emitem eventos
```

**Impacto:** Transforma regras verbais em gates binários. O agente pode rodar `python -m miniautogen check-arch` e ter feedback objetivo.

---

### 2.3 🟡 IMPORTANTE: Expandir hooks de ciclo de vida

**O que o noviuz faz:** 7 hooks via `entire` CLI:

| Hook | Propósito |
|------|-----------|
| `SessionStart` | Injetar contexto, carregar memória |
| `SessionEnd` | Persistir memória, cleanup |
| `Stop` | Snapshot de estado ao parar |
| `UserPromptSubmit` | Interceptar prompt do usuário antes de processar |
| `PreToolUse/Task` | Validar antes de executar task |
| `PostToolUse/Task` | Registrar resultado após task |
| `PostToolUse/TodoWrite` | Sincronizar todos após criação |

**O que o miniAutoGen tem:** Apenas `SessionStart` via ring-dev-team.

**Ação sugerida:** Adicionar em `.claude/settings.json`:
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

Hooks prioritários:
1. **SessionEnd** — salvar resumo de decisões arquiteturais (combate context rot mencionado no CLAUDE.md)
2. **UserPromptSubmit** — injetar estado atual do projeto (branch, tests passing, etc.)

---

### 2.4 🟡 IMPORTANTE: Multi-agent awareness (instruções por modelo)

**O que o noviuz faz:** 3 arquivos de instruções consistentes entre si:
- `CLAUDE.md` — para Claude Code
- `.github/copilot-instructions.md` — para GitHub Copilot
- `.github/gemini.md` — para Gemini

Todos apontam para a mesma `constitution.md` como source of truth. Isso significa que qualquer agente (Claude, Copilot, Gemini) opera com as mesmas invariantes.

**O que o miniAutoGen tem:** Apenas `CLAUDE.md`. Se alguém usar Copilot ou Gemini, não há guardrails.

**Ação sugerida:**
```
.github/
├── copilot-instructions.md    # Invariantes + workflow para Copilot
└── gemini.md                  # Invariantes + workflow para Gemini
```

Extrair as invariantes do CLAUDE.md para um `docs/constitution.md` compartilhado, e fazer os 3 arquivos referenciarem ele.

---

### 2.5 🟡 IMPORTANTE: Whitelist granular de permissões

**O que o noviuz faz:** `settings.local.json` com ~40 patterns de bash explicitamente permitidos:
```json
{
  "permissions": {
    "allow": [
      "Bash(cat:*)", "Bash(git:*)", "Bash(find:*)", "Bash(tree:*)",
      "Bash(grep:*)", "Bash(docker compose:*)", "Bash(make:*)",
      "Bash(npx:*)", "Bash(ruff check:*)", "Bash(pnpm lint:*)",
      "Bash(alembic:*)", "Bash(railway run:*)", "Bash(gh api:*)"
    ]
  }
}
```

Isso é pragmático: o agente pode executar operações comuns sem pedir aprovação a cada vez, mas está contido a um set conhecido.

**O que o miniAutoGen tem:** Apenas `ls` e `python`. Na prática, isso significa que o agente pede aprovação para TUDO, o que gera friction e fadiga de aprovação.

**Ação sugerida:** Criar `.claude/settings.local.json`:
```json
{
  "permissions": {
    "allow": [
      "Bash(cat:*)", "Bash(git:*)", "Bash(find:*)", "Bash(tree:*)",
      "Bash(grep:*)", "Bash(ls:*)", "Bash(wc:*)",
      "Bash(python:*)", "Bash(pytest:*)", "Bash(ruff:*)", "Bash(mypy:*)",
      "Bash(pip:*)"
    ]
  }
}
```

**Impacto:** Reduz friction sem sacrificar segurança. O agente flui em operações de desenvolvimento sem interrupção.

---

### 2.6 🟡 IMPORTANTE: CI Pipeline

**O que o noviuz faz:** GitHub Actions com 7 jobs que formam um gate binário:
```
lint → security → dx-standards → architecture → test → security-test
                                                                    ↘
frontend-test ──────────────────────────────────────────────────────→ ci-passed
```

O job `ci-passed` verifica que TODOS os anteriores passaram. Nenhum PR é mergeado sem este gate.

**O que o miniAutoGen tem:** Sem CI visível no repositório.

**Ação sugerida:** Criar `.github/workflows/ci.yml` com pelo menos:
```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: ruff check miniautogen/ tests/
      - run: mypy miniautogen/

  test:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/ --cov=miniautogen --cov-report=json

  arch-check:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - run: python -m miniautogen check-arch  # (após criar o linter)

  ci-passed:
    needs: [lint, test, arch-check]
    runs-on: ubuntu-latest
    steps:
      - run: echo "All gates passed"
```

---

### 2.7 🟢 NICE-TO-HAVE: Memória automatizada (claude-mem pattern)

**O que o noviuz faz:** Plugin `claude-mem` com hooks que automaticamente:
- Registram atividade do agente em CLAUDE.md distribuídos pelo repo
- Persistem contexto ao final de sessão
- Recarregam contexto no início da próxima sessão

**O que o miniAutoGen tem:** Sistema de memória manual com 4 tipos semânticos (user, feedback, project, reference). Mais rico semanticamente, mas requer ação explícita para salvar.

**Insight:** O sistema do miniAutoGen é semanticamente superior (tipos, frontmatter, index). Mas a automação do noviuz garante que a memória é SEMPRE atualizada. O ideal seria combinar:
- Manter o sistema de tipos semânticos do miniAutoGen
- Adicionar hooks de SessionEnd que façam auto-save de decisões da sessão

---

### 2.8 🟢 NICE-TO-HAVE: Git workflow formalizado

**O que o noviuz faz:**
```
feature/*, fix/*, chore/*  →  develop  →  staging  →  main
```
- Naming conventions documentadas
- Semantic commits obrigatórios (`feat(scope):`, `fix(scope):`)
- Hotfixes com backport imediato

**O que o miniAutoGen tem:** Branch `main` sem workflow documentado. Features parecem ir direto para main (`feat/tui-dash` → main).

**Ação sugerida:** Documentar no CLAUDE.md ou criar `CONTRIBUTING.md`:
- Branch naming: `feat/`, `fix/`, `chore/`, `docs/`
- Commit format: `feat(core):`, `fix(runtime):`, `test(policies):`
- Merge strategy: squash ou merge commit

---

## 3. O que o miniAutoGen faz MELHOR

Nem tudo é melhoria do noviuz. Há áreas onde o miniAutoGen está à frente:

### 3.1 Delegação Multi-Modelo
O noviuz usa apenas Claude Code. O miniAutoGen tem GPT-5.2 via Codex MCP com 5 especialistas (Architect, Plan Reviewer, Scope Analyst, Code Reviewer, Security Analyst). Isso dá perspectiva fresca e reduz viés de modelo único.

### 3.2 Ring Teams (Especialização por Domínio)
9 times especializados vs 0 no noviuz. O `ring-dev-team` com ciclo de 6 gates, o `ring-pm-team` com 9 gates de planejamento, e a capacidade de despachar subagentes paralelos são diferenciais significativos.

### 3.3 Skills Processuais (Superpowers)
O noviuz tem slash commands (procedurais — "faça X, Y, Z"). O miniAutoGen tem skills (comportamentais — "pense assim, valide assim, complete assim"). Skills como `systematic-debugging`, `brainstorming`, e `verification-before-completion` governam o *como* o agente trabalha, não apenas *o que* faz.

### 3.4 Memória Semântica
4 tipos de memória (user, feedback, project, reference) vs logs cronológicos. A memória de feedback — que captura tanto correções quanto confirmações — é particularmente valiosa para evitar drift comportamental.

### 3.5 Dúvida Estruturada
O sistema de 5 níveis de resolução antes de perguntar (dispatch context → CLAUDE.md → codebase patterns → best practice → ask) reduz interrupções desnecessárias. O noviuz não tem equivalente.

---

## 4. Matriz de Prioridades

| # | Melhoria | Esforço | Impacto | Prioridade |
|---|----------|---------|---------|------------|
| 2.1 | Sistema de Specs (`.specs/`) | Médio | Alto | 🔴 P0 |
| 2.2 | Linters arquiteturais programáticos | Alto | Alto | 🔴 P0 |
| 2.6 | CI Pipeline | Médio | Alto | 🔴 P0 |
| 2.3 | Hooks de ciclo de vida | Baixo | Médio | 🟡 P1 |
| 2.5 | Whitelist granular de permissões | Baixo | Médio | 🟡 P1 |
| 2.4 | Multi-agent awareness | Médio | Médio | 🟡 P1 |
| 2.8 | Git workflow formalizado | Baixo | Baixo | 🟢 P2 |
| 2.7 | Memória automatizada | Médio | Baixo | 🟢 P2 |

---

## 5. Síntese: O Ambiente Ideal

O ambiente ideal combina:

```
┌─────────────────────────────────────────────────────────────┐
│                    AMBIENTE IDEAL                            │
├──────────────────────┬──────────────────────────────────────┤
│  Do noviuz-app       │  Do miniAutoGen                      │
├──────────────────────┼──────────────────────────────────────┤
│  Spec-kit system     │  Ring teams (9 especializações)      │
│  Linters por AST     │  Delegação multi-modelo (GPT+Claude) │
│  7 hooks lifecycle   │  Skills processuais (Superpowers)    │
│  CI com 7 gates      │  Memória semântica (4 tipos)         │
│  Multi-agent docs    │  Dúvida estruturada (5 níveis)       │
│  Perms granulares    │  3-file rule como gate               │
│  Git workflow formal │  Subagent dispatch paralelo          │
│  Constitution.md     │  Plan mode por padrão                │
└──────────────────────┴──────────────────────────────────────┘
```

O noviuz-app ensina que **enforcement programático > instruções verbais**. Invariantes no CLAUDE.md são sugestões; invariantes no CI são leis.

O miniAutoGen ensina que **processo de pensamento > processo de ação**. Skills que governam *como* o agente raciocina (brainstorming, debugging sistemático, verificação antes de completar) produzem output de qualidade superior a scripts que governam *o que* o agente faz.

A combinação ideal: **pensar como miniAutoGen, enforçar como noviuz**.
