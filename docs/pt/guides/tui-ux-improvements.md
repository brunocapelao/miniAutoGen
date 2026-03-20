# MiniAutoGen Dash -- Plano de Melhorias UX

> **Versao:** 1.0.0 | **Data:** 2026-03-20
> **Baseado em:** Auditoria completa da spec UX (`tui-ux-spec.md`) + codigo-fonte de 30 arquivos em `miniautogen/tui/`
> **Objetivo:** Transformar o Dash em interface standalone que cobre o ciclo de vida completo da orquestracao multi-agente.

---

## Sumario Executivo

A TUI atual possui uma base solida: arquitetura de 3 camadas, 7 estados com simbolos acessiveis, 4 temas semanticos, streaming de eventos em tempo real e 146 testes. Porem, a auditoria identificou **32 itens acionaveis** distribuidos em 5 categorias, sendo 8 criticos (P0), 10 de alta prioridade (P1), 8 medios (P2) e 6 de baixa prioridade (P3).

Os problemas mais graves sao: exclusao sem confirmacao, funcoes anunciadas mas nao-funcionais (search `/`, stubs em AgentCardScreen), formulario de flow incompleto (sem `participants`/`leader`), e ausencia total de paridade com CLI para `check` e `session`.

---

## Legenda

| Simbolo | Significado |
|---------|-------------|
| **P0** | Critico -- bloqueia ciclo de vida basico |
| **P1** | Alta prioridade -- lacuna funcional significativa |
| **P2** | Media prioridade -- qualidade da interacao |
| **P3** | Baixa prioridade -- polish e delight |
| **S** | Esforco pequeno (< 2h) |
| **M** | Esforco medio (2-8h) |
| **L** | Esforco grande (> 8h) |

---

## A. Correcoes Criticas de Usabilidade (bloqueiam ciclo de vida)

### A.1 Exclusao sem confirmacao em todas as views CRUD

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforco** | M |
| **Impacto** | Exclusao acidental de agentes, engines ou flows sem possibilidade de desfazer. Um unico toque em `d` apaga o recurso permanentemente. |

**Problema:** `action_delete_agent()`, `action_delete_engine()` e `action_delete_pipeline()` executam exclusao imediata. Nenhuma das 3 views pede confirmacao. O YAML e reescrito instantaneamente.

**Evidencia no codigo:**
- `views/agents.py:84-97` -- `action_delete_agent()` chama `provider.delete_agent(name)` diretamente
- `views/engines.py:81-94` -- identico
- `views/pipelines.py:85-98` -- identico

**Sugestao de implementacao:**
1. Criar widget `ConfirmDialog(ModalScreen[bool])` em `tui/screens/confirm_dialog.py`
2. Conteudo: "Excluir '{name}'? Esta acao nao pode ser desfeita." + botoes [Confirm] / [Cancel]
3. Aplicar em todas as 3 actions de delete via callback pattern ja usado em `_on_form_result`

**Arquivos a modificar:**
- Criar: `tui/screens/confirm_dialog.py`
- Modificar: `tui/views/agents.py`, `tui/views/engines.py`, `tui/views/pipelines.py`

---

### A.2 Search (`/`) anunciado no Footer mas nao-funcional

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforco** | S |
| **Impacto** | Quebra de confianca -- usuario ve "Search" no footer, pressiona `/`, nada acontece. Viola heuristica de Nielsen #1 (visibilidade do status). |

**Problema:** Em `app.py:64`, o binding `slash` esta com `show=True` mas `action_search()` (linha 224) e corpo vazio (`pass`).

**Sugestao de implementacao (correcao imediata):**
- Alterar para `show=False` ate que busca seja implementada:
  ```python
  Binding("slash", "search", "Search", show=False),
  ```
- Alternativa (melhor UX): implementar busca basica que foca o campo de filtro na view ativa

**Arquivos a modificar:**
- `tui/app.py` linhas 64, 224-225

---

### A.3 Formulario de Flow sem campo `participants` e `leader`

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforco** | M |
| **Impacto** | Impossivel criar um flow funcional pela TUI -- flows sem participantes nao executam. O usuario e forcado a editar YAML manualmente. |

**Problema:** `_PIPELINE_FIELDS` em `screens/create_form.py:33-37` define apenas `name`, `mode` e `target`. O `DashDataProvider.create_pipeline()` aceita `participants` e `leader` mas a TUI nao expoe esses campos.

**Sugestao de implementacao:**
1. Adicionar novo tipo de campo `multi_agent_select` ao `CreateFormScreen`
2. Listar agentes disponiveis como checkboxes (ou SelectionList do Textual)
3. Adicionar campo `leader` como Select dinamico (populado com agentes selecionados)

