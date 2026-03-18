# Ambiente de desenvolvimento com agentes: configuracao, ferramentas e tecnicas para DX de qualidade

> **Analise de ambiente** -- Como um setup de desenvolvimento orientado a agentes de IA transforma a relacao entre humano, codigo e qualidade de software.

**Contexto:** Este documento captura e analisa o ambiente de desenvolvimento configurado em torno do repositorio MiniAutoGen -- um framework Python microkernel para orquestracao multi-agente. O foco nao e tutorial ("como configurar"), mas percepcao ("o que esta configurado, por que funciona, e que tecnicas emergem desse design").

**Audiencia:** Desenvolvedores e tech leads que querem entender como estruturar um ambiente de desenvolvimento assistido por agentes de IA com controle de qualidade real -- nao apenas "vibes".

---

## Sumario

- [1. Visao geral do ambiente](#1-visao-geral-do-ambiente)
- [2. Sistema de skills (Superpowers + Ring)](#2-sistema-de-skills-superpowers--ring)
- [3. Delegacao multi-modelo (Codex MCP)](#3-delegacao-multi-modelo-codex-mcp)
- [4. Sistema de memoria persistente](#4-sistema-de-memoria-persistente)
- [5. Hooks e automacao](#5-hooks-e-automacao)
- [6. MCP Servers (integracao com sistemas externos)](#6-mcp-servers-integracao-com-sistemas-externos)
- [7. Contrato de desenvolvimento (CLAUDE.md)](#7-contrato-de-desenvolvimento-claudemd)
- [8. Regra dos 3 arquivos (Ring Orchestrator)](#8-regra-dos-3-arquivos-ring-orchestrator)
- [9. Tecnicas de qualidade transversais](#9-tecnicas-de-qualidade-transversais)
- [10. Percepcao critica e oportunidades](#10-percepcao-critica-e-oportunidades)

---

## 1. Visao geral do ambiente

### O agente como IDE primaria

O desenvolvimento do MiniAutoGen utiliza o **Claude Code** como interface primaria de desenvolvimento. Nao como assistente lateral ou copiloto de autocomplete -- como a propria IDE. O modelo subjacente e o **Claude Opus 4.6** com janela de contexto de **1 milhao de tokens**, o que permite que sessoes inteiras de desenvolvimento (leitura de multiplos arquivos, analise de dependencias, refatoracao cross-cutting) acontecam dentro de uma unica conversa sem degradacao de contexto.

O modo padrao de operacao e **`plan`** -- o agente propoe acoes e aguarda aprovacao humana antes de executar. Isso e uma decisao de design critica: seguranca por padrao. O agente nao pode fazer `git push --force`, apagar arquivos ou executar comandos destrutivos sem consentimento explicito. Quando o desenvolvedor confia numa sequencia de operacoes, pode temporariamente escalar para modo `act`, mas o default e conservador.

```json
{
  "permissions": {
    "allow": [
      "Bash(ls:*)",
      "Bash(/Users/brunocapelao/.pyenv/versions/3.13.5/bin/python3.13:*)"
    ],
    "defaultMode": "plan"
  }
}
```

A whitelist de permissoes e minima: `ls` e o interpretador Python. Qualquer outra operacao de shell requer aprovacao. Isso impede que o agente execute comandos arbitrarios mesmo quando "tem certeza" de que sao seguros.

### Por que Claude Code e nao um IDE tradicional com copilot?

A diferenca entre usar Claude Code como IDE e usar VS Code + Copilot e qualitativa, nao quantitativa:

| Dimensao | IDE + Copilot | Claude Code como IDE |
|----------|---------------|---------------------|
| **Unidade de trabalho** | Linha, funcao | Tarefa inteira (multi-arquivo, multi-step) |
| **Contexto** | Arquivo aberto + vizinhos | Repositorio inteiro (1M tokens) |
| **Interacao** | Autocomplete passivo | Dialogo ativo sobre decisoes |
| **Processo** | Nenhum (o dev decide) | Skills mandatorias (o agente segue processo) |
| **Verificacao** | Manual (dev roda testes) | Automatica (agente verifica antes de completar) |
| **Delegacao** | Nao existe | Multi-modelo (Claude + GPT) |
| **Memoria** | Nenhuma entre sessoes | Persistente por projeto |

A implicacao e que o Claude Code nao substitui apenas o editor de texto -- ele substitui parte do fluxo de trabalho do desenvolvedor. O agente nao apenas escreve codigo; ele planeja, testa, verifica, delega e documenta.

Isso cria uma nova categoria de interacao: o desenvolvedor opera mais como um **tech lead** que revisa e aprova do que como um **implementador** que escreve cada linha.

### O repositorio

O MiniAutoGen e um framework Python orientado a **Microkernel** para orquestracao de pipelines e agentes assincronos. A arquitetura atual tem ~15.000+ LOC distribuidos em 4 camadas:

| Camada | Responsabilidade | Modulos |
|--------|------------------|---------|
| **Core/Kernel** | Contratos, eventos, runtimes de coordenacao | `core/contracts/`, `core/events/`, `core/runtime/` |
| **Policies** | Regras transversais (retry, budget, approval, timeout) | `policies/` |
| **Adapters** | Drivers de backend, templates, LLM providers | `backends/`, `adapters/` |
| **Shell** | CLI, TUI Dashboard, Server | `cli/`, `tui/`, `app/` |

A complexidade do repositorio e relevante para entender o ambiente: nao se trata de um projeto simples onde "qualquer LLM resolve". A separacao rigorosa de responsabilidades, os 47+ tipos de evento canonicos, os 4 runtimes de coordenacao e a abstracacao multi-provider criam um contexto onde erros de acoplamento sao faceis de introduzir e dificeis de detectar. O ambiente de desenvolvimento precisa compensar isso.

### Anatomia de uma sessao tipica

Uma sessao tipica de desenvolvimento neste ambiente segue um padrao reconhecivel:

1. **Inicializacao** (~5 segundos): O Claude Code carrega o MEMORY.md, as regras de delegacao, o contrato constitucional (`claude.md`) e os plugins ativados. O agente chega ao primeiro prompt ja sabendo o nome do projeto, as decisoes arquiteturais anteriores, as convencoes de naming e o roadmap.

2. **Contextualizacao** (~1-2 minutos): O desenvolvedor descreve a tarefa. O agente verifica skills aplicaveis, consulta memorias relevantes e, se necessario, le arquivos do repositorio para entender o estado atual.

3. **Planejamento** (~3-5 minutos): O agente propoe um plano (ativando a skill `writing-plans` se a tarefa for complexa). O plano inclui file paths exatos, code examples e checkpoints de review humano.

4. **Execucao** (~variavel): O agente executa o plano step-by-step, com cada acao proposta em modo `plan` e aprovada pelo humano. Skills de TDD, debugging e verificacao sao ativadas conforme necessario.

5. **Verificacao** (~2-3 minutos): O agente apresenta evidencia de conclusao (testes passando, output demonstrado). Memorias de projeto sao atualizadas se decisoes relevantes foram tomadas.

O tempo total e geralmente 30-60% menor que desenvolvimento manual para tarefas de complexidade media, com a vantagem adicional de que o processo e documentado e reprodutivel.

---

## 2. Sistema de skills (Superpowers + Ring)

O conceito central do ambiente e que o agente de IA nao opera por intuicao -- ele opera por **processo**. Skills sao instrucoes processuais que governam COMO o agente trabalha, invocadas ANTES de qualquer acao. O agente nao pode racionalizar pular uma skill aplicavel.

### Superpowers plugin (v4.3.1)

O plugin **Superpowers** fornece skills processuais que atacam os modos de falha mais comuns de agentes de IA: agir antes de pensar, declarar sucesso sem evidencia, e ignorar processo quando "a tarefa e simples".

| Skill | O que governa | Modo de falha que previne |
|-------|---------------|--------------------------|
| `brainstorming` | Refinamento socratico antes de implementar | Overengineering, solucoes precipitadas |
| `test-driven-development` | RED-GREEN-REFACTOR mandatorio | Codigo sem testes, testes escritos depois |
| `systematic-debugging` | 4 fases antes de tentar fix | Fix-by-guess, loops infinitos de debugging |
| `verification-before-completion` | Evidencia antes de claims | "Pronto!" sem verificacao real |
| `writing-plans` | Planos com file paths exatos e code examples | Planos vagos e inaplicaveis |
| `executing-plans` | Execucao com checkpoints de review humano | Execucao autonoma sem supervisao |
| `dispatching-parallel-agents` | Paralelismo para tasks independentes | Execucao sequencial desnecessaria |
| `subagent-driven-development` | Execucao autonoma com code review entre tasks | Monolithic agent behavior |
| `receiving-code-review` | Verificacao tecnica antes de implementar sugestoes | Aceitacao cega de sugestoes de review |
| `requesting-code-review` | 3 reviewers paralelos (code, business-logic, security) | Review unidimensional |

#### Tipos de skill: Rigid vs Flexible

Nem todas as skills sao iguais. O sistema distingue entre dois tipos:

- **Rigid**: O agente deve seguir exatamente os passos definidos. Nao ha margem para adaptacao. Exemplos: `test-driven-development` (RED-GREEN-REFACTOR nao e negociavel), `systematic-debugging` (as 4 fases devem ser seguidas na ordem).

- **Flexible**: O agente deve aplicar o padrao, mas pode adaptar ao contexto. Exemplos: `brainstorming` (a profundidade do refinamento socratico varia com a complexidade do problema), `writing-plans` (o nivel de detalhe depende do escopo).

A distincao e importante porque evita dois anti-padroes opostos: rigidez excessiva (seguir TDD roboticamente para um one-liner) e flexibilidade excessiva (pular debugging sistematico porque "eu ja sei o que e").

#### Exemplo pratico: systematic-debugging em acao

Para ilustrar como uma skill rigid funciona na pratica, considere um cenario onde o agente encontra um `TypeError: 'NoneType' object is not subscriptable` ao executar testes:

**Sem a skill** (comportamento natural do agente):
```
1. O agente ve o erro
2. Imediatamente propoe um fix: "Vamos adicionar um check de None antes de acessar"
3. O fix pode funcionar ou pode mascarar o bug real
4. Se nao funcionar, tenta outra variacao do mesmo fix
5. Loop potencialmente infinito
```

**Com a skill `systematic-debugging`** (4 fases mandatorias):
```
Fase 1 - OBSERVAR: Ler a stack trace completa, identificar o arquivo e linha exatos.
         Resultado: O erro ocorre em core/runtime/workflow.py:142

Fase 2 - HIPOTESE: Formular hipotese especifica sobre por que o valor e None.
         Resultado: "O step anterior pode ter retornado None em vez de um dict
                     quando o agent driver nao encontra o engine configurado"

Fase 3 - TESTAR: Verificar a hipotese com evidencia (nao com opiniao).
         Resultado: Ler o codigo do step anterior, confirmar que o path de
                    "engine not found" retorna None em vez de levantar excecao

Fase 4 - CORRIGIR: Agora, com compreensao completa, aplicar o fix correto.
         Resultado: Corrigir o step anterior para levantar EngineNotFoundError
                    em vez de retornar None. O TypeError desaparece porque a
                    causa raiz foi tratada, nao o sintoma.
```

A diferenca e que a skill forca o agente a **entender** antes de **agir**. O fix natural do agente (check de None) teria mascarado um bug real de design.

#### Mecanismo de invocacao

A tecnica-chave e que skills sao invocadas **ANTES** de qualquer acao. Quando o agente recebe uma tarefa, o sistema verifica se alguma skill e aplicavel e a ativa automaticamente. O agente nao pode:

1. Decidir que "essa tarefa e simples demais para brainstorming"
2. Pular TDD porque "e so uma mudanca de config"
3. Declarar conclusao sem passar pela skill de verificacao

Isso cria um **processo mandatorio** que independe do julgamento situacional do agente -- exatamente onde agentes de IA costumam falhar.

### Ring system (marketplace de plugins)

Enquanto o Superpowers governa processos individuais, o **Ring** organiza times inteiros de especialistas. O Ring e um marketplace de plugins open-source (hospedado em `lerianstudio/ring`) que fornece equipes tematicas:

| Ring | Versao | Especialidade | Agentes |
|------|--------|---------------|---------|
| `ring-default` | -- | Operacoes base, utilities, git worktrees | Ferramentas fundamentais |
| `ring-dev-team` | v0.42.0 | Ciclo de desenvolvimento completo | 6 gates sequenciais |
| `ring-pm-team` | -- | Planejamento pre-desenvolvimento | 9 gates de especificacao |
| `ring-tw-team` | -- | Documentacao tecnica | Guias, API docs, review |
| `ring-ops-team` | -- | Operacoes e infraestrutura | Incident response, cost optimization, security audit |
| `ring-finance-team` | -- | Financas e contabilidade | 6 especialistas financeiros |
| `ring-finops-team` | -- | Compliance regulatorio brasileiro | BACEN, RFB |
| `ring-pmm-team` | -- | Go-to-market e estrategia | Positioning, pricing, launch |
| `ring-pmo-team` | -- | Portfolio management | Governance, resource allocation |

Todos os 9 rings estao habilitados neste ambiente:

```json
{
  "enabledPlugins": {
    "ring-default@ring": true,
    "ring-dev-team@ring": true,
    "ring-pm-team@ring": true,
    "ring-finops-team@ring": true,
    "ring-finance-team@ring": true,
    "ring-tw-team@ring": true,
    "ring-ops-team@ring": true,
    "ring-pmm-team@ring": true,
    "ring-pmo-team@ring": true
  }
}
```

#### ring-dev-team: o ciclo de 6 gates

O ring mais relevante para desenvolvimento e o `ring-dev-team`, que organiza o ciclo de implementacao em 6 gates sequenciais:

```
implementation → devops → SRE → testing → review → validation
```

Cada gate e um especialista com criterios de aceitacao proprios. O agente nao avanca para o proximo gate sem satisfazer o anterior. Isso transforma o desenvolvimento de uma atividade ad-hoc num pipeline com quality gates formais.

#### ring-pm-team: pre-planejamento em 9 gates

Antes sequer de comecar a implementar, o `ring-pm-team` fornece 9 gates de especificacao:

```
research → PRD → feature-map → TRD → API → data-model → dependencies → tasks → subtasks
```

A profundidade e notavel: o agente nao pode comecar a escrever codigo sem ter passado por pesquisa, documento de requisitos do produto, mapeamento de features, documento tecnico, definicao de API, modelo de dados, analise de dependencias, decomposicao em tasks e sub-tasks.

Na pratica, nem toda tarefa exige os 9 gates. Mas a existencia do pipeline completo garante que, para tarefas complexas, nenhuma etapa seja inadvertidamente pulada.

### Plugins adicionais habilitados

Alem de Superpowers e Ring, o ambiente inclui:

| Plugin | Fonte | Funcao |
|--------|-------|--------|
| `claude-delegator` | jarrodwatts-claude-delegator | Delegacao multi-modelo |
| `frontend-design` | claude-plugins-official | Design de interfaces |
| `github` | claude-plugins-official | Operacoes GitHub nativas |
| `playwright` | claude-plugins-official | Automacao de browser para testes E2E |
| `supabase` | claude-plugins-official | Integracao com Supabase |
| `claude-md-management` | claude-plugins-official | Gerenciamento de CLAUDE.md |
| `rust-analyzer-lsp` | claude-plugins-official | Language Server Protocol |

A quantidade de plugins ativados (18 no total) pode parecer excessiva, mas reflete a filosofia do ambiente: **especializar em vez de generalizar**. Cada plugin adiciona capacidades especificas em vez de sobrecarregar o agente principal com instrucoes genericas.

### Interacao entre Superpowers e Ring

Uma questao natural e: como Superpowers e Ring coexistem? A resposta e que eles operam em niveis diferentes:

| Camada | Sistema | O que governa | Exemplo |
|--------|---------|---------------|---------|
| **Processo** | Superpowers | COMO o agente executa cada acao individual | "Antes de implementar, faca brainstorming" |
| **Pipeline** | Ring | EM QUE ORDEM as etapas de um projeto se encadeiam | "Passe por implementation → testing → review" |

Superpowers governa o **micro** (cada acao). Ring governa o **macro** (o fluxo do projeto). Um agente passando pelo gate de `testing` do ring-dev-team ainda usara a skill `test-driven-development` do Superpowers para escrever cada teste individual.

A sobreposicao existe (ambos mencionam testes, por exemplo), mas nao e conflitante -- e reforco em camadas. O ring diz "voce precisa passar pelo gate de testes". O Superpowers diz "e os testes devem ser escritos em RED-GREEN-REFACTOR". Sao instrucoes complementares em niveis de granularidade diferentes.

### A economia cognitiva das skills

Skills resolvem um problema fundamental de agentes de IA: **o custo cognitivo da decisao processual**. Cada vez que um agente decide "preciso fazer TDD nesta tarefa?" ou "devo fazer debugging sistematico ou posso tentar um fix rapido?", ele consome tokens de raciocinio e introduz variabilidade no resultado.

Skills eliminam essas decisoes. O agente nao gasta contexto decidindo SE vai usar TDD -- ele ja sabe que TDD e mandatorio. Isso libera capacidade cognitiva para o problema real, que e a implementacao.

A analogia mais proxima e com checklists na aviacao. Pilotos nao decidem se vao verificar os flaps antes da decolagem -- o checklist manda, e eles executam. A qualidade vem da **consistencia**, nao da **improvisacao**.

---

## 3. Delegacao multi-modelo (Codex MCP)

### O problema que resolve

Mesmo com 1M tokens de contexto, um unico modelo tem pontos cegos. Ele desenvolve "vicios" de raciocinio, tende a confirmar suas proprias suposicoes, e pode ficar preso em loops de debugging. A solucao arquitetural deste ambiente e usar um **segundo modelo** como consultor especializado.

### Arquitetura da delegacao

O **GPT-5.2 Codex** opera como segundo modelo via protocolo **MCP** (Model Context Protocol), configurado como servidor stdio:

```json
{
  "mcpServers": {
    "codex": {
      "type": "stdio",
      "command": "codex",
      "args": [
        "-m",
        "gpt-5.2-codex",
        "mcp-server"
      ]
    }
  }
}
```

O Claude Code (Opus 4.6) e o **executor** -- ele escreve codigo, roda testes, gerencia arquivos. O GPT-5.2 Codex e o **consultor** -- ele analisa, revisa, sugere, mas nunca executa diretamente.

### 5 especialistas GPT

A delegacao nao e generica ("pergunte ao GPT"). Cada chamada e roteada para um dos 5 especialistas, cada um com um prompt de sistema dedicado:

| Especialista | Especialidade | Quando ativar |
|-------------|---------------|---------------|
| **Architect** | System design, tradeoffs, debugging complexo | Decisoes de arquitetura, apos 2+ tentativas falhadas |
| **Plan Reviewer** | Validacao de planos antes da execucao | Antes de iniciar trabalho significativo |
| **Scope Analyst** | Analise pre-planejamento, ambiguidades | Requisitos vagos, multiplas interpretacoes |
| **Code Reviewer** | Qualidade de codigo, bugs, seguranca | Antes de merge, apos implementacao |
| **Security Analyst** | Vulnerabilidades, threat modeling | Mudancas de auth, dados sensiveis, APIs novas |

### Design stateless

Cada chamada ao Codex e **independente**. O especialista GPT nao tem memoria de chamadas anteriores. Isso e uma limitacao tecnica (o MCP server retorna session IDs, mas o Claude Code so expoe a resposta final), mas tambem uma decisao de design que simplifica o raciocinio sobre o sistema.

A implicacao pratica: cada delegacao deve incluir **contexto completo**. O agente orquestrador (Claude) deve montar um prompt autocontido com tudo que o especialista precisa saber.

### Formato mandatorio de 7 secoes

Toda delegacao segue um formato estruturado:

```markdown
1. TASK: [Uma frase -- objetivo atomico e especifico]

2. EXPECTED OUTCOME: [Como o sucesso se parece]

3. CONTEXT:
   - Current state: [o que existe agora]
   - Relevant code: [paths ou snippets]
   - Background: [por que isso e necessario]

4. CONSTRAINTS:
   - Technical: [versoes, dependencias]
   - Patterns: [convencoes existentes a seguir]
   - Limitations: [o que nao pode mudar]

5. MUST DO:
   - [Requisito 1]
   - [Requisito 2]

6. MUST NOT DO:
   - [Acao proibida 1]
   - [Acao proibida 2]

7. OUTPUT FORMAT:
   - [Como estruturar a resposta]
```

O formato e mandatorio por uma razao pratica: sem estrutura, delegacoes para modelos externos degeneram rapidamente em prompts vagos que produzem respostas genericas. As 7 secoes forcam o orquestrador a pensar com clareza sobre o que realmente precisa.

### Triggers proativos vs reativos

O sistema de delegacao nao espera que o usuario peca explicitamente por ajuda. Existem dois tipos de trigger:

**Triggers proativos** (verificados em CADA mensagem do usuario):

| Sinal | Especialista |
|-------|-------------|
| Decisao de arquitetura/design | Architect |
| 2+ tentativas falhadas no mesmo issue | Architect (perspectiva fresca) |
| "Review this plan", "validate approach" | Plan Reviewer |
| Requisitos vagos/ambiguos | Scope Analyst |
| "Review this code", "find issues" | Code Reviewer |
| Concerns de seguranca, "is this secure" | Security Analyst |

**Triggers reativos** (pedido explicito do usuario):

| O usuario diz | Acao |
|---------------|------|
| "ask GPT", "consult GPT", "ask codex" | Identifica tipo de tarefa e roteia |
| "ask GPT to review the architecture" | Delega ao Architect |
| "have GPT review this code" | Delega ao Code Reviewer |
| "GPT security review" | Delega ao Security Analyst |

O aspecto mais relevante dos triggers proativos e a deteccao de **falhas repetidas**. Apos 2 tentativas falhadas de corrigir o mesmo problema, o agente deve automaticamente escalar para o Architect GPT. Isso quebra loops de debugging onde o modelo fica tentando variacoes da mesma abordagem incorreta.

### Modos de operacao

Cada especialista pode operar em dois modos:

| Modo | Sandbox | Quando usar |
|------|---------|-------------|
| **Advisory** | `read-only` | Analise, recomendacoes, revisoes |
| **Implementation** | `workspace-write` | Fazer mudancas, corrigir issues |

O modo determina o nivel de acesso. Um Architect em modo advisory nao pode modificar arquivos -- ele analisa e recomenda. O mesmo Architect em modo implementation pode fazer mudancas diretamente.

### Retry flow com contexto acumulado

Quando uma implementacao delegada falha na verificacao, o retry inclui **todo o historico** de tentativas anteriores:

```
Tentativa 1 → Verificar → [Falha]
     ↓
Tentativa 2 (nova chamada com: tarefa original + o que foi tentado + detalhes do erro)
     ↓
Tentativa 3 (nova chamada com: historico completo de tentativas)
     ↓
Escalar para o humano
```

O contexto acumulado e critico porque cada chamada e stateless. Sem incluir o historico, o especialista GPT tentaria a mesma abordagem que ja falhou.

### Exemplo concreto de delegacao

Para tornar tangivel, aqui esta um exemplo de como uma delegacao real seria estruturada para o Architect:

```markdown
TASK: Avaliar se RuntimeInterceptors devem ser implementados como middleware
composavel ou como decorators no PipelineRunner do MiniAutoGen.

EXPECTED OUTCOME: Recomendacao clara com justificativa tecnica e exemplo
de implementacao em ambas as abordagens.

CONTEXT:
- Current state: O MiniAutoGen tem 4 runtimes de coordenacao (Workflow,
  AgenticLoop, Deliberation, Composite) e um PipelineRunner que e o unico
  executor oficial.
- Relevant code: miniautogen/core/runtime/pipeline_runner.py,
  miniautogen/core/contracts/protocols.py
- Background: Interceptors transformativos sao o grande diferencial competitivo
  proposto (vs callbacks observacionais de concorrentes). Precisam ser
  boundary-aware (Flow, Step, Agent level).

CONSTRAINTS:
- Technical: Python 3.11+, AnyIO para async, Pydantic para contratos
- Patterns: Isolamento absoluto de adapters, policies event-driven laterais
- Limitations: PipelineRunner deve permanecer o unico executor

MUST DO:
- Comparar ambas abordagens com code examples
- Considerar composabilidade (multiplos interceptors encadeados)
- Avaliar impacto no sistema de eventos canonicos (47+ types)
- Fornecer effort estimate (Quick/Short/Medium/Large)

MUST NOT DO:
- Propor mudancas que violem o isolamento Core/Adapters
- Sugerir patterns que introduzam acoplamento com providers especificos
- Ignorar o requisito de cancelamento estruturado via AnyIO

OUTPUT FORMAT:
Bottom line → Analise comparativa → Recomendacao → Effort estimate
```

Note a precisao do prompt: file paths exatos, constraints do repositorio incluidas, e instrucoes explicitas sobre o que NAO fazer. Isso e o que o formato de 7 secoes forca -- sem ele, a delegacao seria algo como "o que voce acha de interceptors vs decorators?", que produziria uma resposta generica e inaplicavel.

### Tecnica-chave: sintese, nao repasse

O agente orquestrador (Claude) **nunca** mostra o output bruto do especialista GPT ao usuario. Ele sintetiza, interpreta e aplica julgamento critico. O especialista pode estar errado -- o orquestrador avalia a resposta antes de apresenta-la.

Isso e sutil mas fundamental. Sem sintese, o sistema degeneraria num "tradutor de prompts" -- o usuario fala com o Claude que repassa para o GPT que responde para o Claude que repassa para o usuario. A sintese adiciona uma camada de raciocinio critico que justifica a complexidade do setup multi-modelo.

---

## 4. Sistema de memoria persistente

### O problema da amnesia

Agentes de IA operam em sessoes isoladas. Sem memoria persistente, cada conversa comeca do zero: o agente nao sabe que decisoes arquiteturais foram tomadas, que convencoes foram estabelecidas, ou que erros ja foram cometidos e corrigidos. Isso leva a retrabalho, inconsistencia e "context rot" -- a degradacao gradual do alinhamento entre o agente e o projeto.

### Arquitetura da memoria

O sistema de memoria e baseado em arquivos, armazenados em:

```
~/.claude/projects/-Users-brunocapelao-Projects-miniAutoGen/memory/
```

Estrutura atual:

```
memory/
├── MEMORY.md                        # Index (carregado automaticamente)
├── project_backend_drivers.md       # Projeto: Backend drivers
├── project_milestone1_sdk.md        # Projeto: SDK Foundation
├── project_milestone2_cli.md        # Projeto: CLI Developer Product
├── project_strategic_vision.md      # Projeto: Visao estrategica
└── project_tui_dash.md              # Projeto: TUI Dashboard
```

### 4 tipos de memoria

| Tipo | Proposito | Exemplo |
|------|-----------|---------|
| **user** | Preferencias e padroes do desenvolvedor | Estilo de commit, convencoes de nomes |
| **feedback** | Correcoes e confirmacoes | "Nao use async generators neste caso", "Essa abordagem funcionou bem" |
| **project** | Estado e decisoes de projeto | Decisoes arquiteturais, convencoes, naming |
| **reference** | Informacoes de referencia | Links, specs externas, APIs |

### Index automatico (MEMORY.md)

O arquivo `MEMORY.md` funciona como indice e e **carregado automaticamente** no inicio de cada conversa. Ele contem links para as memorias detalhadas:

```markdown
# MiniAutoGen Memory Index

## Project

- [backend-drivers-implementation](project_backend_drivers.md) -- Backend driver abstraction
- [milestone1-sdk-foundation](project_milestone1_sdk.md) -- Milestone 1 SDK Foundation
- [milestone2-cli-developer-product](project_milestone2_cli.md) -- Milestone 2 CLI
- [tui-dash-implementation](project_tui_dash.md) -- TUI Dashboard
- [strategic-vision-2025-06](project_strategic_vision.md) -- Strategic positioning
```

### Frontmatter estruturado

Cada arquivo de memoria usa frontmatter YAML para categorizacao:

```yaml
---
name: strategic-vision-2025-06
description: MiniAutoGen strategic positioning, naming conventions, and architectural evolution
type: project
---
```

Isso permite que o sistema de memoria filtre e priorize memorias por tipo, evitando sobrecarga de contexto desnecessaria.

### O que NAO salvar

Tao importante quanto o que salvar e o que **nao** salvar:

| Nao salvar | Razao |
|------------|-------|
| Padroes de codigo | Derivaveis do repositorio em tempo real |
| Historico git | Disponivel via `git log` |
| Solucoes de debugging | Especificas demais, envelhecem rapido |
| Detalhes de implementacao | Mudam com frequencia |

A regra e: salve **decisoes** e **convencoes**, nao **implementacoes**.

### Tecnica-chave: memoria de feedback bidirecional

A memoria de feedback captura tanto **correcoes** ("nao faca X") quanto **confirmacoes** ("essa abordagem funcionou bem"). A maioria dos sistemas so registra erros. Ao registrar tambem acertos, o agente aprende nao apenas o que evitar, mas o que replicar.

Isso previne **drift** -- a tendencia de um agente corrigido em excesso a se afastar gradualmente de comportamentos corretos por medo de repetir erros antigos.

---

## 5. Hooks e automacao

### Inicializacao automatica de sessao

Hooks de `SessionStart` executam scripts de inicializacao do `ring-dev-team` quando uma nova sessao comeca. Os triggers incluem:

| Trigger | Quando |
|---------|--------|
| `startup` | Inicio de nova sessao |
| `resume` | Retomada de sessao anterior |
| `clear` | Apos limpeza de contexto |
| `compact` | Apos compactacao de historico |

### O que os hooks injetam

A inicializacao automatica injeta:

1. **Contexto de time**: Qual ring-team esta ativo, quais gates estao disponiveis
2. **Workflow state**: Em que ponto do pipeline de desenvolvimento o projeto se encontra
3. **Memorias relevantes**: O MEMORY.md e carregado com referencia indexada a todas as memorias de projeto

Isso garante que o agente nunca comeca uma sessao "do zero" -- ele sempre tem contexto sobre o projeto, as convencoes e o estado atual do trabalho.

### Ausencia de hooks complexos

E notavel que o ambiente **nao** utiliza hooks de pre/pos-commit ou automacoes de CI/CD via hooks do Claude Code. A filosofia parece ser: hooks para **contexto** (injetar informacao), nao para **enforcement** (bloquear acoes). O enforcement e feito pelas skills e pelo modo `plan`.

---

## 6. MCP Servers (integracao com sistemas externos)

O **Model Context Protocol** (MCP) permite que o agente interaja com sistemas externos sem sair do ambiente de desenvolvimento. Tres servidores estao configurados:

### Codex (GPT-5.2)

```json
{
  "codex": {
    "type": "stdio",
    "command": "codex",
    "args": ["-m", "gpt-5.2-codex", "mcp-server"]
  }
}
```

**Funcao:** Delegacao de tarefas especializadas para 5 especialistas GPT (detalhado na secao 3). E o MCP server mais utilizado e o mais critico para a DX multi-modelo.

**Protocolo:** stdio (comunicacao via stdin/stdout do processo local). Nao requer rede -- o modelo GPT roda como processo local via CLI do Codex.

### Cloudflare

```json
{
  "cloudflare": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "mcp-remote", "https://graphql.mcp.cloudflare.com/mcp"]
  }
}
```

**Funcao:** API GraphQL para gerenciamento de infraestrutura Cloudflare. Permite que o agente consulte e configure Workers, DNS, R2, KV e outros servicos sem sair do IDE.

**Protocolo:** MCP remote via npx -- o processo local conecta ao endpoint remoto da Cloudflare.

### Hetzner

```json
{
  "hetzner": {
    "type": "stdio",
    "command": "mcp-hetzner",
    "env": {
      "HCLOUD_TOKEN": "***"
    }
  }
}
```

**Funcao:** Gerenciamento de cloud Hetzner via token autenticado. Permite provisionar, consultar e gerenciar servidores, redes e volumes.

**Protocolo:** stdio com variavel de ambiente para autenticacao.

### Implicacao para DX

A presenca de MCP servers de infraestrutura (Cloudflare, Hetzner) junto com o de desenvolvimento (Codex) indica que o ambiente e projetado para **operacoes full-stack** -- o agente pode nao apenas escrever codigo, mas tambem provisionar infraestrutura, configurar DNS e gerenciar deployments. Tudo dentro do mesmo fluxo de conversa.

Isso elimina o context-switching entre IDE, cloud console e terminal -- uma das maiores fontes de friccao em workflows de desenvolvimento.

---

## 7. Contrato de desenvolvimento (CLAUDE.md)

### O conceito de "constituicao"

O arquivo `claude.md` na raiz do repositorio funciona como uma **constituicao** para o agente. Nao e documentacao para humanos -- e um contrato que define como o agente deve operar neste repositorio especifico. O titulo e explicito: "Constituicao do Sistema e Contrato de Prompt".

O agente e definido como **Engenheiro de Software Senior** e **Arquiteto de IA**, e a primeira diretiva e clara: **"Vibe coding e estritamente proibido."**

### Spec-Driven Development em 4 passos

O CLAUDE.md impoe um workflow de desenvolvimento obrigatorio:

```
1. Spec (/.specs/)  →  2. Test-First  →  3. Prompt Contract  →  4. Atomic Commits
```

#### Passo 1: Especificacao

Nenhuma linha de codigo Python pode ser escrita antes do preenchimento e aprovacao de um documento de especificacao no diretorio `/.specs/`, usando o template padrao.

#### Passo 2: Test-First (Nyquist Validation)

Testes unitarios e de integracao em AnyIO devem ser escritos **falhando** antes da implementacao. O nome "Nyquist Validation" e uma analogia ao teorema de Nyquist -- voce precisa de pelo menos o dobro da frequencia de amostragem para reconstruir o sinal. Analogamente, voce precisa de testes antes do codigo para reconstruir a intencao.

#### Passo 3: Contrato de Prompt (G/C/FC)

Antes de iniciar qualquer modificacao, o agente deve declarar explicitamente:

| Componente | Significado |
|------------|-------------|
| **Goal** | O que estamos a construir |
| **Constraint** | Que regra arquitetural NAO sera violada |
| **Failure Condition** | Como provaremos se a implementacao falhou |

Isso forca o agente a articular nao apenas o que vai fazer, mas os limites do que nao pode fazer e como sera verificado.

#### Passo 4: Commits Atomicos

Commits pequenos, isolados por funcionalidade e atrelados aos testes correspondentes. A justificativa e pragmatica: permite `git bisect` caso o agente introduza regressoes.

### Invariantes arquiteturais inviolaveis

O CLAUDE.md define 4 regras que o agente nunca pode violar, independente do contexto:

| Invariante | Regra |
|-----------|-------|
| **Isolamento de Adapters** | Adapters concretos (LiteLLM, Gemini, OpenAI, Jinja) NUNCA vazam para `miniautogen/core/`. O dominio comunica APENAS atraves de Protocols tipados |
| **PipelineRunner unico** | O PipelineRunner e o unico executor oficial. Proibido criar loops de execucao paralelos |
| **AnyIO canonico** | Codigo bloqueante (sincrono) no fluxo principal e terminantemente proibido |
| **Policies event-driven** | ExecutionPolicies operam lateralmente. O Core emite eventos, as policies observam e reagem |

### Condicoes de rejeicao imediata

4 situacoes que causam rejeicao automatica do trabalho:

1. Introduzir logica de provedores externos no `core` ou modificar `core/contracts` sem tipagem forte
2. Criar classe de erro fora da Taxonomia Canonica (`transient`, `permanent`, `validation`, `timeout`, `cancellation`, `adapter`, `configuration`, `state_consistency`)
3. Declarar conclusao sem testes passando a 100%
4. Omitir emissao de `ExecutionEvent` apos adicionar componente ao ciclo de vida

### Declaracao de autonomia

O contrato inclui uma clausula notavel:

> *Se a sua janela de contexto comecar a ficar saturada de erros ou loops de debugging infinitos, PARE. Faca um sumario do estado atual, crie um checkpoint de codigo e solicite ao operador humano um reset da sessao.*

Isso reconhece explicitamente que agentes de IA tem limites. Em vez de deixar o agente degradar silenciosamente, o contrato o instrui a **reconhecer a degradacao e parar**. E raro ver essa honestidade num contrato de prompt -- a maioria assume (incorretamente) que o agente pode resolver qualquer coisa se tentar o suficiente.

---

## 8. Regra dos 3 arquivos (Ring Orchestrator)

### A regra

O agente orquestrador **NAO** deve ler/editar mais de 3 arquivos diretamente. Acima de 3 arquivos, ele deve despachar um agente especialista para a tarefa.

### Por que 3?

O numero nao e arbitrario. Ele reflete uma observacao empirica sobre agentes de IA: quando um agente manipula muitos arquivos simultaneamente, a qualidade de cada operacao individual degrada. O agente perde contexto sobre as interdependencias, introduz inconsistencias entre arquivos e tende a fazer mudancas "quase certas" em vez de "corretas".

3 arquivos e o limiar onde um agente consegue manter todas as relacoes em "memoria de trabalho" sem degradacao perceptivel.

### O anti-padrao que previne

O anti-padrao mais perigoso e o racionalizacao: **"this task is small"**. O agente quer simplificar e argumenta que a tarefa e pequena o suficiente para nao precisar de delegacao. A regra e explicita: **tamanho e irrelevante, contagem > 3 = agent**.

Isso previne o que em engenharia de software se chama de "scope creep silencioso" -- a tarefa comeca com 2 arquivos, mas cada um depende de mais um, e em 10 minutos o agente esta editando 8 arquivos sem ter delegado.

### Impacto na arquitetura de agentes

A regra dos 3 arquivos tem uma consequencia arquitetural profunda: ela forca o desenvolvimento de capacidades de **delegacao e paralelismo**. O agente orquestrador nao pode ser um "faz-tudo" -- ele precisa saber decompor tarefas, identificar dependencias e orquestrar execucao distribuida.

Isso espelha a propria filosofia do MiniAutoGen: "O agente e commodity. O runtime e o produto." O agente orquestrador nao e o que faz o trabalho -- e o que coordena quem faz.

---

## 9. Tecnicas de qualidade transversais

As secoes anteriores descrevem componentes individuais do ambiente. Esta secao compila as **tecnicas transversais** que emergem da interacao entre esses componentes. Sao padroes que nenhum componente implementa sozinho, mas que o sistema como um todo produz.

### 9.1 Brainstorming antes de implementar

**Origem:** Skill `brainstorming` (Superpowers)

**Tecnica:** Refinamento socratico. O agente nao pode ir direto para a solucao. Ele deve explorar o espaco do problema, questionar suposicoes e considerar alternativas antes de comecar a implementar.

**O que previne:** Overengineering (a primeira solucao que o agente imagina tende a ser a mais complexa) e prematuridade (comecar a codar antes de entender o problema).

**Na pratica:** Antes de implementar um novo RuntimeInterceptor, o agente primeiro questiona: "Isso e realmente um interceptor? Ou e uma policy? Qual a diferenca neste contexto? O que acontece se eu fizer isso como policy?"

### 9.2 TDD mandatorio

**Origem:** Skill `test-driven-development` (Superpowers) + CLAUDE.md (Passo 2)

**Tecnica:** RED-GREEN-REFACTOR sem excecoes. O teste falhando e escrito primeiro, depois a implementacao minima para passar, depois a refatoracao.

**O que previne:** Codigo sem testes (o modo de falha mais comum de agentes de IA) e testes que testam a implementacao em vez do comportamento (escritos depois do codigo, acabam testando o que foi feito, nao o que deveria ter sido feito).

**Reforco duplo:** A tecnica aparece em dois lugares (skill + contrato), garantindo que mesmo se o agente ignorar um, o outro captura.

### 9.3 Verificacao antes de completar

**Origem:** Skill `verification-before-completion` (Superpowers) + CLAUDE.md (Condicao de rejeicao 3)

**Tecnica:** O agente deve apresentar **evidencia** de que a tarefa funciona. Nao basta dizer "implementado" -- ele precisa mostrar testes passando, output esperado ou outra verificacao tangivel.

**O que previne:** O modo de falha mais sutil de agentes de IA: declarar conclusao prematuramente. O agente tem um vies forte para "parecer produtivo" e frequentemente declara tarefas concluidas que na verdade tem bugs ou incompletudes.

### 9.4 Code review em 3 eixos paralelos

**Origem:** Skill `requesting-code-review` (Superpowers) + sistema de delegacao multi-modelo

**Tecnica:** Tres reviewers avaliam o mesmo codigo simultaneamente, cada um com foco diferente:

| Reviewer | Foco |
|----------|------|
| **Code Quality** | Estrutura, legibilidade, padroes |
| **Business Logic** | Corretude do comportamento, edge cases |
| **Security** | Vulnerabilidades, input validation, auth |

**O que previne:** Review unidimensional. Um unico reviewer tende a focar no que conhece melhor e ignorar dimensoes fora da sua especialidade. Tres reviewers paralelos garantem cobertura completa.

### 9.5 Delegacao multi-modelo

**Origem:** Sistema Codex MCP + regras de delegacao

**Tecnica:** Usar um segundo modelo (GPT-5.2) para perspectiva fresca quando o modelo principal (Claude Opus 4.6) esta preso ou enviesado.

**O que previne:** Loops de raciocinio. Modelos de IA desenvolvem "vicios" -- tendem a abordar problemas da mesma forma repetidamente. Um segundo modelo traz uma perspectiva completamente diferente.

**Quando ativa:** Automaticamente apos 2+ tentativas falhadas, ou quando o usuario explicitamente pede.

### 9.6 Memoria de feedback

**Origem:** Sistema de memoria persistente

**Tecnica:** Registrar tanto correcoes ("nao faca X") quanto confirmacoes ("essa abordagem funcionou bem"). Nao apenas erros.

**O que previne:** Drift comportamental. Agentes que so registram erros ficam progressivamente mais conservadores, evitando abordagens que funcionam porque parecem similares a algo que uma vez falhou. O feedback bidirecional mantem o equilibrio.

### 9.7 Duvida estruturada

**Origem:** Skill `systematic-debugging` (Superpowers) + contrato de prompt

**Tecnica:** 5 niveis de resolucao antes de perguntar ao humano:

1. **Releitura**: Reler o codigo e as mensagens de erro com atencao
2. **Contexto expandido**: Buscar arquivos relacionados, testes existentes
3. **Hipotese**: Formular hipotese especifica sobre a causa
4. **Teste da hipotese**: Verificar a hipotese com evidencia
5. **Escalar**: So perguntar ao humano se os 4 niveis anteriores falharam

**O que previne:** Dois extremos: o agente que pergunta demais (interrompendo o humano a cada duvida) e o agente que nunca pergunta (tentando indefinidamente resolver sozinho).

### 9.8 Plan mode por padrao

**Origem:** `settings.json` (`"defaultMode": "plan"`)

**Tecnica:** O agente propoe acoes e aguarda aprovacao antes de executar.

**O que previne:** Acoes irreversiveis sem consentimento. O agente pode propor `git push --force` ou apagar um diretorio -- mas nao pode executar sem o humano aprovar.

**Trade-off:** Mais seguro, mas mais lento. O desenvolvedor precisa aprovar cada acao, o que adiciona friccao ao fluxo. A escalacao temporaria para modo `act` e possivel para sequencias confiadas.

### 9.9 Skill-first

**Origem:** Mecanismo de invocacao de skills (Superpowers)

**Tecnica:** Processo antes de acao, sempre. O agente verifica se alguma skill e aplicavel ANTES de tomar qualquer acao.

**O que previne:** Acao impulsiva. O modo de falha mais natural de um agente de IA e "entender o pedido e comecar a fazer". Skills interceptam esse impulso e forcam reflexao processual.

**Analogia:** Como um cirurgiao que verifica o checklist da OMS antes de cada operacao -- mesmo que "ja saiba" o que fazer.

### 9.10 3-file gate

**Origem:** Ring Orchestrator

**Tecnica:** Contagem de arquivos como gatilho automatico de delegacao. Mais de 3 = despachar agente.

**O que previne:** Monolithic agent behavior -- um unico agente tentando fazer tudo, perdendo contexto e qualidade a cada arquivo adicional.

### Tabela resumo

| # | Tecnica | Componente de origem | Modo de falha prevenido |
|---|---------|---------------------|------------------------|
| 1 | Brainstorming socratico | Superpowers | Overengineering, prematuridade |
| 2 | TDD mandatorio | Superpowers + CLAUDE.md | Codigo sem testes |
| 3 | Verificacao antes de completar | Superpowers + CLAUDE.md | Conclusao prematura |
| 4 | Code review 3 eixos | Superpowers + Codex MCP | Review unidimensional |
| 5 | Delegacao multi-modelo | Codex MCP | Loops de raciocinio |
| 6 | Memoria de feedback | Sistema de memoria | Drift comportamental |
| 7 | Duvida estruturada | Superpowers + CLAUDE.md | Dependencia excessiva do humano |
| 8 | Plan mode padrao | settings.json | Acoes irreversiveis |
| 9 | Skill-first | Superpowers | Acao impulsiva |
| 10 | 3-file gate | Ring Orchestrator | Monolithic agent behavior |

---

## 10. Percepcao critica e oportunidades

### O que funciona excepcionalmente bem

#### Separacao entre execucao e consultoria

A divisao Claude (executor) / GPT (consultor) e elegante e eficaz. O Claude tem o contexto completo do repositorio e executa operacoes. O GPT traz perspectiva fresca sem vieses acumulados. Cada modelo faz o que faz melhor.

A sinergia nao e obvia: nao se trata de "dois modelos sao melhores que um". Se trata de que dois modelos com **papeis diferentes** se complementam de formas que um unico modelo, mesmo mais poderoso, nao consegue replicar. O executor acumula contexto mas tambem vieses. O consultor nao tem contexto mas tambem nao tem vieses. A combinacao produz resultados superiores a ambos isoladamente.

#### Skills como sistema imunologico

As skills do Superpowers funcionam como um sistema imunologico para o desenvolvimento: elas detectam e neutralizam padroes perigosos (acao impulsiva, conclusao prematura, debugging por tentativa) antes que causem dano. O fato de serem invocadas automaticamente -- e nao por decisao do agente -- e o que as torna eficazes.

Um agente que pode decidir "nao preciso de TDD para isso" vai, eventualmente, decidir errado. Um agente que NAO pode decidir nao erra nessa dimensao.

#### Contrato constitucional (CLAUDE.md)

O CLAUDE.md e mais sofisticado que a maioria dos prompts de sistema. Ele nao apenas instrui -- ele define invariantes inviolaveis, condicoes de rejeicao e uma clausula de auto-reconhecimento de limites. A combinacao de regras positivas ("faca isso") com regras negativas ("NUNCA faca isso") e com mecanismos de auto-regulacao ("quando estiver saturado, pare") e rara e eficaz.

#### Memoria como acumulador de sabedoria

O sistema de memoria nao tenta armazenar tudo -- ele armazena **decisoes**. Isso e uma distincao critica. Decisoes sao estaveis e reutilizaveis; implementacoes sao volateis e descartaveis. O resultado e um agente que "lembra" do que importa sem ficar sobrecarregado com detalhes obsoletos.

### Onde ha potencial de melhoria

#### O diretorio `.specs/` referenciado mas inexistente

O CLAUDE.md instrui: "Nenhuma linha de codigo Python pode ser escrita antes do preenchimento e aprovacao do documento de especificacao (use `/.specs/template.md`)." No entanto, o diretorio `.specs/` e o template nao existem no repositorio. Isso cria uma desconexao entre o contrato e a realidade -- o agente e instruido a seguir um processo cujo artefato de entrada nao existe.

**Impacto:** Medio. O agente pode (e provavelmente vai) interpretar a ausencia como "esse processo nao esta ativo" e pular a etapa de especificacao. Isso invalida o primeiro passo do workflow mandatorio.

**Acao sugerida:** Criar `/.specs/template.md` com um template minimo ou remover/atualizar a referencia no CLAUDE.md.

#### Layer 3 canonical patterns pendentes

A documentacao de arquitetura do agente (`07-agent-anatomy.md`) descreve 5 layers do Agent, sendo a Layer 3 (Agent Runtime -- tools, memory, hooks, delegation) identificada como "O DIFERENCIAL". Porem, os padroes canonicos para essa layer ainda nao estao implementados. O runtime do agente e conceitual mas nao tem patterns de referencia que o agente de IA possa seguir.

**Impacto:** Alto para contribuicoes futuras. Sem canonical patterns, cada implementacao de Layer 3 sera ad-hoc, potencialmente violando a consistencia arquitetural.

#### Ausencia de metricas de eficacia

O ambiente e sofisticado mas nao mede sua propria eficacia. Nao ha registro de:
- Quantas vezes cada skill foi invocada
- Taxa de sucesso de delegacoes multi-modelo
- Frequencia de uso de memorias
- Reducao de bugs vs baseline sem o ambiente

Sem metricas, e impossivel saber quais componentes adicionam valor e quais adicionam complexidade sem retorno.

**Acao sugerida:** Implementar logging minimo para invocacoes de skills e delegacoes, permitindo analise retrospectiva de eficacia.

#### Complexidade de onboarding

O ambiente tem 18 plugins ativados, 3 MCP servers, 4 arquivos de regras de delegacao, um contrato constitucional e um sistema de memoria. Para um novo desenvolvedor que queira replicar o setup, a curva de aprendizado e significativa.

Nao ha um `setup.sh` ou guia de instalacao que reproduza o ambiente. Cada componente precisa ser configurado manualmente com conhecimento previo das ferramentas.

**Acao sugerida:** Criar um script de bootstrap ou, no minimo, um checklist de configuracao.

#### Potencial de conflito entre skills e rings

Com 10 skills do Superpowers e 9 rings ativados simultaneamente, ha potencial de conflito ou redundancia. Por exemplo, o TDD mandatorio do Superpowers e o gate de testing do `ring-dev-team` podem impor requisitos conflitantes ou redundantes.

Nao ha documentacao explicita sobre precedencia ou resolucao de conflitos entre skills de diferentes fontes.

### O balanco entre automacao e controle humano

O ambiente atinge um equilibrio notavel:

| Dimensao | Automatizado | Controle humano |
|----------|-------------|-----------------|
| **Processo** | Skills invocadas automaticamente | Humano pode overrider |
| **Execucao** | Plan mode propoe, humano aprova | Modo `act` disponivel |
| **Consultoria** | Triggers proativos para GPT | Humano pode pedir explicitamente |
| **Memoria** | Index carregado automaticamente | Humano decide o que salvar |
| **Delegacao** | 3-file gate automatico | Humano pode forcar agente unico |

O padrao e **automacao com supervisao**. O sistema faz o maximo que pode automaticamente, mas o humano sempre tem a palavra final. Isso e mais maduro que os dois extremos (automacao total vs controle total) e reflete uma compreensao realista do estado atual dos agentes de IA: poderosos o suficiente para serem uteis, nao confiaveis o suficiente para serem autonomos.

### A sinergia multi-LLM como modelo de trabalho

O uso de Claude (execucao) + GPT (consultoria) nao e apenas uma escolha tecnica -- e um modelo de trabalho que espelha praticas de engenharia humana. Em equipes de software, o desenvolvedor que implementa raramente e o mesmo que revisa. O reviewer traz perspectiva fresca e detecta problemas que o implementador nao ve.

A aplicacao desse principio a agentes de IA e uma inovacao pratica com implicacoes amplas:

1. **Desacoplamento de vieses**: Cada modelo tem vieses diferentes. Usa-los em sequencia (implementacao → revisao) cancela vieses mutuos.

2. **Especializacao economica**: GPT-5.2 via Codex e usado apenas para consultoria de alto valor (arquitetura, seguranca, code review). O volume de execucao fica com Claude. Isso otimiza custo por qualidade.

3. **Escalacao natural**: Quando Claude nao consegue resolver algo apos 2 tentativas, a escalacao para GPT nao e uma admissao de falha -- e um processo padrao. Isso remove o estigma da escalacao e torna o fluxo mais saudavel.

4. **Verificacao cruzada**: O fato de dois modelos diferentes concordarem sobre uma abordagem aumenta significativamente a confianca na corretude.

O modelo multi-LLM deste ambiente pode ser a tecnica mais inovadora de todo o setup. Enquanto a industria debate qual modelo e "melhor", este ambiente demonstra que a pergunta certa nao e "qual modelo usar" mas "como combinar modelos para compensar mutuamente suas fraquezas".

---

## Apendice A: Topologia completa do ambiente

```
Ambiente de Desenvolvimento (Claude Code)
│
├── Modelo Principal: Claude Opus 4.6 (1M context)
│   ├── Modo padrao: plan
│   └── Permissoes: whitelist minima (ls, python3.13)
│
├── Skills (Superpowers v4.3.1)
│   ├── brainstorming (flexible)
│   ├── test-driven-development (rigid)
│   ├── systematic-debugging (rigid)
│   ├── verification-before-completion (rigid)
│   ├── writing-plans (flexible)
│   ├── executing-plans (flexible)
│   ├── dispatching-parallel-agents (flexible)
│   ├── subagent-driven-development (flexible)
│   ├── receiving-code-review (rigid)
│   └── requesting-code-review (rigid)
│
├── Ring Teams (9 times)
│   ├── ring-default
│   ├── ring-dev-team (v0.42.0) — 6 gates
│   ├── ring-pm-team — 9 gates
│   ├── ring-tw-team
│   ├── ring-ops-team
│   ├── ring-finance-team
│   ├── ring-finops-team
│   ├── ring-pmm-team
│   └── ring-pmo-team
│
├── MCP Servers
│   ├── Codex (GPT-5.2) — delegacao multi-modelo
│   ├── Cloudflare — infraestrutura
│   └── Hetzner — cloud management
│
├── Delegacao Multi-Modelo
│   ├── Architect
│   ├── Plan Reviewer
│   ├── Scope Analyst
│   ├── Code Reviewer
│   └── Security Analyst
│
├── Memoria Persistente
│   ├── MEMORY.md (index automatico)
│   ├── project_backend_drivers.md
│   ├── project_milestone1_sdk.md
│   ├── project_milestone2_cli.md
│   ├── project_strategic_vision.md
│   └── project_tui_dash.md
│
├── Contrato (claude.md)
│   ├── Spec-Driven Development (4 passos)
│   ├── 4 invariantes inviolaveis
│   ├── 4 condicoes de rejeicao
│   └── Declaracao de autonomia
│
└── Plugins Adicionais (8)
    ├── claude-delegator
    ├── frontend-design
    ├── github
    ├── playwright
    ├── supabase
    ├── claude-md-management
    ├── rust-analyzer-lsp
    └── superpowers (marketplace)
```

---

## Apendice B: Fluxo de uma tarefa tipica

Para ilustrar como todos esses componentes interagem, aqui esta o fluxo de uma tarefa real: "Implementar RuntimeInterceptor para o MiniAutoGen".

```
1. [USUARIO] "Implemente RuntimeInterceptor"
   │
2. [SKILL-FIRST] Skill brainstorming ativada automaticamente
   │ → Refinamento socratico: "O que e um interceptor neste contexto?"
   │ → "Qual a diferenca entre interceptor e policy?"
   │ → "Que padroes existem (Tapable, Express middleware)?"
   │ → Decisao informada sobre o design
   │
3. [TRIGGER PROATIVO] Decisao de arquitetura detectada
   │ → Delega ao Architect (GPT-5.2) para validar o design
   │ → Formato de 7 secoes, modo Advisory (read-only)
   │ → Claude sintetiza a resposta (nunca mostra output bruto)
   │
4. [CONTRATO G/C/FC] Declaracao obrigatoria:
   │ → Goal: Implementar RuntimeInterceptor com hooks Waterfall/Bail/Series
   │ → Constraint: Nao violar isolamento de adapters, usar AnyIO
   │ → Failure Condition: Testes de interceptacao falhando ou event leaks
   │
5. [SPEC-DRIVEN] Verificar /.specs/ para template (NOTA: nao existe)
   │
6. [TDD] Skill test-driven-development ativada (rigid)
   │ → Escrever testes falhando para interceptors
   │ → Implementacao minima
   │ → Refatoracao
   │
7. [3-FILE GATE] Se > 3 arquivos envolvidos
   │ → Despachar agente especialista
   │ → Orquestrador acompanha sem editar diretamente
   │
8. [PLAN MODE] Cada acao proposta e aprovada pelo humano
   │
9. [CODE REVIEW] Skill requesting-code-review ativada
   │ → 3 reviewers paralelos (code, business-logic, security)
   │ → Se necessario, delega review ao Code Reviewer GPT
   │
10. [VERIFICACAO] Skill verification-before-completion ativada
    │ → Evidencia: testes passando, output demonstrado
    │ → Sem evidencia = tarefa nao concluida
    │
11. [MEMORIA] Decisoes arquiteturais salvas em project memory
    │ → "RuntimeInterceptor usa padrao Tapable com 3 hook types"
    │ → Disponivel em sessoes futuras
    │
12. [COMMIT] Atomic commit atrelado aos testes
```

Este fluxo envolve **7 componentes diferentes** do ambiente interagindo em sequencia. Nenhum componente sozinho garante qualidade -- e a orquestracao entre eles que produz o resultado.

---

## Apendice C: Configuracao de referencia

Para replicar este ambiente, os seguintes arquivos devem ser configurados:

| Arquivo | Localizacao | Funcao |
|---------|-------------|--------|
| `settings.json` | `~/.claude/settings.json` | Permissoes, plugins, MCP servers |
| `claude.md` | Raiz do repositorio | Contrato constitucional |
| `MEMORY.md` | `~/.claude/projects/*/memory/` | Index de memoria |
| Regras de delegacao | `~/.claude/rules/delegator/` | 4 arquivos: orchestration, model-selection, triggers, delegation-format |
| Memorias de projeto | `~/.claude/projects/*/memory/` | Decisoes e convencoes |

### Hierarquia de configuracao

```
~/.claude/
├── settings.json                    # Global: plugins, MCP servers, permissoes
├── rules/
│   └── delegator/                   # Global: regras de delegacao multi-modelo
│       ├── orchestration.md         # Como delegar (7 passos)
│       ├── model-selection.md       # Quando usar cada especialista
│       ├── triggers.md              # Triggers proativos e reativos
│       └── delegation-format.md     # Formato de 7 secoes
└── projects/
    └── -Users-*-Projects-miniAutoGen/
        └── memory/                  # Por projeto: decisoes e convencoes
            ├── MEMORY.md
            └── project_*.md

<repositorio>/
└── claude.md                        # Por repositorio: contrato constitucional
```

A hierarquia e deliberada: configuracoes globais (plugins, MCP) ficam em `~/.claude/`, convencoes de delegacao ficam em `~/.claude/rules/`, memorias de projeto ficam no diretorio do projeto, e o contrato constitucional fica na raiz do repositorio (versionado no git).

---

*Documento gerado como analise do ambiente de desenvolvimento do MiniAutoGen. Reflete a configuracao observada em marco de 2026.*
