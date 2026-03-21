# Especificação: TUI UX Sprint 1 — Fixes Críticos (P0)

| Campo      | Valor                          |
|------------|--------------------------------|
| Data       | 2026-03-20                     |
| Autor      | Claude (Arquiteto)             |
| Status     | Aprovada                       |
| Spec ID    | 009                            |

---

## Contrato de Prompt (G/C/FC)

### 🎯 Goal (Objetivo)

> Corrigir os 8 itens críticos (P0) de usabilidade da TUI que bloqueiam o ciclo de vida básico. Após esta sprint, o usuário consegue usar o Dash como interface standalone para init → configure → run sem encontrar stubs, deleções acidentais, ou telas vazias sem orientação.

### 🚧 Constraint (Restrição)

> 1. Zero mudanças no core/SDK — todas as alterações são na camada TUI.
> 2. Reutilizar widgets e padrões existentes (EmptyState, CreateFormScreen callback pattern).
> 3. Manter 146+ testes TUI passando sem regressões.
> 4. Seguir padrões Textual existentes no codebase.

### 🛑 Failure Condition (Condição de Falha)

> 1. Pressionar `d` em qualquer view CRUD deleta sem pedir confirmação.
> 2. Search `/` continua visível no footer mas não funciona.
> 3. Criar flow pela TUI não permite selecionar participants.
> 4. Tecla `r` em PipelinesView executa pipeline em vez de refresh.
> 5. AgentCardScreen mostra botões [h]istory que não funcionam.
> 6. DataTables vazias não mostram mensagem de orientação.
> 7. Workspace recém-criado não mostra guia de próximo passo.

---

## Itens

### A.1 — ConfirmDialog para deleção

**Criar:** `miniautogen/tui/screens/confirm_dialog.py`

```python
from textual.screen import ModalScreen
from textual.widgets import Static, Button
from textual.containers import Vertical, Horizontal

class ConfirmDialog(ModalScreen[bool]):
    """Modal de confirmação para ações destrutivas."""

    DEFAULT_CSS = \"\"\"
    ConfirmDialog {
        align: center middle;
    }
    ConfirmDialog > Vertical {
        width: 60;
        height: auto;
        max-height: 15;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    \"\"\"

    def __init__(self, message: str, title: str = "Confirmar") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self):
        with Vertical():
            yield Static(f"[bold]{self._title}[/bold]\\n\\n{self._message}")
            with Horizontal():
                yield Button("Cancelar", variant="default", id="cancel")
                yield Button("Confirmar", variant="error", id="confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")
```

**Modificar:** `views/agents.py`, `views/engines.py`, `views/pipelines.py`

Em cada `action_delete_*()`, substituir chamada direta por:
```python
def action_delete_agent(self) -> None:
    name = self._get_selected_name()
    if not name:
        return
    self.app.push_screen(
        ConfirmDialog(f"Excluir agente '{name}'? Esta ação não pode ser desfeita."),
        callback=lambda confirmed: self._do_delete_agent(name) if confirmed else None,
    )
```

### A.2 — Esconder Search stub

**Modificar:** `tui/app.py`

Alterar binding de search:
```python
# ANTES:
Binding("slash", "search", "Search", show=True),
# DEPOIS:
Binding("slash", "search", "Search", show=False),
```

### A.3 — Form de Flow com participants e leader

**Modificar:** `tui/screens/create_form.py`

Adicionar campos ao `_PIPELINE_FIELDS`:
```python
_PIPELINE_FIELDS = [
    {"name": "name", "label": "Flow Name", "type": "input", "required": True},
    {"name": "mode", "label": "Mode", "type": "select",
     "options": ["workflow", "deliberation", "loop", "composite"], "default": "workflow"},
    {"name": "participants", "label": "Participants (comma-separated agent names)",
     "type": "input", "required": True, "placeholder": "agent1, agent2"},
    {"name": "leader", "label": "Leader (for deliberation/loop)",
     "type": "input", "placeholder": "agent_name"},
    {"name": "target", "label": "Target callable (optional)",
     "type": "input", "placeholder": "module.path:callable"},
]
```