```python
_PIPELINE_FIELDS = [
    {"name": "name", "label": "Flow Name", "type": "input", "required": True},
    {"name": "mode", "label": "Mode", "type": "select",
     "options": ["workflow", "deliberation", "loop", "composite"], "default": "workflow"},
    {"name": "participants", "label": "Participants", "type": "multi_agent_select", "required": True},
    {"name": "leader", "label": "Leader (optional)", "type": "agent_select"},
    {"name": "target", "label": "Target (optional)", "type": "input", "placeholder": "module.path:callable"},
]
```

**Arquivos a modificar:**
- `tui/screens/create_form.py` -- adicionar `_PIPELINE_FIELDS` e logica de `multi_agent_select`

---

### A.4 Inconsistencia da tecla `r` (Refresh vs Run)

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforco** | S |
| **Impacto** | Risco de execucao acidental de pipeline. Usuario acostumado com `r = Refresh` em AgentsView/EnginesView pode executar pipeline inadvertidamente em PipelinesView. |

**Problema:** Em `views/pipelines.py:21`, `r` esta mapeado para `action_run_pipeline`. Nas outras views CRUD, `r` e sempre Refresh.

**Sugestao de implementacao:**
- Remapear PipelinesView: `x` ou `Enter` para Run, `r` para Refresh
- Remover binding `F5` que se torna redundante

```python
BINDINGS = [
    Binding("escape", "pop_screen", "Back", show=True),
    Binding("n", "new_pipeline", "New", show=True),
    Binding("e", "edit_pipeline", "Edit", show=True),
    Binding("d", "delete_pipeline", "Delete", show=True),
    Binding("x", "run_pipeline", "Run", show=True),
    Binding("r", "refresh_pipelines", "Refresh", show=True),
]
```

**Arquivos a modificar:**
- `tui/views/pipelines.py` linhas 16-23

---

### A.5 Stubs visiveis na AgentCardScreen (`[e]dit` e `[h]istory`)

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforco** | M |
| **Impacto** | Botoes visiveis que exibem "not yet implemented" quebram expectativa. O usuario ve "[e]dit [h]istory [Esc] close" e espera funcionalidade. |

**Problema:** `screens/agent_card.py:166-172` -- ambas acoes sao stubs com `self.notify("... not yet implemented")`.

**Sugestao de implementacao:**
- **[e]dit:** Implementar abrindo `CreateFormScreen(resource_type="agent", edit_name=self.agent_id)` e dismiss do card apos edicao. Ja existe a infraestrutura completa.
- **[h]istory:** Se nao sera implementado agora, remover do hint text e dos bindings. Manter apenas `[e]dit [Esc] close`.

**Arquivos a modificar:**
- `tui/screens/agent_card.py` linhas 66-68, 161-172

---

### A.6 Estado vazio sem orientacao nas DataTables

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforco** | S |
| **Impacto** | Primeiro contato frustrante. Usuario novo ve tabelas vazias sem nenhuma indicacao de proximo passo. O widget `EmptyState` existe mas nao e usado nas views CRUD. |

**Problema:** `views/agents.py:39-50` -- `_refresh_table()` apenas limpa a tabela quando nao ha dados. Nao mostra mensagem orientadora. Identico em `engines.py` e `pipelines.py`.

**Sugestao de implementacao:**
1. Verificar `table.row_count == 0` apos populate
2. Mostrar `Static` com mensagem contextual: "Nenhum agente ainda. Pressione [bold]n[/bold] para criar o primeiro."
3. Ou usar o widget `EmptyState` ja existente em `widgets/empty_state.py`

**Arquivos a modificar:**
- `tui/views/agents.py` -- `_refresh_table()`
- `tui/views/engines.py` -- `_refresh_table()`
- `tui/views/pipelines.py` -- `_refresh_table()`

---

### A.7 Workspace vazio sem guia de primeiro uso

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforco** | M |
| **Impacto** | Apos init wizard, o usuario cai no workspace com InteractionLog vazio e sidebar potencialmente vazia. Zero orientacao sobre proximo passo. |

**Problema:** O `WorkPanel` monta com `InteractionLog` vazio e `ProgressBar` em "Ready". Nao ha onboarding. O widget `EmptyState` existe mas nao esta montado no fluxo principal.

**Sugestao de implementacao:**
1. Quando `InteractionLog.entry_count == 0` e sidebar vazia, montar `EmptyState` no WorkPanel
2. Personalizar mensagem baseada no estado do projeto:
   - Sem engines: "Configure um engine primeiro. Pressione [:] e digite 'engines'."
   - Sem agentes: "Crie seu primeiro agente. Pressione [:] e digite 'agents'."
   - Sem flows: "Defina um flow para sua equipe. Pressione [:] e digite 'pipelines'."
   - Tudo pronto: "Sua equipe esta pronta. Execute um flow via [:] > 'pipelines' > [r]un."

**Arquivos a modificar:**
- `tui/widgets/work_panel.py` -- condicional no `compose()`
- `tui/widgets/empty_state.py` -- adicionar variantes de mensagem

---

