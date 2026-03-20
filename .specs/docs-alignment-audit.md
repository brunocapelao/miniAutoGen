# Auditoria de Alinhamento: Documentacao vs README Estrategico

> **Data:** 2026-03-20
> **Numero real de eventos:** 63 em 13 categorias (verificado no enum `EventType`)
> **Documentos auditados:** 21

---

## Numero Canonico de Eventos

Verificacao no codigo (`miniautogen/core/events/types.py`):
- **63 membros** no enum `EventType`
- **13 categorias**: Run, Component, Tool, Checkpoint, AgenticLoop, Deliberation, Backend, Approval, Effect, Supervision, AgentRuntime, Interceptor, RunState

Todos os docs devem usar **"63+ eventos em 13 categorias"**.

---

## Resumo por Documento

### Totalmente Alinhados (0 fixes)

| Documento | Status |
|-----------|--------|
| `architecture/06-decisoes.md` | Alinhado — usa Engine/Flow/Workspace correctamente |
| `dx-comparison-noviuz.md` | Alinhado — referencias a nivel de codigo, nao conceptual |

### Fixes Menores (1-3 fixes)

| Documento | Fixes Necessarios |
|-----------|-------------------|
| `architecture/07-agent-anatomy.md` | 3x "63" event count (ja correcto, manter) |
| `architecture/08-tech-stack.md` | 1x "47+ em 12 categorias" → "63+ em 13 categorias" |
| `architecture/09-invariantes-SO.md` | 2x "63" event count (ja correcto) + 2x anotar PipelineRunner como "(executor de Flows)" |
| `guides/gemini-cli-gateway.md` | 1x adicionar frase linkando gateway ao conceito de Engine |
| `guides/release-checklist.md` | Expandir scope de testes para incluir `flow` command |

### Fixes Moderados (4-10 fixes)

| Documento | Problema Principal | Fixes |
|-----------|-------------------|-------|
| `architecture/01-contexto.md` | "pipelines" e "backends" como conceito | 3x pipeline→flow, 2x backend→engine |
| `architecture/02-containers.md` | "47+ em 12 categorias" + stores desatualizados | 1x event count, 1x store count (3→5), 2x backend→engine |
| `architecture/03-componentes.md` | Seccao "Motor de pipeline" e legacy | Marcar como legacy, 1x backend→engine |
| `architecture/05-invariantes.md` | Categorias de eventos incompletas | Adicionar Efeitos, Supervisao, Estado na taxonomia |
| `architecture/README.md` | Labels "(Proposto)" desatualizados | 2x remover "(Proposto)", 2x event count |
| `quick-reference.md` | "47+" + "Backend drivers" header | 1x event count, 1x header, verificar rename de services |
| `dx-agent-environment.md` | "47+" + "pipelines" na descricao | 2x event count, 1x pipeline→flow, 1x backend→engine |

### Fixes Pesados (10+ fixes ou reescrita parcial)

| Documento | Problema | Recomendacao |
|-----------|----------|-------------|
| `competitive-landscape.md` | Terminologia toda antiga (AgentDriver, PipelineRunner, backend). "47+" events. Sem DeerFlow/Open SWE/Bit Office. Duplica posicionamento do README. | Reescrita parcial: migrar terminologia, adicionar 3 concorrentes, remover seccoes duplicadas do README |
| `e2e-funcional.md` | 3x "47+" events. "8 categorias". Usa "projecto" extensivamente. | Ja tem disclaimer. Fix: event counts + categorias. Migrar terminologia seria ideal mas disclaimer cobre. |
| `plano-langgraph.md` | 30+ "pipeline", 0 "Flow", 0 "Engine", 0 "Workspace" | Adicionar disclaimer de terminologia (mesmo padrao do e2e-funcional) |
| `agent-frameworks-research-2026.md` | Seccao 7 usa terminologia antiga. Sem link aos pilares/teses. | Reescrita da Seccao 7 com terminologia actual |
| `architecture-retrospective.md` | "47+" events. Terminologia antiga no estado actual (historico OK). Topologia desatualizada (faltam effect engine, supervision). | Atualizar estado actual, manter v0 historico |

---

## Plano de Execucao (por prioridade)

### P0: Event Count Global (15 min)

Search-replace mecanico em todos os docs:
- `47+` → `63+` (onde refere eventos)
- `12 categorias` → `13 categorias` (onde acompanha event count)
- `8 categorias` → `13 categorias` (e2e-funcional)

**Ficheiros:** 02-containers, 05-invariantes (tabelas incompletas), 08-tech-stack, architecture/README, quick-reference, e2e-funcional (x3), dx-agent-environment (x2)

### P1: Terminologia Conceptual nos Docs de Arquitetura (30 min)

Corrigir uso conceptual de "pipeline"→"flow" e "backend"→"engine" nos docs de arquitetura:
- 01-contexto.md (5 fixes)
- 02-containers.md (2 fixes + store count)
- 03-componentes.md (marcar legacy)
- architecture/README.md (remover "(Proposto)")

### P2: competitive-landscape.md (1h)

- Migrar terminologia (AgentDriver→Engine, PipelineRunner→Flow, etc.)
- Adicionar DeerFlow, Open SWE, Bit Office
- Remover seccoes 5 e 7 que duplicam README — linkar
- Atualizar event count e features

### P3: Disclaimers em Docs Pre-Rename (15 min)

Adicionar disclaimer de terminologia a:
- plano-langgraph.md
- architecture-retrospective.md (seccoes de estado actual)

### P4: Reescrita de Seccoes Especificas (30 min)

- agent-frameworks-research-2026.md Seccao 7
- architecture-retrospective.md topologia actual
- 05-invariantes.md tabelas de eventos (adicionar categorias em falta)

---

## Regra de Consistencia

Apos as correcoes, a hierarquia de documentos deve ser:

```
README.md (ESTRATEGICO)
  └── WHY + WHAT — pilares, modelo mental, posicionamento, validacao de mercado
       │
       ├── competitive-landscape.md (DADOS COMPETITIVOS)
       │     └── Analise raw de concorrentes — sem duplicar posicionamento do README
       │
       ├── architecture/ (HOW)
       │     └── Implementacao — como os conceitos do README se materializam em codigo
       │
       └── guides/ + specs/ (OPERACIONAL)
             └── Como usar — tutoriais, checklists, specs de features
```

**Regra:** Se algo esta no README, os outros docs REFERENCIAM, nao duplicam.