**Nota:** Usar input com comma-separated por simplicidade (MVP). Multi-select widget pode vir no Sprint 3.

**Modificar:** `tui/data_provider.py` — `create_pipeline()` deve parsear `participants` string em lista e passar `leader`.

### A.4 — Tecla `r` consistente

**Modificar:** `tui/views/pipelines.py`

```python
# ANTES:
Binding("r", "run_pipeline", "Run", show=True),
# DEPOIS:
Binding("x", "run_pipeline", "Run", show=True),
Binding("r", "refresh_pipelines", "Refresh", show=True),
```

Renomear `action_refresh_pipelines` se necessário, adicionar método se não existe.

### A.5 — AgentCardScreen stubs

**Modificar:** `tui/screens/agent_card.py`

1. Wire `[e]dit` → `self.app.push_screen(CreateFormScreen("agent", edit_name=self._agent_id))`
2. Remover binding `[h]istory` (não implementado)

### A.6 — Empty states nas DataTables

**Modificar:** `views/agents.py`, `views/engines.py`, `views/pipelines.py`

Em cada `_refresh_table()`, após popular a tabela, se vazia:
```python
if self._table.row_count == 0:
    self._empty_msg.update("Nenhum agente ainda. Pressione [bold]n[/bold] para criar o primeiro.")
    self._empty_msg.display = True
else:
    self._empty_msg.display = False
```

Adicionar `Static` widget (`_empty_msg`) no `compose()` de cada view, inicialmente `display = False`.

### A.7 — Onboarding no WorkPanel

**Modificar:** `tui/widgets/work_panel.py`

Quando `InteractionLog` está vazio e nenhum run ativo, mostrar guia contextual:
```python
def _get_onboarding_message(self) -> str:
    if not self.app._provider:
        return "Crie um workspace para começar."
    if not self.app._provider.get_engines():
        return "Configure um engine. Pressione [:] e digite 'engines'."
    if not self.app._provider.get_agents():
        return "Crie seu primeiro agente. Pressione [:] e digite 'agents'."
    if not self.app._provider.get_pipelines():
        return "Defina um flow. Pressione [:] e digite 'pipelines'."
    return "Sua equipe está pronta! Vá em [:] > 'pipelines' e pressione [bold]x[/bold] para executar."
```

### A.8 — ApprovalBanner focus

**Modificar:** `tui/widgets/approval_banner.py`

```python
def on_mount(self) -> None:
    self.focus()
    self.scroll_visible()
```

---

## Critérios de Aceitação

- [ ] CA-1: `d` em qualquer view CRUD abre ConfirmDialog antes de deletar
- [ ] CA-2: Search `/` não aparece no footer
- [ ] CA-3: Criar flow pela TUI permite definir participants e leader
- [ ] CA-4: `r` em PipelinesView faz Refresh, `x` executa
- [ ] CA-5: AgentCardScreen [e]dit abre form de edição, [h]istory removido
- [ ] CA-6: DataTables vazias mostram mensagem contextual
- [ ] CA-7: WorkPanel mostra guia progressivo quando vazio
- [ ] CA-8: ApprovalBanner captura focus ao aparecer
- [ ] CA-9: 146+ testes TUI passam sem regressões
- [ ] CA-10: Novos testes para ConfirmDialog e empty states

---

## Invariantes Afetadas

- [ ] **Isolamento de Adapters** — N/A (só TUI)
- [ ] **Microkernel / PipelineRunner** — N/A (só TUI)
- [ ] **Assincronismo Canônico (AnyIO)** — N/A (Textual tem seu próprio event loop)
- [ ] **Policies Event-Driven** — N/A (só TUI)

---

## Dependências

| Dependência | Tipo | Estado |
|---|---|---|
| Textual >= 1.0.0 | Externa | Instalada (v8.1.1) |
| TUI widgets existentes | Interna | Prontos |
| CreateFormScreen | Interna | Pronto (reutilizar) |

---

## Referências

- Plano completo: `docs/pt/guides/tui-ux-improvements.md`
- Spec UX: `docs/pt/guides/tui-ux-spec.md`