### A.8 Focus management no ApprovalBanner

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforco** | S |
| **Impacto** | Quando um ApprovalBanner aparece inline no InteractionLog, o foco permanece no log. O usuario pode nao perceber que aprovacao e necessaria, especialmente se nao estiver olhando a tela (nenhum focus trap). |

**Problema:** `widgets/approval_banner.py` define handlers `key_a()` e `key_d()` mas nao captura foco automaticamente. O banner aparece no scroll do RichLog, podendo ficar fora da area visivel.

**Sugestao de implementacao:**
1. Ao criar ApprovalBanner, chamar `self.focus()` no `on_mount()`
2. Garantir scroll ate o banner: `self.scroll_visible()`
3. Considerar mover o banner para fora do RichLog (widget separado docked no bottom do WorkPanel) para visibilidade garantida

**Arquivos a modificar:**
- `tui/widgets/approval_banner.py` -- adicionar `on_mount` com focus
- `tui/widgets/work_panel.py` -- considerar area dedicada para banners

---

## B. Completude de Fluxo (lacunas no ciclo de vida)

### B.1 Ausencia de view `check` (validacao de projeto)

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforco** | M |
| **Impacto** | CLI possui `miniautogen check` que valida engines, agentes e flows. TUI nao tem equivalente. Usuario nao consegue diagnosticar problemas de configuracao pela interface. |

**Problema:** O servico `cli/services/check_project.py` existe mas nao ha view correspondente. O `SCREENS` dict em `app.py:48-55` nao inclui `check`.

**Sugestao de implementacao:**
1. Criar `tui/views/check.py` como `CheckView(SecondaryView)`
2. Executar `check_project()` e exibir resultado em formato de checklist visual
3. Status por item: verde (ok), amarelo (warning), vermelho (erro)
4. Registrar como `:check` no SCREENS dict

**Arquivos a criar:**
- `tui/views/check.py`

**Arquivos a modificar:**
- `tui/app.py` -- adicionar ao SCREENS

---

### B.2 Ausencia de view `session` (gerenciamento de sessoes)

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforco** | M |
| **Impacto** | CLI possui `miniautogen session` com CRUD de sessoes. TUI nao expoe. Impossivel gerenciar memoria persistente de agentes pela interface. |

**Problema:** `cli/services/session_ops.py` existe mas nao tem view na TUI.

**Sugestao de implementacao:**
1. Criar `tui/views/sessions.py` como `SessionsView(SecondaryView)` com DataTable
2. Colunas: Session ID, Agent, Created, Messages, Status
3. Bindings: `n` new, `d` delete, `Enter` detail (mostrar mensagens), `r` refresh
4. Registrar como `:sessions` no SCREENS dict

**Arquivos a criar:**
- `tui/views/sessions.py`

**Arquivos a modificar:**
- `tui/app.py` -- adicionar ao SCREENS

---

### B.3 Server start/stop sem bindings visiveis

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforco** | S |
| **Impacto** | Acoes de servidor existem (`action_server_start`, `action_server_stop` em app.py:237-253) mas sao invisiveis. Nenhum binding de teclado, nenhuma entrada no Footer. O usuario precisa saber da command palette. |

**Problema:** Acoes de servidor estao implementadas mas sem rota de acesso visivel.

**Sugestao de implementacao:**
Opcao A (simples): Adicionar binding `S` (maiusculo) como toggle:
```python
Binding("S", "toggle_server", "Server", show=True),
```

Opcao B (melhor): Criar view `:server` com status detalhado, logs, config de porta, toggle start/stop.

**Arquivos a modificar:**
- `tui/app.py` -- adicionar binding e action

---

### B.4 Historico de runs apenas em memoria

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforco** | M |
| **Impacto** | `DashDataProvider._run_history` e uma lista em memoria. Ao fechar o Dash, todo historico e perdido. Impossivel comparar runs entre sessoes. |

**Problema:** `data_provider.py:62` -- `self._run_history: list[dict] = []`. `get_runs()` retorna apenas essa lista.

**Sugestao de implementacao:**
1. Persistir em arquivo JSON em `.miniautogen/run_history.json` no project root
2. Carregar ao inicializar o provider, salvar apos cada run
3. Limitar a ultimas 100 runs para evitar crescimento ilimitado

**Arquivos a modificar:**
- `tui/data_provider.py` -- `get_runs()`, `run_pipeline()`, `__init__()`

---

### B.5 Eventos nao persistidos entre sessoes

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforco** | M |
| **Impacto** | `data_provider.get_events()` retorna lista vazia (linha 164-170). Eventos so existem durante streaming ao vivo. Impossivel debugar runs passados. |

**Problema:** Eventos sao streamados pelo `TuiEventSink` e renderizados ao vivo no `InteractionLog`, mas nunca persistidos. A `EventsView` depende de `provider.get_events()` que e hardcoded para retornar `[]`.

**Sugestao de implementacao:**
1. Implementar `TuiEventSink.persist_event()` que grava em `.miniautogen/events/`
2. `get_events()` le do disco, com filtro por run_id
3. EventsView carrega eventos persistidos + ao vivo

