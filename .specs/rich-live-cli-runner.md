# Spec: Rich Live CLI Runner — Sair da "Caixa Preta"

| Campo      | Valor                                          |
|------------|------------------------------------------------|
| Data       | 2026-05-16                                     |
| Autor      | DX Sprint 3                                    |
| Status     | Rascunho                                       |
| Spec ID    | 012                                            |
| Origem     | `docs/plans/AVALIACAO-MINIAUTOGEN.md` §4 e §7.2 |

---

## Contrato de Prompt (G/C/FC)

### 🎯 Goal

Durante `miniautogen run` em modo headless (sem `--console`), substituir o spinner braille de uma linha por uma **interface inline rica** (biblioteca `Rich`) que mostra: agente ativo, ação corrente (`Contribute` / `Review` / `Synthesize`), número de turno/round, e as últimas 1–3 linhas do "pensamento" (output streaming truncado). A flag `--verbose` continua disponível mas é redefinida: dump de eventos brutos via stderr **sem** sobrescrever a UI. Permanece factível rodar em pipe/CI graças a detecção automática de TTY.

### 🚧 Constraint

1. **Reaproveitar o event bus existente:** a UI ouve o mesmo `EventSink` que o `--console` consome (`InMemoryEventSink` / `TuiEventSink`). Não criar um canal paralelo.
2. **Sem regressão de pipes/CI:** quando `stderr` não é TTY ou `MINIAUTOGEN_NO_TTY=1` está set, cai para `_VerboseEventSink` puro (linha por evento, sem `Rich`). Idem para `--format json`.
3. **Microkernel intacto:** a UI é puramente consumidor de eventos — não modifica o Runner nem injeta lógica de coordenação.
4. **Sem novas dependências:** `rich` ainda **não** está em `pyproject.toml`; precisa ser adicionado em `[project.optional-dependencies]` como `tui` (já existe esse extra) **e** como base, pois CLI é parte do produto core. Decisão: adicionar `rich>=13.0` em `dependencies` (não opcional). Avaliar peso (~250 KB) — aceitável.
5. **Acessível:** stream textual continua presente; `Rich` é uma camada visual sobre os mesmos eventos.

### 🛑 Failure Condition

- `miniautogen run main | cat` (pipe) produz códigos ANSI no output.
- Em CI sem TTY, a UI rich quebra ou trava por mais de 2s.
- Performance: a renderização atualiza mais de 30 vezes/segundo (consumindo CPU desnecessária).
- Output `--format json` mistura UI no stdout (deve ir só JSON limpo).
- Algum evento canônico (`run_started`, `agent_turn_started`, `agent_turn_finished`, `run_completed`) deixa de ser visível na UI.
- Em deliberação multi-agente, a UI esconde **quem** está falando.

---

## User Stories

- Como **engenheiro debugando uma deliberação**, quero ver `[Advogado Sênior — Review] » "O artigo 12 da LGPD impede..."` em tempo real, para entender se a discussão está convergindo ou divergindo, sem precisar abrir o dashboard web.
- Como **dev em CI/CD**, quero que o `miniautogen run` em modo não-TTY emita apenas linhas estruturadas legíveis em logs, para que GitHub Actions não polua a saída com ANSI.
- Como **PM acompanhando lateralmente o terminal de outro dev**, quero que a UI mostre a frase "Round 2/5, sintetizando consenso..." em vez de spinner morto, para entender o progresso sem perguntar.

---

## Critérios de Aceitação

- [ ] Quando `output_format == "text"` e `sys.stderr.isatty()` e não `--verbose`, a UI rich é ativada.
- [ ] A UI contém 3 zonas: (a) cabeçalho com `flow / run_id / elapsed`, (b) painel "atividade" com agente/ação/turno, (c) últimas N linhas de pensamento truncado a 80 colunas.
- [ ] `--verbose` mantém comportamento atual (`_VerboseEventSink` em stderr) **e** desativa a UI rich (sem duplicação visual).
- [ ] Em pipe/CI (não-TTY), a UI rich é desativada e cai para `_VerboseEventSink`.
- [ ] `--format json` desativa toda UI visual (stdout fica limpo).
- [ ] A UI ouve os eventos canônicos via uma classe `RichLiveEventSink` (novo arquivo `miniautogen/cli/services/rich_live_sink.py`).
- [ ] Frame rate ≤ 8 FPS (`Live(refresh_per_second=8)`).
- [ ] `Ctrl+C` durante UI rich não deixa o terminal em estado quebrado (handler `__exit__` do `Live` é chamado).
- [ ] Pelo menos 4 testes: TTY detectada → rich ativa; sem TTY → cai para verbose sink; `--verbose` flag → verbose sink; `--format json` → nenhum sink visual.
- [ ] Smoke visual: rodar uma deliberação de 3 agentes e capturar screenshot demonstrando UI funcional.

---

## Invariantes Afetadas

- [ ] **Isolamento de Adapters** — UI vive em `cli/`, não em `core/`.
- [ ] **Microkernel / PipelineRunner** — UI não modifica runner.
- [x] **Assincronismo Canônico (AnyIO)** — `RichLiveEventSink.publish` é `async def`; o `Live` da Rich roda em thread separada gerenciada pelo próprio Rich (não bloqueia o loop).
- [x] **Policies Event-Driven** — a UI é um sink lateral, observa eventos sem reagir/modificar.

---

## Dependências

| Dependência                                                   | Tipo    | Estado                          |
|---------------------------------------------------------------|---------|---------------------------------|
| `rich>=13.0`                                                  | Externa | **Adicionar** em `dependencies` |
| Event bus (`EventSink`, `InMemoryEventSink`, `CompositeEventSink`) | Interna | Já existe                       |
| Detecção TTY (`sys.stderr.isatty`)                            | Padrão  | Built-in                        |
| `MINIAUTOGEN_NO_TTY` env var                                  | Nova    | Documentar                      |

---

## Notas Adicionais

- **Por que `Rich Live` e não `Textual`?** `Textual` é full-screen TUI (já existe em `miniautogen/tui/`). `Rich Live` é inline (não ocupa a tela inteira), o que combina com o paradigma de "comando que termina". Termos as duas é deliberado: `miniautogen run` ⇒ inline rich; `miniautogen dash` ⇒ Textual full-screen.
- **Tamanho da dependência:** `rich` adiciona ~250 KB ao install. Trade-off aceitável dado que CLI é o caminho principal de uso. Alternativa: `colorama` apenas, mas perderia layout.
- **Localização das strings de UI:** manter em inglês por enquanto (consistente com o restante do CLI). i18n é fora de scope.
- **Item 2 (graceful-cancel) interage:** quando o Ctrl+C dispara o save shielded, a UI deve exibir uma última linha `Saving checkpoint...` antes de sair.
