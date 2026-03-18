# Plano Técnico: [Nome da Feature]

| Campo      | Valor       |
|------------|-------------|
| Spec ID    | NNN         |
| Data       | YYYY-MM-DD  |
| Complexidade | Quick / Short / Medium / Large |

---

## Arquitetura Proposta

### Módulos Afetados

| Módulo / Caminho            | Tipo de Alteração       |
|-----------------------------|-------------------------|
| `miniautogen/core/...`      | Novo / Alterado / Nenhum |
| `miniautogen/adapters/...`  | Novo / Alterado / Nenhum |
| `miniautogen/policies/...`  | Novo / Alterado / Nenhum |
| `tests/...`                 | Novo / Alterado         |

### Diagrama (opcional)

```
Componente A -> Componente B -> Componente C
```

---

## Contratos e Interfaces

### Novos Contratos

```python
# Exemplo:
# class NovoProtocol(Protocol):
#     async def metodo(self) -> Resultado: ...
```

### Contratos Alterados

> Liste contratos existentes que serão modificados e o que muda.

---

## Riscos e Mitigações

| Risco                        | Impacto  | Mitigação                      |
|------------------------------|----------|--------------------------------|
| Exemplo: Breaking change API | Alto     | Manter backward compat via alias |

---

## Estimativa de Complexidade

| Aspecto              | Estimativa |
|----------------------|------------|
| Ficheiros novos      |            |
| Ficheiros alterados  |            |
| Testes novos         |            |
| Esforço estimado     | Quick / Short / Medium / Large |

---

## Sequência de Implementação

1. Passo 1 — descrição
2. Passo 2 — descrição
3. Passo 3 — descrição

---

## Notas

> Decisões de design, alternativas consideradas, trade-offs.