**Arquivos a modificar:**
- `tui/data_provider.py` -- `get_events()`
- `tui/event_sink.py` -- persistencia opcional

---

### B.6 Ausencia de input para pipeline (prompt do usuario)

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforco** | S |
| **Impacto** | O `provider.run_pipeline()` aceita `pipeline_input` (linha 300) mas a UI de `PipelinesView.action_run_pipeline()` nao pede input ao usuario. Flows que dependem de input inicial falham ou usam valor vazio. |

**Problema:** `views/pipelines.py:100-130` -- `action_run_pipeline()` nao coleta input.

**Sugestao de implementacao:**
1. Ao pressionar Run, abrir um pequeno modal com campo de input: "Prompt para o flow (opcional):"
2. Passar o valor para `provider.run_pipeline(name, pipeline_input=user_input)`

**Arquivos a modificar:**
- `tui/views/pipelines.py` -- `action_run_pipeline()`
- Possivelmente criar: `tui/screens/run_input.py`

---

### B.7 Nenhuma forma de cancelar pipeline em execucao

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforco** | M |
| **Impacto** | Uma vez iniciado, o pipeline roda ate completar ou falhar. Nenhum botao de cancelamento. O usuario so pode fechar o Dash inteiro. |

**Problema:** `views/pipelines.py:112-130` usa `app.run_worker(_run(), exclusive=False)` sem guardar referencia ao worker. Nao ha action de cancelamento.

**Sugestao de implementacao:**
1. Guardar referencia ao worker: `self._active_worker = self.app.run_worker(...)`
2. Adicionar binding `c` para cancel quando ha pipeline ativo
3. `action_cancel_pipeline()` chama `self._active_worker.cancel()`
4. Exibir estado "Cancelling..." no InteractionLog

**Arquivos a modificar:**
- `tui/views/pipelines.py` -- `action_run_pipeline()`, novo `action_cancel_pipeline()`
- `tui/app.py` -- binding condicional

---

### B.8 `flow_ops.py` nao integrado ao data_provider

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforco** | S |
| **Impacto** | O CLI migrou de "pipeline" para "flow" (commits recentes: `dacf7f0`, `b51b0b9`, `3e3a859`). O `data_provider.py` ainda importa de `pipeline_ops` (linhas 35-40) mas `flow_ops.py` existe no CLI services. A TUI pode estar desalinhada com a terminologia nova. |

**Problema:** Desalinhamento terminologico entre CLI (que ja usa "flow") e TUI (que ainda usa "pipeline" em todo lugar).

**Sugestao de implementacao:**
1. Verificar se `flow_ops` e wrapper ou substituto de `pipeline_ops`
2. Atualizar labels na TUI: "Pipelines" -> "Flows" (ou manter backward compat)
3. Atualizar SCREENS key: `"flows"` (manter `"pipelines"` como alias)

**Arquivos a modificar:**
- `tui/data_provider.py` -- imports
- `tui/views/pipelines.py` -- labels e VIEW_TITLE
- `tui/app.py` -- SCREENS keys

---

## C. Qualidade da Interacao (polish e delight)

### C.1 `action_fullscreen()` nao e toggle

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforco** | S |
| **Impacto** | `f` esconde a sidebar mas nao a restaura. Usuario desorientado precisa descobrir `t` para voltar. |

**Problema:** `app.py:208-214` -- `action_fullscreen()` faz `sidebar.display = False` incondicionalmente.

**Sugestao de implementacao:**
```python
def action_fullscreen(self) -> None:
    try:
        sidebar = self.query_one(TeamSidebar)
        sidebar.display = not sidebar.display
    except Exception:
        pass
```
Ou: unificar com `action_toggle_sidebar()` e remover duplicacao.

**Arquivos a modificar:**
- `tui/app.py` linhas 208-214

---

### C.2 Help (`?`) mostra apenas toast generico

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforco** | M |
| **Impacto** | `action_help()` exibe um notify de 1 linha: "Press : for commands, / to search". Insuficiente. O usuario precisa de um mapa de atalhos completo. |

**Problema:** `app.py:200-202` -- help e um toast efemero.

**Sugestao de implementacao:**
1. Criar `HelpScreen(ModalScreen)` com listagem completa de bindings por contexto
2. Organizar em secoes: Global, CRUD Views, Agent Detail, During Execution
3. Acessivel via `?` em qualquer tela

**Arquivos a criar:**
- `tui/screens/help_screen.py`

**Arquivos a modificar:**
- `tui/app.py` -- `action_help()`

---

### C.3 RunsView detail mostra apenas toast

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforco** | M |
| **Impacto** | `action_show_detail()` em `views/runs.py:59-65` exibe apenas `notify(f"Run: {id} | Status: {status}")`. Nenhum detalhe real: sem eventos, sem output, sem duracao expandida. |

