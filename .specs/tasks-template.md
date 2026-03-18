# Tarefas: [Nome da Feature]

| Campo      | Valor       |
|------------|-------------|
| Spec ID    | NNN         |
| Data       | YYYY-MM-DD  |
| Total      | X tarefas   |

---

## Legenda

- **Status:** TODO / IN_PROGRESS / DONE / BLOCKED
- **P:** Paralelizável (sim/não) — pode ser feita em paralelo com outras tarefas marcadas P
- **Deps:** IDs de tarefas das quais esta depende

---

## Tarefas

### T001 — [Título da tarefa]

| Campo    | Valor     |
|----------|-----------|
| Status   | TODO      |
| P        | sim / não |
| Deps     | —         |

**Descrição:** O que fazer.

**Critério de conclusão:**
- [ ] Critério específico e verificável

---

### T002 — [Título da tarefa]

| Campo    | Valor     |
|----------|-----------|
| Status   | TODO      |
| P        | sim / não |
| Deps     | T001      |

**Descrição:** O que fazer.

**Critério de conclusão:**
- [ ] Critério específico e verificável

---

### T003 — [Título da tarefa]

| Campo    | Valor     |
|----------|-----------|
| Status   | TODO      |
| P        | sim / não |
| Deps     | T001      |

**Descrição:** O que fazer.

**Critério de conclusão:**
- [ ] Critério específico e verificável

---

## Grafo de Dependências

```
T001 ──┬── T002
       └── T003
```

---

## Resumo

| Paralelizáveis | Sequenciais | Bloqueadas | Total |
|----------------|-------------|------------|-------|
| X              | X           | 0          | X     |