**Sugestao de implementacao:**
1. Criar `RunDetailScreen(ModalScreen)` exibindo:
   - Run ID completo, pipeline name, status com cor
   - Timeline de eventos do run
   - Output/resultado
   - Duracao, timestamp inicio/fim
2. Reusar a tabela de EventsView filtrada por `run_id`

**Arquivos a criar:**
- `tui/screens/run_detail.py`

**Arquivos a modificar:**
- `tui/views/runs.py` -- `action_show_detail()`

---

### C.4 Feedback insuficiente durante execucao de pipeline

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforco** | M |
| **Impacto** | Ao iniciar pipeline, o unico feedback e `notify("Starting pipeline...")`. A ProgressBar nao e atualizada (permanece em "Ready"). O usuario nao sabe se algo esta acontecendo ate que eventos comecem a fluir. |

**Problema:** `views/pipelines.py:110` posta notify mas nao atualiza o ProgressBar no WorkPanel. `WorkPanel.update_progress()` existe mas nunca e chamado durante execucao.

**Sugestao de implementacao:**
1. No handler `on_tui_event()` do App, interceptar `COMPONENT_STARTED` e atualizar ProgressBar
2. Extrair `step_number` e `total_steps` do payload do evento
3. Exibir spinner/loading indicator enquanto aguarda primeiro evento

**Arquivos a modificar:**
- `tui/app.py` -- `on_tui_event()`
- `tui/widgets/work_panel.py` -- integrar updates de progresso

---

### C.5 AgentCard na sidebar nao e clicavel via teclado

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforco** | S |
| **Impacto** | AgentCards tem `:hover` CSS mas nao sao focaveis nem ativaveis por teclado. Nao ha como abrir o `AgentCardScreen` sem mouse. |

**Problema:** `widgets/agent_card.py` -- nao implementa `can_focus = True` nem handlers de Enter/click.

**Sugestao de implementacao:**
1. Adicionar `can_focus = True` ao AgentCard
2. Implementar `action_activate()` ou `on_click()` que abre `AgentCardScreen`
3. Adicionar handler `key_enter()` para equivalencia teclado

```python
class AgentCard(Widget):
    can_focus = True

    def on_click(self) -> None:
        from miniautogen.tui.screens.agent_card import AgentCardScreen
        self.app.push_screen(AgentCardScreen(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            role=self.role,
        ))
```

**Arquivos a modificar:**
- `tui/widgets/agent_card.py`

---

### C.6 Validacao de formularios apenas por presenca

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforco** | S |
| **Impacto** | `CreateFormScreen._do_save()` verifica apenas se campo required esta presente. Nao valida formato (ex: nome com espacos, endpoint como URL valida, model existente). |

**Problema:** `screens/create_form.py:188-192` -- validacao e `field["name"] not in values`.

**Sugestao de implementacao:**
1. Adicionar `validators` opcional ao field definition:
   - `name`: regex `^[a-z][a-z0-9_-]*$` (sem espacos)
   - `endpoint`: validacao basica de URL
   - `api_key_env`: apenas alfanumerico + underscore
2. Exibir mensagem especifica por tipo de erro

**Arquivos a modificar:**
- `tui/screens/create_form.py` -- `_do_save()`, field definitions

---

### C.7 Exceptions silenciadas com `pass` em 15+ locais

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforco** | M |
| **Impacto** | Padroes `try/except: pass` em `app.py`, `team_sidebar.py`, `interaction_log.py`, `work_panel.py` e `workspace.py` escondem erros reais. Debugging dificultado. |

**Locais identificados:**
- `app.py`: linhas 129, 147, 167, 177, 198, 213, 222
- `team_sidebar.py`: linhas 74, 83
- `interaction_log.py`: linhas 104, 128, 148, 168
- `work_panel.py`: linha 64
- `workspace.py`: linhas 73, 89, 95

**Sugestao de implementacao:**
1. Substituir `pass` por logging: `import logging; logger.debug("Widget not mounted", exc_info=True)`
2. Manter silenciamento apenas para `NoMatches` (widget nao montado), logar tudo mais
3. Considerar verificar `self.is_mounted` antes de queries

**Arquivos a modificar:**
- Todos os listados acima

---

### C.8 HintBar existente mas nao integrada ao fluxo principal

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforco** | S |
| **Impacto** | `widgets/hint_bar.py` define contextos (workspace, agent_detail, approval, pipeline) e hints contextuais. Mas o widget nao e montado em nenhuma tela ativa. |

**Problema:** `HintBar` esta definido, tem CSS no `dash.tcss:205-211`, mas nao e instanciado em `app.py:compose()` nem em `workspace.py:compose()`.

**Sugestao de implementacao:**
1. Montar `HintBar()` entre `WorkPanel` e `Footer` no `app.py:compose()`
2. Atualizar contexto baseado na tela ativa (subscriber de `screen_changed`)

**Arquivos a modificar:**
- `tui/app.py` -- `compose()`

---

## D. Melhorias de Arquitetura de Informacao

### D.1 Command palette como unica via de navegacao

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforco** | M |
| **Impacto** | As 6 views (agents, engines, pipelines, runs, events, config) sao acessiveis APENAS via command palette (`:nome`). Nenhum menu, nenhum atalho numerico, nenhuma barra de navegacao. Problema de discoverability grave para novos usuarios. |

**Sugestao de implementacao:**
Opcao A: Adicionar bindings numericos globais:
```python
Binding("1", "push_screen('agents')", "Agents", show=True),
Binding("2", "push_screen('pipelines')", "Flows", show=True),
Binding("3", "push_screen('engines')", "Engines", show=True),
Binding("4", "push_screen('runs')", "Runs", show=True),
Binding("5", "push_screen('events')", "Events", show=True),
```

Opcao B (melhor): Criar `NavigationBar` widget docked no top com tabs clicaveis: `[Workspace] [Agents] [Flows] [Engines] [Runs] [Events] [Config]`

**Arquivos a modificar:**
- `tui/app.py` -- bindings ou novo widget
- Possivelmente criar: `tui/widgets/nav_bar.py`

---

### D.2 Theme switcher ausente

| Campo | Valor |
|-------|-------|
| **Prioridade** | P3 |
| **Esforco** | M |
| **Impacto** | 4 temas estao definidos em `themes.py` mas nao ha como alternar. O `DashTheme` nao e aplicado em runtime -- os tokens vem do CSS estatico do Textual. |

**Problema:** `themes.py` define `THEMES` dict com 4 temas mas a `MiniAutoGenDash` nao os utiliza para alterar o CSS em runtime.

**Sugestao de implementacao:**
1. Usar o sistema de themes do Textual: `self.theme = "catppuccin"`
2. Registrar temas via `App.register_theme()` convertendo `DashTheme` tokens
3. Adicionar action: `action_cycle_theme()` com binding `T` (maiusculo)

**Arquivos a modificar:**
- `tui/app.py` -- registro de temas, binding `T`
- `tui/themes.py` -- converter para formato Textual Theme

---

### D.3 Sidebar nao distingue modo compacto (6 colunas)

| Campo | Valor |
|-------|-------|
| **Prioridade** | P3 |
| **Esforco** | S |
| **Impacto** | No modo compacto (100-119 cols), sidebar tem 6 colunas mas renderiza `simbolo + nome + [role]` que trunca ilegivel. |

**Problema:** `app.py:163` seta `width = "6"` mas `AgentCard` nao tem modo compacto.

**Sugestao de implementacao:**
1. Adicionar propriedade `compact: reactive[bool]` ao AgentCard
2. No modo compacto, renderizar apenas `simbolo` (1 char)
3. `TeamSidebar` propaga modo compacto aos cards quando width < 10

**Arquivos a modificar:**
- `tui/widgets/agent_card.py` -- modo compacto
- `tui/widgets/team_sidebar.py` -- propagacao

---

### D.4 PipelineTabs widget existente mas nao integrado

| Campo | Valor |
|-------|-------|
| **Prioridade** | P3 |
| **Esforco** | M |
| **Impacto** | `widgets/pipeline_tabs.py` esta implementado com add/remove/switch/status update mas nao aparece na composicao de nenhuma tela. O `WorkspaceScreen` importa mas nao monta. |

**Sugestao de implementacao:**
1. Montar `PipelineTabs` no topo do `WorkPanel`
2. Ao iniciar pipeline, criar tab via `pipeline_tabs.add_tab()`
3. Ao completar, atualizar status via `update_tab_status()`
4. Conectar `action_next_pipeline()` ao `pipeline_tabs.next_tab()`

**Arquivos a modificar:**
- `tui/widgets/work_panel.py` -- montar PipelineTabs
- `tui/app.py` ou `tui/screens/workspace.py` -- conectar eventos

---

### D.5 ConfigView e somente leitura

| Campo | Valor |
|-------|-------|
| **Prioridade** | P3 |
| **Esforco** | M |
| **Impacto** | O usuario ve a configuracao mas nao pode editar defaults (engine, memory). Precisa editar YAML manualmente. |

**Sugestao de implementacao:**
1. Adicionar binding `e` para Edit na ConfigView
2. Abrir formulario com campos editaveis: default engine (select), default memory, database URL
3. Salvar via `yaml_ops.write_yaml()`

**Arquivos a modificar:**
- `tui/views/config.py` -- adicionar bindings e logica de edicao

---

### D.6 Nomenclatura "Pipeline" vs "Flow" inconsistente

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforco** | S |
| **Impacto** | O CLI ja migrou para "flow" (commits recentes), mas a TUI usa "pipeline" em todos os labels, view titles, e nomes de arquivos. Confusao terminologica. |

**Sugestao de implementacao:**
1. Atualizar todos os labels para "Flow" mantendo backward compat internamente
2. `PipelinesView.VIEW_TITLE = "Flows"`
3. Renomear display text em hints e notificacoes
4. Manter nomes de arquivo como estao (breaking change desnecessario)

**Arquivos a modificar:**
- `tui/views/pipelines.py` -- labels
- `tui/screens/create_form.py` -- `_PIPELINE_FIELDS` label text
- `tui/app.py` -- SCREENS: adicionar alias `"flows"` apontando para PipelinesView

---

## E. Acessibilidade e Inclusividade

### E.1 Cores duplicadas no tema Light (waiting == failed)

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforco** | S |
| **Impacto** | Em `themes.py:80-81`, `status_waiting = "#e45649"` e `status_failed = "#e45649"`. Mesma cor para dois estados semanticamente opostos. Usuarios que dependem de cor (alem do simbolo) nao conseguem distinguir. |

**Sugestao de implementacao:**
Alterar `status_waiting` no tema light para uma cor distinta:
```python
status_waiting="#c18401",  # usar o amarelo do working? ou #d75f00
status_failed="#e45649",   # manter vermelho
```
Reavaliar paleta completa do tema light para garantir unicidade.

**Arquivos a modificar:**
- `tui/themes.py` -- `_LIGHT`

---

### E.2 Widgets customizados sem ARIA labels/roles

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforco** | M |
| **Impacto** | `AgentCard`, `ApprovalBanner`, `StepBlock`, `ToolCallCard` e `PipelineTabs` nao declaram roles ou labels para screen readers. Conteudo inacessivel para usuarios de leitores de tela. |

**Sugestao de implementacao:**
1. Adicionar `COMPONENT_CLASSES` e tooltips descritivos
2. Para Textual, usar `tooltip` property e `name` parameter:
```python
class AgentCard(Widget):
    def __init__(self, ...):
        super().__init__(name=f"Agent: {name}, Role: {role}, Status: {status}")
```
3. ApprovalBanner: incluir `role="alertdialog"` semantico (via Textual's DOM attributes)

**Arquivos a modificar:**
- `tui/widgets/agent_card.py`
- `tui/widgets/approval_banner.py`
- `tui/widgets/step_block.py`
- `tui/widgets/tool_call_card.py`

---

### E.3 Sem anuncio de mudanca de status de agente

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforco** | S |
| **Impacto** | Quando o status de um agente muda (PENDING -> ACTIVE -> DONE), a sidebar atualiza visualmente mas nao ha live region ou anuncio. Usuarios de screen reader perdem contexto. |

**Sugestao de implementacao:**
1. Usar `self.notify()` com severity="information" para mudancas de status importantes (ACTIVE, FAILED)
2. Considerar Textual's `post_message` para anuncio: "Agent 'planner' is now active"

**Arquivos a modificar:**
- `tui/widgets/team_sidebar.py` -- `update_agent_status()`

---

### E.4 Navegacao sequencial limitada na sidebar

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforco** | S |
| **Impacto** | Nao ha como navegar entre AgentCards via setas up/down dentro da sidebar. O `VerticalScroll` nao roteia foco para AgentCards filhos. |

**Sugestao de implementacao:**
1. Tornar AgentCards focaveis (`can_focus = True`) -- ver C.5
2. `VerticalScroll` do Textual ja suporta Tab entre filhos focaveis
3. Adicionar visual de focus ring via CSS:
```css
AgentCard:focus {
    border: tall $accent;
}
```

**Arquivos a modificar:**
- `tui/widgets/agent_card.py` -- `can_focus = True`
- `tui/dash.tcss` -- focus style

---

### E.5 Sem indicador persistente de loading durante execucao

| Campo | Valor |
|-------|-------|
| **Prioridade** | P3 |
| **Esforco** | S |
| **Impacto** | Entre o notify "Starting pipeline..." e o primeiro evento, nao ha feedback visual persistente. Pode demorar segundos. |

**Sugestao de implementacao:**
1. Mostrar spinner/loading no ProgressBar label: "Connecting..."
2. Ou usar `LoadingIndicator` widget do Textual ate o primeiro evento chegar
3. Remover ao receber primeiro `TuiEvent`

**Arquivos a modificar:**
- `tui/widgets/work_panel.py`
- `tui/app.py` -- `on_tui_event()` (remover loading no primeiro evento)

---

### E.6 Contraste de `text_muted` no tema light

| Campo | Valor |
|-------|-------|
| **Prioridade** | P3 |
| **Esforco** | S |
| **Impacto** | `text_muted = "#a0a1a7"` sobre `background = "#fafafa"` tem ratio de contraste ~2.6:1, abaixo do minimo WCAG AA de 4.5:1 para texto normal. Hints, placeholders e timestamps ficam quase invisiveis. |

**Sugestao de implementacao:**
Escurecer `text_muted` no tema light:
```python
text_muted="#696c77",  # ratio ~5.2:1 contra #fafafa
```

**Arquivos a modificar:**
- `tui/themes.py` -- `_LIGHT`

---

## Resumo por Prioridade

### P0 -- Criticos (8 itens)

| ID | Item | Esforco |
|----|------|---------|
| A.1 | Confirmacao de exclusao | M |
| A.2 | Remover `/` search do Footer | S |
| A.3 | Formulario de flow com participants/leader | M |
| A.4 | Consistencia tecla `r` (Refresh vs Run) | S |
| A.5 | Stubs visiveis na AgentCardScreen | M |
| A.6 | Empty states nas DataTables | S |
| A.7 | Workspace vazio sem guia | M |
| A.8 | Focus management no ApprovalBanner | S |

### P1 -- Alta prioridade (10 itens)

| ID | Item | Esforco |
|----|------|---------|
| B.1 | View check (validacao) | M |
| B.2 | View session (sessoes) | M |
| B.3 | Server bindings visiveis | S |
| B.4 | Persistencia de runs | M |
| B.5 | Persistencia de eventos | M |
| B.6 | Input para pipeline | S |
| B.7 | Cancelamento de pipeline | M |
| B.8 | Alinhamento flow_ops | S |
| D.1 | Navegacao alem do command palette | M |
| E.1 | Cores duplicadas tema light | S |

### P2 -- Media prioridade (8 itens)

| ID | Item | Esforco |
|----|------|---------|
| C.1 | Fullscreen como toggle | S |
| C.2 | Help screen completo | M |
| C.3 | RunsView detail screen | M |
| C.4 | Feedback durante execucao | M |
| C.5 | AgentCard clicavel por teclado | S |
| C.6 | Validacao de formularios | S |
| C.7 | Exceptions silenciadas | M |
| C.8 | HintBar integrada | S |
| D.6 | Nomenclatura Pipeline vs Flow | S |
| E.2 | ARIA labels/roles | M |
| E.3 | Anuncio mudanca de status | S |
| E.4 | Navegacao sidebar por teclado | S |

### P3 -- Baixa prioridade (6 itens)

| ID | Item | Esforco |
|----|------|---------|
| D.2 | Theme switcher | M |
| D.3 | Sidebar compacta inteligente | S |
| D.4 | PipelineTabs integrado | M |
| D.5 | ConfigView editavel | M |
| E.5 | Loading indicator persistente | S |
| E.6 | Contraste text_muted tema light | S |

---

## Ordem de Implementacao Sugerida

### Sprint 1: Correcoes Criticas (P0)
1. A.2 (S) + A.4 (S) + A.6 (S) + A.8 (S) -- correcoes rapidas, alto impacto
2. A.1 (M) -- ConfirmDialog reutilizavel
3. A.3 (M) -- formulario de flow completo
4. A.5 (M) -- AgentCardScreen funcional
5. A.7 (M) -- onboarding no workspace

### Sprint 2: Paridade CLI (P1 selecionados)
1. E.1 (S) + B.3 (S) + B.8 (S) -- correcoes rapidas
2. B.6 (S) -- input para pipeline
3. B.7 (M) -- cancelamento de pipeline
4. B.4 (M) -- persistencia de runs
5. D.1 (M) -- navegacao

### Sprint 3: Completude (P1 restantes + P2 criticos)
1. B.1 (M) -- view check
2. B.2 (M) -- view session
3. B.5 (M) -- persistencia de eventos
4. C.4 (M) -- feedback de execucao
5. E.2 (M) -- acessibilidade widgets

### Sprint 4: Polish (P2 restantes + P3)
- Itens restantes conforme prioridade

---

## Apendice: Mapa de Arquivos Impactados

| Arquivo | Itens que o modificam |
|---------|-----------------------|
| `tui/app.py` | A.2, A.4, B.3, B.8, C.1, C.2, C.4, C.8, D.1, D.6 |
| `tui/views/pipelines.py` | A.4, B.6, B.7, D.6 |
| `tui/views/agents.py` | A.1, A.6 |
| `tui/views/engines.py` | A.1, A.6 |
| `tui/views/runs.py` | C.3 |
| `tui/views/config.py` | D.5 |
| `tui/screens/create_form.py` | A.3, C.6, D.6 |
| `tui/screens/agent_card.py` | A.5 |
| `tui/widgets/agent_card.py` | C.5, D.3, E.2, E.4 |
| `tui/widgets/approval_banner.py` | A.8, E.2 |
| `tui/widgets/work_panel.py` | A.7, C.4, D.4, E.5 |
| `tui/widgets/team_sidebar.py` | D.3, E.3 |
| `tui/widgets/empty_state.py` | A.7 |
| `tui/data_provider.py` | B.4, B.5, B.8 |
| `tui/themes.py` | E.1, E.6 |
| `tui/dash.tcss` | E.4 |
| **Novos arquivos** | |
| `tui/screens/confirm_dialog.py` | A.1 |
| `tui/screens/help_screen.py` | C.2 |
| `tui/screens/run_detail.py` | C.3 |
| `tui/screens/run_input.py` | B.6 |
| `tui/views/check.py` | B.1 |
| `tui/views/sessions.py` | B.2 |
