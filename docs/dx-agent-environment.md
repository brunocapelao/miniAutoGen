# Ambiente de desenvolvimento com agentes: configuracao, ferramentas e tecnicas para DX de qualidade

> **Analise de ambiente** -- Como um setup de desenvolvimento orientado a agentes de IA transforma a relacao entre humano, codigo e qualidade de software.

**Contexto:** Este documento captura e analisa o ambiente de desenvolvimento configurado em torno do repositorio MiniAutoGen -- um framework Python microkernel para orquestracao multi-agente. O foco nao e tutorial ("como configurar"), mas percepcao ("o que esta configurado, por que funciona, e que tecnicas emergem desse design").

**Audiencia:** Desenvolvedores e tech leads que querem entender como estruturar um ambiente de desenvolvimento assistido por agentes de IA com controle de qualidade real -- nao apenas "vibes".

**Data de referencia:** Marco de 2026.

**Premissa:** O desenvolvimento assistido por agentes de IA esta em transicao de "ferramenta de produtividade" para "modo de operacao". A diferenca e fundamental: uma ferramenta complementa o workflow existente; um modo de operacao substitui o workflow inteiro. Este documento analisa um ambiente que opera no segundo paradigma.

---

## Sumario

- [1. Visao geral do ambiente](#1-visao-geral-do-ambiente)
- [2. Sistema de skills (Superpowers + Ring)](#2-sistema-de-skills-superpowers--ring)
- [3. Delegacao multi-modelo (Codex MCP)](#3-delegacao-multi-modelo-codex-mcp)
- [4. Sistema de memoria persistente](#4-sistema-de-memoria-persistente)
- [5. Hooks e automacao](#5-hooks-e-automacao)
- [5.1. Enforcement programatico: linter arquitetural e CI](#51-enforcement-programatico-linter-arquitetural-e-ci)
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

A whitelist de permissoes e granular: 13 padroes cobrindo operacoes de leitura (`cat`, `find`, `grep`, `ls`, `wc`, `tree`), git, toolchain Python (`python`, `pytest`, `ruff`, `mypy`, `pip`) e build (`make`). Cada padrao usa o formato `Bash(comando:*)`, permitindo qualquer argumento para o comando aprovado. Operacoes fora dessa lista (como `rm`, `curl`, `docker`) continuam exigindo aprovacao explicita. A configuracao fica em `.claude/settings.local.json`, separada da configuracao global -- permitindo que cada desenvolvedor ajuste permissoes sem afetar o repositorio.

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

O MiniAutoGen e um framework Python orientado a **Microkernel** para orquestracao de flows e agentes assincronos. A arquitetura atual tem ~15.000+ LOC distribuidos em 4 camadas:

| Camada | Responsabilidade | Modulos |
|--------|------------------|---------|
| **Core/Kernel** | Contratos, eventos, runtimes de coordenacao | `core/contracts/`, `core/events/`, `core/runtime/` |
| **Policies** | Regras transversais (retry, budget, approval, timeout) | `policies/` |
| **Adapters** | Engine Drivers, templates, LLM providers | `backends/`, `adapters/` |
| **Shell** | CLI, TUI Dashboard, Server | `cli/`, `tui/`, `app/` |

A complexidade do repositorio e relevante para entender o ambiente: nao se trata de um projeto simples onde "qualquer LLM resolve". A separacao rigorosa de responsabilidades, os 63 tipos de evento (expandindo para 69 com o AgentRuntime compositor) canonicos, os 4 runtimes de coordenacao e a abstracacao multi-provider criam um contexto onde erros de acoplamento sao faceis de introduzir e dificeis de detectar. O ambiente de desenvolvimento precisa compensar isso.

> **Nota de terminologia (DA-9):** O código interno usa `PipelineRunner` e `backends/` como nomes de classes e módulos. Na terminologia pública, estes correspondem a "Flow runtime" e "Engine drivers" respectivamente. Ver [README estratégico](pt/README.md) para o mapeamento completo.

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

#### O paradoxo da autonomia controlada

Skills criam um paradoxo produtivo: o agente e **mais autonomo** precisamente porque e **mais controlado**. Sem skills, o agente precisa de supervisao humana constante porque seu processo e imprevisivel. Com skills, o processo e previsivel, e o humano pode confiar na execucao sem microgerenciar.

E como a diferenca entre um estagiario e um senior: o estagiario precisa de supervisao porque voce nao sabe que processo ele vai seguir. O senior pode trabalhar autonomamente porque voce sabe que ele vai seguir o processo correto. Skills transformam o agente de "estagiario imprevisivel" em "junior com processo rigoroso".

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
- Avaliar impacto no sistema de eventos canonicos (63 tipos de evento, expandindo para 69 com o AgentRuntime compositor)
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

### Exemplo de memoria eficaz vs ineficaz

**Memoria EFICAZ** (decisao estrategica):
```yaml
---
name: strategic-vision-2025-06
type: project
---
## Strategic Positioning (decided 2025-06-18)
Core thesis: "O agente e commodity. O runtime e o produto."
MiniAutoGen does NOT reinvent the agent. It orchestrates agents from
any provider in customizable Flows with interceptors, policies, and
composable coordination.
```

Esta memoria e valiosa porque captura uma **decisao estrategica** que influencia todas as implementacoes futuras. Quando o agente precisa decidir se deve adicionar uma feature ao Agent ou ao Flow, essa memoria o orienta: "o runtime e o produto, nao o agente".

**Memoria INEFICAZ** (que seria um erro salvar):
```markdown
## Como fix o bug do TypeAdapter em policy.py
1. O erro era na linha 42 de policies/retry.py
2. Troquei TypeAdapter(dict) por TypeAdapter(Dict[str, Any])
3. Testes passaram apos o fix
```

Esta "memoria" e inutil porque: (a) o fix e especifico demais para ser reutilizavel, (b) a informacao esta no git log, e (c) o contexto pode mudar (a linha 42 pode nao existir mais). Salvar isso poluiria o sistema de memoria com ruido.

### Escala e governanca da memoria

Com 5 memorias de projeto ativas, o sistema ainda e gerenciavel. Mas o design levanta uma questao de escala: o que acontece quando o projeto tem 50 memorias? 200?

O MEMORY.md atual serve como indice plano. Nao ha hierarquia, tags, ou mecanismo de expiracao. Para projetos de longo prazo, isso pode se tornar um gargalo -- o agente carrega todas as memorias no contexto, mesmo as irrelevantes para a tarefa atual.

Uma solucao potencial seria memoria hierarquica:
- **Sempre carregada**: Decisoes estrategicas e convencoes canonicas
- **Sob demanda**: Decisoes de projeto especificas (carregadas quando o agente trabalha na area relevante)
- **Arquivada**: Decisoes de milestones concluidos (acessiveis mas nao injetadas automaticamente)

### Tecnica-chave: memoria de feedback bidirecional

A memoria de feedback captura tanto **correcoes** ("nao faca X") quanto **confirmacoes** ("essa abordagem funcionou bem"). A maioria dos sistemas so registra erros. Ao registrar tambem acertos, o agente aprende nao apenas o que evitar, mas o que replicar.

Isso previne **drift** -- a tendencia de um agente corrigido em excesso a se afastar gradualmente de comportamentos corretos por medo de repetir erros antigos.

### Captura automatica de artefatos git

O hook `session-end.sh` automatiza parte do ciclo de vida da memoria. Ao final de cada sessao, ele:

1. Identifica commits feitos durante a sessao (usando o marcador de `session-start.sh`)
2. Captura diff stats de mudancas pendentes (staged e unstaged)
3. Gera um arquivo de memoria com frontmatter YAML valido
4. Adiciona a entrada no index `MEMORY.md` automaticamente

O resultado e um registro cronologico de atividade por sessao -- util para rastrear progresso e retomar trabalho interrompido. A limitacao e que o hook captura apenas **artefatos** (o que mudou), nao **raciocinio** (por que mudou). Decisoes estrategicas continuam exigindo registro manual.

### Ciclo de vida da memoria

As memorias nao sao estaticas. Elas passam por um ciclo:

1. **Criacao automatica**: O hook de `SessionEnd` gera memorias de sessao com artefatos git
2. **Criacao manual**: O agente ou o humano registra decisoes estrategicas e convencoes
3. **Injecao**: Em sessoes futuras, o MEMORY.md carrega a referencia
4. **Aplicacao**: O agente usa a memoria para tomar decisoes consistentes
5. **Atualizacao**: Se a decisao muda, a memoria e atualizada (nao duplicada)
6. **Arquivamento**: Memorias de milestones concluidos podem ser arquivadas

O passo 5 e critico e frequentemente negligenciado. Memorias desatualizadas sao piores que a ausencia de memoria -- elas guiam o agente na direcao errada com a confianca de que esta seguindo uma decisao validada.

A pratica observada neste ambiente e que memorias sao atualizadas quando convencoes mudam (como a renomeacao de Pipeline para Flow, Project para Workspace). O frontmatter nao inclui data de criacao, o que torna dificil identificar memorias potencialmente obsoletas.

---

## 5. Hooks e automacao

### Pipeline de 3 hooks

O ambiente configura 3 lifecycle hooks em `.claude/settings.json`, cobrindo o ciclo completo de uma sessao de desenvolvimento:

| Hook | Evento | Script | Funcao |
|------|--------|--------|--------|
| **SessionStart** | Inicio de sessao | `scripts/hooks/session-start.sh` | Salva o HEAD atual como marcador de sessao |
| **SessionEnd** | Fim de sessao | `scripts/hooks/session-end.sh` | Gera memoria automatica com artefatos git |
| **UserPromptSubmit** | Cada prompt do usuario | `scripts/hooks/pre-prompt.sh` | Injeta contexto git conciso (branch, arquivos modificados, ultimo commit) |

A configuracao em `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{ "type": "command", "command": "scripts/hooks/session-start.sh" }],
    "SessionEnd": [{ "type": "command", "command": "scripts/hooks/session-end.sh" }],
    "UserPromptSubmit": [{ "type": "command", "command": "scripts/hooks/pre-prompt.sh" }]
  }
}
```

### SessionStart: marcador de sessao

O `session-start.sh` e minimo e intencional: salva o commit `HEAD` atual num arquivo marcador (`.claude/.session-start-commit`). Esse marcador permite que o hook de `SessionEnd` calcule exatamente quais commits pertencem a sessao que esta encerrando.

### UserPromptSubmit: contexto git continuo

O `pre-prompt.sh` executa a cada prompt do usuario e injeta um bloco conciso de contexto git:

```
Branch: feat/engine-v2
Modified: 4 files (2 staged, 2 unstaged)
Last commit: 9ced23f feat(tui): show discovered engines alongside YAML engines
```

Isso resolve um problema sutil: em sessoes longas, o agente perde nocao do estado do repositorio. Com o hook de pre-prompt, cada interacao comeca com informacao atualizada sobre branch, arquivos modificados e ultimo commit. O agente nao precisa rodar `git status` manualmente -- a informacao chega proativamente.

### SessionEnd: memoria automatica de artefatos git

O `session-end.sh` e o hook mais sofisticado. Ele:

1. Compara o `HEAD` atual com o marcador salvo no `SessionStart`
2. Coleta todos os commits feitos durante a sessao (`git log --oneline`)
3. Captura diff stats de mudancas nao comitadas (staged e unstaged)
4. Gera um arquivo de memoria com frontmatter YAML valido
5. Adiciona uma entrada no `MEMORY.md` (index) automaticamente

O arquivo gerado segue o formato:

```yaml
---
name: session-2026-03-18_14-30
description: "Session on feat/engine-v2 with 3 commit(s) + uncommitted changes"
type: project
---
```

**Limitacao documentada:** O hook captura apenas artefatos git (commits, diffs). Ele NAO captura raciocinio, decisoes ou contexto conversacional. Decisoes estrategicas ainda precisam ser salvas manualmente pelo agente ou pelo humano. Essa limitacao e intencional -- capturar raciocinio exigiria acesso ao historico da conversa, que nao esta disponivel via hooks de shell.

**Condicionalidade:** O hook so gera memoria se houve atividade na sessao (commits ou mudancas pendentes). Sessoes de consulta pura (leitura sem escrita) nao produzem artefatos de memoria desnecessarios.

### A filosofia dos hooks: contexto e registro, nao enforcement

Os 3 hooks seguem uma filosofia coerente: eles fornecem **contexto** (pre-prompt) e **registro** (session-start/end), mas nao fazem **enforcement**. Nao ha hooks que bloqueiem commits, rodem linters ou impeçam acoes.

O enforcement neste ambiente e feito em camadas superiores: skills do Superpowers forcam TDD e verificacao, o modo `plan` impede execucao nao aprovada, e o linter arquitetural (`scripts/check_arch.py`) valida invariantes programaticamente. A redundancia de ter hooks de enforcement ALEM desses mecanismos seria contraproducente.

### Implicacoes para reprodutibilidade

Os hooks sao scripts shell puros (sem dependencias externas) e estao versionados no repositorio. Um novo desenvolvedor que clona o repositorio e tem `.claude/settings.json` configurado recebe automaticamente os 3 hooks. A unica dependencia e git, que e prerequisito do proprio repositorio.

---

## 5.1. Enforcement programatico: linter arquitetural e CI

### O problema que resolve

As invariantes arquiteturais do CLAUDE.md (secao 3) sao regras textuais que dependem do agente interpreta-las e segui-las. Isso funciona na maioria dos casos, mas falha quando: (a) o agente racionaliza uma excecao ("esse import e temporario"), (b) o agente desconhece uma violacao indireta (um import transitivo que vaza um adapter para o core), ou (c) um agente diferente (Copilot, Gemini) nao carrega o CLAUDE.md com a mesma fidelidade.

O linter arquitetural (`scripts/check_arch.py`) resolve esse problema transformando regras textuais em verificacoes programaticas. As invariantes deixam de ser "instrucoes que o agente deve seguir" e passam a ser "checagens que o CI executa automaticamente".

### O linter: 4 checagens AST

O `check_arch.py` usa apenas stdlib Python (`ast`, `pathlib`, `sys`) -- sem dependencias externas. Isso significa que roda em qualquer ambiente com Python 3.11+, incluindo o CI, sem instalacao de pacotes.

As 4 checagens mapeiam diretamente as 4 invariantes do CLAUDE.md:

| Checagem | Invariante CLAUDE.md | O que verifica | Como verifica |
|----------|---------------------|----------------|---------------|
| `adapter_isolation` | Isolamento de Adapters | `core/` nao importa adapters, backends ou LLM libs | AST: busca imports de `miniautogen.adapters`, `litellm`, `openai`, `google.generativeai`, `anthropic` em `core/` |
| `runner_exclusivity` | PipelineRunner unico | Nenhuma classe fora de `core/runtime/` age como executor paralelo | AST: detecta classes com `run()`/`execute()` que contem `while True` e referenciam `RunContext`/`RunResult` |
| `anyio_compliance` | AnyIO canonico | `core/` nao importa primitivas de concorrencia bloqueantes | AST: busca imports de `threading`, `multiprocessing`, `concurrent.futures` e usos de `asyncio.run`, `asyncio.get_event_loop` |
| `event_emission` | Policies event-driven | Classes de runtime com `run()`/`execute()` emitem eventos | AST: verifica se classes em `core/runtime/` referenciam `ExecutionEvent`, `emit`, `publish` ou `send_event` |

### Output do linter

O output e deliberadamente simples:

```
[PASS] adapter_isolation: core/ has no adapter imports
[PASS] runner_exclusivity: no parallel executors found
[PASS] anyio_compliance: core/ uses only AnyIO for concurrency
[PASS] event_emission: all runtime classes emit events

Result: 0 FAILED, 4 PASSED
```

Em caso de violacao:

```
[FAIL] adapter_isolation:
  miniautogen/core/runtime/workflow.py:12 imports litellm
```

O exit code e 0 (sucesso) ou 1 (falha), permitindo uso direto em CI.

### O que o linter NAO verifica

E importante notar os limites:

- **Nao verifica logica de negocios** -- apenas imports e padroes estruturais
- **Nao verifica testes** -- os testes podem (e devem) importar adapters
- **Nao substitui code review** -- detecta violacoes mecanicas, nao decisoes de design

O linter e a **primeira linha de defesa**, nao a unica. Skills de code review e delegacao ao Code Reviewer GPT continuam essenciais para violacoes que exigem julgamento.

### Pipeline de CI: 3 jobs + gate

O `.github/workflows/ci.yml` implementa integracao continua com 3 jobs paralelos e um gate consolidado:

```
┌─────────┐  ┌─────────┐  ┌──────────────┐
│  lint   │  │  test   │  │  arch-check  │
│         │  │         │  │              │
│ ruff    │  │ pytest  │  │ check_arch.py│
│ mypy    │  │ --cov   │  │ (4 checks)  │
└────┬────┘  └────┬────┘  └──────┬───────┘
     │            │              │
     └────────────┼──────────────┘
                  │
           ┌──────┴──────┐
           │  ci-passed  │
           │  (gate)     │
           └─────────────┘
```

| Job | Ferramentas | O que valida |
|-----|-------------|--------------|
| **lint** | `ruff check` + `mypy` | Estilo de codigo e tipagem estatica |
| **test** | `pytest --cov` | Testes unitarios e cobertura |
| **arch-check** | `python scripts/check_arch.py` | Invariantes arquiteturais |
| **ci-passed** | Gate consolidado | So passa se os 3 jobs passam |

Os 3 jobs rodam em **paralelo** em Ubuntu com Python 3.11, usando Poetry para gerenciamento de dependencias. O job `ci-passed` usa `if: always()` e verifica explicitamente o resultado de cada job -- nao e um simple `needs`, mas uma verificacao ativa que reporta qual job falhou.

### A sinergia entre linter, CI e contrato

O linter arquitetural cria um **ciclo de enforcement** que fecha o loop entre o contrato constitucional e a realidade do codigo:

```
CLAUDE.md (regras textuais)
    │
    ▼
check_arch.py (regras programaticas)
    │
    ▼
ci.yml (execucao automatica)
    │
    ▼
PR bloqueado se falhar
    │
    ▼
Invariante preservada
```

Antes do linter, as invariantes dependiam exclusivamente do agente interpreta-las. Agora, mesmo que um agente (Claude, Copilot, Gemini ou um humano) introduza uma violacao, o CI a detecta antes do merge. Isso e defense in depth aplicada a qualidade arquitetural.

### Consciencia multi-agente

O ambiente agora reconhece explicitamente que multiplos agentes de IA operam no mesmo repositorio. Dois arquivos de instrucoes agente-especificas foram adicionados:

| Arquivo | Agente alvo | Contexto de operacao |
|---------|-------------|---------------------|
| `.github/copilot-instructions.md` | GitHub Copilot | Autocomplete e sugestoes inline no editor |
| `.github/gemini.md` | Gemini CLI | Agente conversacional via terminal |

Ambos seguem o mesmo padrao: resumem as invariantes, condicoes de rejeicao, workflow mandatorio e taxonomia de erros -- tudo referenciando o `CLAUDE.md` como fonte canonica. Nao duplicam regras; apenas adaptam a apresentacao ao contexto de operacao de cada agente.

O `.github/gemini.md` inclui uma instrucao especifica: "Utilize `python scripts/check_arch.py` para validar invariantes antes de declarar tarefas concluidas." Isso integra o linter arquitetural ao workflow de agentes que nao tem acesso nativo ao sistema de skills do Claude Code.

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

### Comparacao de protocolos de comunicacao

Os tres MCP servers usam o mesmo protocolo base (stdio) mas com estrategias de conectividade diferentes:

| Server | Protocolo | Conectividade | Autenticacao | Latencia |
|--------|-----------|---------------|--------------|----------|
| Codex | stdio local | Processo local, sem rede | Implicit (CLI auth) | ~1-5s |
| Cloudflare | stdio → MCP remote | Processo local conecta a API remota | OAuth via `npx mcp-remote` | ~2-10s |
| Hetzner | stdio local | Processo local com API calls | Token em env var | ~1-5s |

A escolha de stdio para todos (em vez de HTTP ou WebSocket) e pragmatica: stdio e o protocolo mais simples e confiavel para comunicacao entre processos locais. A complexidade de rede (quando necessaria) e abstraida pelo proprio MCP server, nao pelo Claude Code.

### Seguranca dos MCP Servers

Um ponto que merece atencao: os MCP servers de infraestrutura (Cloudflare, Hetzner) concedem ao agente acesso a sistemas de producao. O token do Hetzner, por exemplo, esta diretamente no `settings.json`. Em modo `plan`, o agente precisa de aprovacao para executar operacoes, o que mitiga o risco. Mas em modo `act`, o agente poderia teoricamente provisionar ou destruir recursos de infraestrutura sem aprovacao explicita.

A pratica de seguranca aqui e que o modo `plan` atua como guardrail. Mas depende do desenvolvedor nao escalar para `act` durante operacoes de infraestrutura. Isso e um risco gerenciavel, mas documentavel.

### O MCP como padrao de extensibilidade

O Model Context Protocol merece destaque como padrao arquitetural. Cada MCP server adiciona capacidades ao agente sem modificar o agente em si. Isso espelha a arquitetura do proprio MiniAutoGen: interceptors e policies estendem o runtime sem modificar o kernel.

A analogia nao e coincidencia. O ambiente de desenvolvimento foi projetado com a mesma filosofia do produto que desenvolve: **extensibilidade por composicao, nao por modificacao**.

Adicionar um novo MCP server (por exemplo, para um banco de dados, uma ferramenta de monitoramento ou outro provider de cloud) e uma operacao puramente aditiva:

```json
{
  "mcpServers": {
    "novo-servico": {
      "type": "stdio",
      "command": "mcp-novo-servico",
      "env": { "API_KEY": "***" }
    }
  }
}
```

Nenhum plugin, skill ou regra existente precisa ser modificado. O agente ganha a nova capacidade automaticamente.

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

### Convencoes git formalizadas (§5)

O CLAUDE.md agora inclui uma secao dedicada a convencoes git, formalizando praticas que antes eram implicitas:

**Branch naming:**

| Prefixo | Uso |
|---------|-----|
| `feat/` | Nova funcionalidade |
| `fix/` | Correcao de bug |
| `chore/` | Manutencao, refactor, tooling |
| `docs/` | Documentacao |

**Formato de commits:** `type(scope): descricao concisa`

Tipos validos: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`. Scopes validos: `core`, `runtime`, `policies`, `stores`, `adapters`, `cli`, `tui`, `backends`, `events`.

**Estrategia de merge:** Squash para branches de feature (historico limpo), merge commit para releases (historico completo preservado).

A formalizacao e relevante porque agentes de IA tendem a criar commits com mensagens genericas ("update code", "fix bug") ou branches com nomes inconsistentes. Convencoes explicitas garantem que o historico git permanece legivel e `git bisect` continua viavel.

### A infraestrutura agentca como extensao do contrato

O CLAUDE.md nao existe isoladamente. Ele referencia tres outros sistemas que devem funcionar em conjunto:

| Referencia no contrato | Sistema real | Status |
|------------------------|-------------|--------|
| `.memconfig.json` para memoria | Sistema de memoria em `~/.claude/projects/*/memory/` | Funcional |
| `/skills` para scripts pre-aprovados | Skills do Superpowers + Ring | Funcional (via plugins) |
| `.mcp.json` para verificacao autonoma | MCP Servers em `settings.json` | Funcional |
| `/.specs/template.md` para especificacoes | 3 templates + script + 3 slash commands | Funcional |

Todas as 4 referencias do contrato estao funcionais. O sistema de especificacoes, que era a lacuna mais critica (primeiro passo do workflow mandatorio), agora inclui:

- **3 templates**: `.specs/template.md` (especificacao de feature), `.specs/plan-template.md` (plano de implementacao), `.specs/tasks-template.md` (decomposicao em tasks)
- **Script de bootstrap**: `scripts/specs/create-feature.sh` para criar a estrutura de diretorio completa de uma nova feature
- **3 slash commands**: `/spec-create`, `/spec-plan`, `/spec-tasks` -- comandos nativos do Claude Code que guiam o agente na criacao de cada artefato

O template de especificacao inclui o contrato G/C/FC (Goal, Constraint, Failure Condition), user stories, criterios de aceitacao e uma secao explicita de invariantes afetadas com referencia ao CLAUDE.md. Isso fecha o loop entre o contrato constitucional e o processo de especificacao.

### Taxonomia canonica de erros

Um elemento sutil mas importante do contrato e a Taxonomia Canonica de erros. O CLAUDE.md proibe a criacao de classes de erro fora desta taxonomia:

| Categoria | Significado | Exemplo tipico |
|-----------|-------------|----------------|
| `transient` | Erro temporario, retentavel | Timeout de rede |
| `permanent` | Erro irrecuperavel | API key invalida |
| `validation` | Dados de entrada invalidos | Schema mismatch |
| `timeout` | Operacao excedeu tempo limite | LLM response timeout |
| `cancellation` | Operacao cancelada pelo usuario ou sistema | AnyIO cancellation scope |
| `adapter` | Erro no adapter externo | Driver de LLM falhou |
| `configuration` | Erro de configuracao | Engine nao definido |
| `state_consistency` | Estado inconsistente detectado | Run sem events emitidos |

Essa taxonomia nao e arbitraria -- ela reflete os modos de falha do sistema e determina como cada tipo de erro e tratado pelas policies (retry, escalacao, logging). Forcando o agente a classificar cada erro dentro dessa taxonomia, o contrato garante que novos erros sejam tratados consistentemente pelo sistema de policies existente.

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

### Como a regra se aplica na pratica

Cenario: O agente precisa implementar um novo `EventType` no sistema de eventos canonicos. Isso envolve:

1. `miniautogen/core/events/types.py` -- adicionar o novo tipo
2. `miniautogen/core/events/sink.py` -- atualizar o sink para emitir
3. `tests/core/events/test_types.py` -- testes para o novo tipo
4. `tests/core/events/test_sink.py` -- testes para a emissao
5. `miniautogen/core/runtime/pipeline_runner.py` -- emitir o evento no ponto correto

5 arquivos. Acima do limite de 3. O agente orquestrador deve:

1. **Decompor** a tarefa em sub-tarefas de no maximo 3 arquivos cada
2. **Despachar** um agente especialista para cada sub-tarefa
3. **Coordenar** a ordem de execucao (tipos antes de sink, sink antes de pipeline_runner)
4. **Verificar** que as sub-tarefas se integram corretamente

O resultado e melhor do que se o agente tivesse editado os 5 arquivos diretamente: cada sub-tarefa recebe atencao focada, e o orquestrador garante a coerencia do todo.

---

## 9. Tecnicas de qualidade transversais

As secoes anteriores descrevem componentes individuais do ambiente. Esta secao compila as **tecnicas transversais** que emergem da interacao entre esses componentes. Sao padroes que nenhum componente implementa sozinho, mas que o sistema como um todo produz.

### 9.1 Brainstorming antes de implementar

**Origem:** Skill `brainstorming` (Superpowers)

**Tecnica:** Refinamento socratico. O agente nao pode ir direto para a solucao. Ele deve explorar o espaco do problema, questionar suposicoes e considerar alternativas antes de comecar a implementar.

**O que previne:** Overengineering (a primeira solucao que o agente imagina tende a ser a mais complexa) e prematuridade (comecar a codar antes de entender o problema).

**Na pratica:** Antes de implementar um novo RuntimeInterceptor, o agente primeiro questiona: "Isso e realmente um interceptor? Ou e uma policy? Qual a diferenca neste contexto? O que acontece se eu fizer isso como policy?"

**A diferenca em numeros:** Sem brainstorming, um agente tipicamente implementa a primeira solucao que concebe em ~95% dos casos. Com brainstorming socratico, a primeira solucao e descartada ou refinada em ~40-60% dos casos, resultando em solucoes mais simples e alinhadas com a arquitetura.

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

**Quando escalar para `act`:** A pratica observada e escalar para `act` apenas em operacoes de baixo risco e alta previsibilidade: leitura de arquivos, execucao de testes, formatacao de codigo. Operacoes de escrita, git operations e chamadas a APIs externas permanecem em `plan`.

### 9.9 Skill-first

**Origem:** Mecanismo de invocacao de skills (Superpowers)

**Tecnica:** Processo antes de acao, sempre. O agente verifica se alguma skill e aplicavel ANTES de tomar qualquer acao.

**O que previne:** Acao impulsiva. O modo de falha mais natural de um agente de IA e "entender o pedido e comecar a fazer". Skills interceptam esse impulso e forcam reflexao processual.

**Analogia:** Como um cirurgiao que verifica o checklist da OMS antes de cada operacao -- mesmo que "ja saiba" o que fazer.

### 9.10 3-file gate

**Origem:** Ring Orchestrator

**Tecnica:** Contagem de arquivos como gatilho automatico de delegacao. Mais de 3 = despachar agente.

**O que previne:** Monolithic agent behavior -- um unico agente tentando fazer tudo, perdendo contexto e qualidade a cada arquivo adicional.

### 9.11 Enforcement programatico

**Origem:** `scripts/check_arch.py` + `.github/workflows/ci.yml`

**Tecnica:** Transformar invariantes textuais (CLAUDE.md) em verificacoes programaticas que rodam automaticamente no CI. As 4 invariantes arquiteturais sao validadas por analise AST -- sem dependencias externas, sem configuracao.

**O que previne:** Violacoes de invariantes que passam despercebidas. Um agente pode racionalizar uma excecao ("esse import e temporario") ou simplesmente nao perceber uma violacao indireta. O linter nao racionaliza -- ele verifica.

**Sinergia com outras tecnicas:** O enforcement programatico e a **base objetiva** sobre a qual as outras tecnicas operam. Skills forcam processo, delegacao traz perspectiva fresca, mas o linter e o CI fornecem **verdade verificavel**. Se o linter diz que ha uma violacao, nao importa o que o agente pensa -- o merge e bloqueado.

### 9.12 Contexto git continuo

**Origem:** Hook `UserPromptSubmit` + `scripts/hooks/pre-prompt.sh`

**Tecnica:** A cada prompt do usuario, injetar automaticamente o estado atual do git (branch, arquivos modificados, ultimo commit). O agente recebe informacao atualizada sem precisar pedi-la.

**O que previne:** Desorientacao em sessoes longas. Apos 30+ minutos de desenvolvimento, o agente pode perder nocao de quantos arquivos modificou, em que branch esta, ou qual foi o ultimo commit. O contexto continuo resolve isso proativamente.

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
| 11 | Enforcement programatico | check_arch.py + CI | Violacao de invariantes nao detectada |
| 12 | Contexto git continuo | pre-prompt.sh hook | Perda de nocao do estado do repo em sessoes longas |

### Interdependencias entre tecnicas

As 10 tecnicas nao operam em isolamento. Existem dependencias e sinergias:

```
brainstorming (1) ──alimenta──► TDD (2)
    │                              │
    │                              ▼
    │                    verificacao (3)
    │                              │
    ▼                              ▼
delegacao multi-modelo (5) ◄──── code review 3 eixos (4)
    │
    ▼
memoria de feedback (6) ◄──── duvida estruturada (7)
    │
    ▼
skill-first (9) ──governa──► todos os acima
    │
    ▼
3-file gate (10) ──forca──► delegacao (5)
    │
    ▼
plan mode (8) ──supervisiona──► todos os acima

enforcement programatico (11) ──valida──► invariantes (independente dos acima)
    │
    ▼
contexto git continuo (12) ──alimenta──► todos os acima
```

O grafo revela tres camadas de tecnicas "meta":
- **skill-first** e **plan mode** governam o *processo* (como o agente trabalha)
- **enforcement programatico** governa a *corretude* (o que o agente produz)
- **contexto git continuo** alimenta a *consciencia situacional* (o que o agente sabe)

O enforcement programatico e particularmente importante porque opera **independentemente** do agente. Mesmo que todas as outras tecnicas falhem (skills ignoradas, delegacao indisponivel, memoria corrompida), o linter e o CI continuam barrando violacoes de invariantes no merge.

### O custo da qualidade

Estas 12 tecnicas adicionam overhead ao fluxo de desenvolvimento. Uma tarefa que levaria 10 minutos em "modo rapido" (sem skills, sem review, sem delegacao) pode levar 25-30 minutos com todas as tecnicas ativas.

O argumento economico a favor e que a qualidade resultante reduz drasticamente o custo de retrabalho, debugging e manutencao. Uma implementacao "rapida" que introduz um bug de acoplamento pode custar horas de investigacao posteriores. Uma implementacao "lenta" que segue TDD, brainstorming e review raramente produz bugs de design.

A questao nao e se as tecnicas "valem a pena" em absoluto -- e para quais tarefas elas valem a pena. Para um fix trivial de typo, ativar todas as 10 tecnicas e claramente excessivo. Para implementar um novo runtime de coordenacao, e claramente necessario. A calibracao entre esses extremos e onde a experiencia do desenvolvedor (humano) faz diferenca.

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

### O que foi implementado desde a versao inicial deste documento

Varias das oportunidades identificadas na versao original deste documento foram implementadas. O registro abaixo captura o que mudou:

#### Sistema de especificacoes (antes: inexistente, agora: funcional)

O diretorio `.specs/` e seus artefatos agora existem e estao integrados ao workflow:

| Artefato | Funcao |
|----------|--------|
| `.specs/template.md` | Template de especificacao com G/C/FC, user stories, criterios de aceitacao, invariantes |
| `.specs/plan-template.md` | Template de plano de implementacao |
| `.specs/tasks-template.md` | Template de decomposicao em tasks |
| `scripts/specs/create-feature.sh` | Script que cria a estrutura de diretorio para uma nova feature |
| `.claude/commands/spec-create.md` | Slash command `/spec-create` |
| `.claude/commands/spec-plan.md` | Slash command `/spec-plan` |
| `.claude/commands/spec-tasks.md` | Slash command `/spec-tasks` |

O workflow mandatorio de Spec-Driven Development (CLAUDE.md passo 1) agora tem todos os artefatos necessarios. A lacuna mais critica da versao anterior foi resolvida.

#### Linter arquitetural (antes: inexistente, agora: funcional)

O `scripts/check_arch.py` e um linter baseado em AST que valida as 4 invariantes arquiteturais do CLAUDE.md programaticamente. Detalhado na secao 5.1.

#### Pipeline de CI (antes: inexistente, agora: funcional)

O `.github/workflows/ci.yml` implementa 3 jobs paralelos (lint, test, arch-check) com um gate consolidado (`ci-passed`). Detalhado na secao 5.1.

#### Hooks expandidos (antes: apenas SessionStart, agora: 3 hooks)

Os 3 lifecycle hooks (SessionStart, SessionEnd, UserPromptSubmit) estao configurados e funcionais. Detalhados na secao 5.

#### Permissoes granulares (antes: whitelist minima, agora: 13 padroes)

A whitelist de permissoes expandiu de 2 padroes (`ls`, `python3.13`) para 13 padroes cobrindo leitura, git, toolchain Python e build.

#### Consciencia multi-agente (antes: inexistente, agora: funcional)

Dois arquivos de instrucoes para outros agentes foram adicionados:
- `.github/copilot-instructions.md` -- orienta o GitHub Copilot a respeitar invariantes e taxonomia de erros
- `.github/gemini.md` -- orienta o Gemini CLI a seguir o workflow mandatorio e rodar o linter arquitetural

Ambos referenciam o `CLAUDE.md` como fonte canonica, evitando duplicacao de regras.

#### Memoria automatizada (antes: manual, agora: parcialmente automatica)

O hook `session-end.sh` gera memorias de sessao automaticamente com artefatos git. Detalhado nas secoes 4 e 5.

#### Convencoes git formalizadas (antes: implicitas, agora: documentadas)

O CLAUDE.md ganhou uma secao 5 com convencoes de branch naming (`feat/`, `fix/`, `chore/`, `docs/`), formato de commits (`type(scope): descricao`) e estrategia de merge (squash para features, merge commit para releases).

---

### Onde ha potencial de melhoria (atualizado)

#### Layer 3 canonical patterns pendentes

> **Actualização (2026-03-20):** O AgentRuntime compositor foi especificado em `.specs/agent-runtime-compositor.md`. Layer 3 agora tem design formal com: compositor que implementa os 3 agent protocols existentes (WorkflowAgent, ConversationalAgent, DeliberationAgent), configuração per-agent em `.miniautogen/agents/{name}/` (prompt.md, tools.yml, memory/), filesystem sandbox para isolamento entre agentes, ToolExecutionPolicy para limites de recursos, e PersistentMemoryProvider para memória cross-session. Os coordination runtimes não mudam — o AgentRuntime satisfaz os mesmos protocols via duck typing.

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

**Acao sugerida:** Criar um script de bootstrap ou, no minimo, um checklist de configuracao com os seguintes itens:

```markdown
## Checklist de configuracao do ambiente (proposta)

### Prerequisitos
- [ ] Claude Code CLI instalado
- [ ] Codex CLI instalado (para delegacao multi-modelo)
- [ ] Python 3.11+ via pyenv
- [ ] Acesso aos repositorios de plugins (Superpowers, Ring)

### Configuracao global (~/.claude/)
- [ ] settings.json com plugins, MCP servers e permissoes
- [ ] rules/delegator/ com 4 arquivos de regras de delegacao
- [ ] Plugins Superpowers e Ring instalados e ativados

### Configuracao por projeto
- [ ] claude.md (contrato constitucional) na raiz do repositorio
- [ ] Diretorio de memoria criado em ~/.claude/projects/*/memory/
- [ ] MEMORY.md com index inicial

### Verificacao
- [ ] Executar uma tarefa simples para confirmar que skills sao invocadas
- [ ] Testar delegacao ao Codex com uma pergunta de arquitetura
- [ ] Confirmar que MEMORY.md e carregado no inicio da sessao
```

#### Potencial de conflito entre skills e rings

Com 10 skills do Superpowers e 9 rings ativados simultaneamente, ha potencial de conflito ou redundancia. Por exemplo, o TDD mandatorio do Superpowers e o gate de testing do `ring-dev-team` podem impor requisitos conflitantes ou redundantes.

Nao ha documentacao explicita sobre precedencia ou resolucao de conflitos entre skills de diferentes fontes.

**Acao sugerida:** Documentar a hierarquia de precedencia (ex: "skills rigid do Superpowers tem prioridade sobre gates do Ring quando ha conflito") e identificar os pontos de sobreposicao explicitos.

#### Custo computacional da sofisticacao

Cada componente do ambiente consome tokens de contexto. Uma estimativa conservadora:

| Componente | Tokens consumidos por sessao |
|------------|------------------------------|
| CLAUDE.md (contrato) | ~2.000 |
| MEMORY.md + memorias de projeto | ~3.000-5.000 |
| Regras de delegacao (4 arquivos) | ~5.000 |
| Skills ativas (prompts injetados) | ~5.000-10.000 |
| Ring teams (contexto de workflow) | ~3.000-5.000 |
| **Total estimado** | **~18.000-27.000 tokens** |

Com 1M tokens de contexto disponivel, esse overhead e insignificante (~2-3%). Mas com modelos menores (128K, 200K), o custo seria proporcionalmente muito maior e poderia impactar a capacidade do agente de processar o codigo real do repositorio.

O ambiente foi claramente projetado para modelos de contexto extenso. Replica-lo com modelos menores exigiria priorizacao agressiva de quais componentes carregar.

#### Dependencia de ecossistema proprietario

O ambiente depende de componentes que nao sao open-source ou facilmente substituiveis:

| Componente | Proprietario | Alternativa |
|------------|-------------|-------------|
| Claude Code | Anthropic | Nao ha equivalente direto |
| Superpowers plugin | Marketplace Claude | Requer Claude Code |
| Ring marketplace | Lerian Studio | Requer Claude Code |
| Codex MCP | OpenAI | Outros MCP servers |

Se a Anthropic descontinuar o Claude Code ou mudar o sistema de plugins, o ambiente inteiro precisaria ser reconstruido. Isso nao e necessariamente um problema (toda ferramenta tem lock-in), mas e uma dependencia que merece registro.

### O balanco entre automacao e controle humano

O ambiente atinge um equilibrio notavel:

| Dimensao | Automatizado | Controle humano |
|----------|-------------|-----------------|
| **Processo** | Skills invocadas automaticamente | Humano pode overrider |
| **Execucao** | Plan mode propoe, humano aprova | Modo `act` disponivel |
| **Consultoria** | Triggers proativos para GPT | Humano pode pedir explicitamente |
| **Memoria** | Index + artefatos git automaticos | Humano decide decisoes estrategicas |
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

### Reflexao final: o meta-nivel

Ha uma ironia produtiva neste setup: o MiniAutoGen e um **framework de orquestracao multi-agente**, e o seu ambiente de desenvolvimento e, ele proprio, um **sistema de orquestracao multi-agente**. O Claude Code orquestra skills, delegacoes ao GPT, memorias e plugins da mesma forma que o MiniAutoGen orquestra Engines, Agents, Flows e Policies.

Isso nao e coincidencia. O ambiente de desenvolvimento evoluiu organicamente para refletir a mesma filosofia do produto:

| Principio do MiniAutoGen | Como aparece no ambiente de desenvolvimento |
|--------------------------|---------------------------------------------|
| "O agente e commodity, o runtime e o produto" | O Claude e commodity, o ambiente (skills + delegacao + memoria) e o produto |
| Isolamento absoluto de adapters | MCP servers isolados, cada um com escopo limitado |
| Policies event-driven laterais | Skills operam lateralmente, sem modificar o agente principal |
| PipelineRunner como unico executor | Claude Code como unico executor, GPT so consulta |
| Contratos tipados | Formato de 7 secoes para delegacoes, taxonomia canonica de erros |

O produto ensina o processo. O processo refina o produto. Esse loop de feedback e o que torna este ambiente mais do que a soma das suas partes -- e um sistema auto-referencial onde as decisoes de design do produto e do ambiente se reforçam mutuamente.

---

## Apendice A: Topologia completa do ambiente

```
Ambiente de Desenvolvimento (Claude Code)
│
├── Modelo Principal: Claude Opus 4.6 (1M context)
│   ├── Modo padrao: plan
│   └── Permissoes: whitelist granular (13 padroes em settings.local.json)
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
├── Hooks (3 lifecycle hooks)
│   ├── SessionStart → session-start.sh (marcador de sessao)
│   ├── SessionEnd → session-end.sh (memoria automatica)
│   └── UserPromptSubmit → pre-prompt.sh (contexto git)
│
├── Enforcement Programatico
│   ├── scripts/check_arch.py (4 checagens AST)
│   └── .github/workflows/ci.yml (lint + test + arch-check + gate)
│
├── Sistema de Specs
│   ├── .specs/template.md (feature spec)
│   ├── .specs/plan-template.md (plano)
│   ├── .specs/tasks-template.md (tasks)
│   ├── scripts/specs/create-feature.sh (bootstrap)
│   └── .claude/commands/spec-*.md (3 slash commands)
│
├── Consciencia Multi-Agente
│   ├── .github/copilot-instructions.md (Copilot)
│   └── .github/gemini.md (Gemini CLI)
│
├── Memoria Persistente
│   ├── MEMORY.md (index automatico)
│   ├── project_backend_drivers.md
│   ├── project_milestone1_sdk.md
│   ├── project_milestone2_cli.md
│   ├── project_strategic_vision.md
│   ├── project_tui_dash.md
│   └── session_*.md (gerados automaticamente)
│
├── Contrato (claude.md)
│   ├── Spec-Driven Development (4 passos)
│   ├── 4 invariantes inviolaveis
│   ├── 4 condicoes de rejeicao
│   ├── Convencoes git (§5)
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
5. [SPEC-DRIVEN] Criar spec em /.specs/ usando /spec-create (template disponivel)
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

### Pontos de decisao humana no fluxo

O fluxo acima tem **5 pontos** onde o humano intervem:

| Ponto | Tipo de decisao | O que o humano avalia |
|-------|-----------------|----------------------|
| 3 (design validado pelo GPT) | Aceitar/rejeitar recomendacao | A recomendacao do GPT faz sentido para este contexto? |
| 4 (contrato G/C/FC) | Aceitar/ajustar contrato | O Goal, Constraint e Failure Condition estao corretos? |
| 8 (cada acao em plan mode) | Aprovar/rejeitar acao | Essa acao especifica e segura e correta? |
| 9 (resultado do code review) | Aceitar/pedir ajustes | Os issues identificados sao reais? |
| 10 (evidencia de conclusao) | Aceitar/rejeitar conclusao | A evidencia apresentada e suficiente? |

A razao entre acoes automaticas e decisoes humanas e aproximadamente 7:5 -- o sistema faz mais do que o humano decide, mas o humano decide nos pontos criticos. Essa e a essencia do modelo "automacao com supervisao".

### Quando o fluxo falha

O fluxo pode falhar em varios pontos, e cada falha tem um mecanismo de recuperacao:

| Ponto de falha | Causa tipica | Recuperacao |
|---------------|-------------|-------------|
| Brainstorming inconclusivo | Problema muito ambiguo | Escalar para Scope Analyst (GPT) |
| Architect GPT da recomendacao irrelevante | Contexto insuficiente na delegacao | Reenviar com mais contexto |
| Testes nao conseguem ser escritos | Especificacao muito vaga | Voltar ao brainstorming |
| 3-file gate ativado mas agente nao pode delegar | Infraestrutura de sub-agentes nao configurada | Humano autoriza execucao direta |
| Code review identifica issues fundamentais | Design incorreto | Voltar ao passo 2 (brainstorming) |
| Verificacao falha | Implementacao incompleta | Continuar implementacao |

O fluxo nao e linear -- ele tem loops de feedback em cada estagio. A robustez vem nao de evitar falhas, mas de ter mecanismos de recuperacao para cada tipo de falha.

---

## Apendice C: Configuracao de referencia

Para replicar este ambiente, os seguintes arquivos devem ser configurados:

| Arquivo | Localizacao | Funcao |
|---------|-------------|--------|
| `settings.json` | `.claude/settings.json` | Hooks de lifecycle (3 hooks) |
| `settings.local.json` | `.claude/settings.local.json` | Permissoes granulares (13 padroes) |
| `claude.md` | Raiz do repositorio | Contrato constitucional (§1-5) |
| `MEMORY.md` | `~/.claude/projects/*/memory/` | Index de memoria |
| Regras de delegacao | `~/.claude/rules/delegator/` | 4 arquivos: orchestration, model-selection, triggers, delegation-format |
| Memorias de projeto | `~/.claude/projects/*/memory/` | Decisoes e convencoes |
| Templates de specs | `.specs/` | 3 templates (feature, plan, tasks) |
| Slash commands | `.claude/commands/` | 3 comandos (spec-create, spec-plan, spec-tasks) |
| Linter arquitetural | `scripts/check_arch.py` | 4 checagens AST das invariantes |
| CI pipeline | `.github/workflows/ci.yml` | 3 jobs + gate consolidado |
| Hooks de lifecycle | `scripts/hooks/` | 3 scripts (session-start, session-end, pre-prompt) |
| Instrucoes Copilot | `.github/copilot-instructions.md` | Contexto para GitHub Copilot |
| Instrucoes Gemini | `.github/gemini.md` | Contexto para Gemini CLI |

### Hierarquia de configuracao

```
~/.claude/
├── settings.json                    # Global: plugins, MCP servers
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
            ├── project_*.md
            └── session_*.md         # Gerados automaticamente por session-end.sh

<repositorio>/
├── CLAUDE.md                        # Contrato constitucional (§1-5)
├── .claude/
│   ├── settings.json                # Hooks de lifecycle (3 hooks)
│   ├── settings.local.json          # Permissoes granulares (13 padroes)
│   └── commands/
│       ├── spec-create.md           # /spec-create slash command
│       ├── spec-plan.md             # /spec-plan slash command
│       └── spec-tasks.md            # /spec-tasks slash command
├── .specs/
│   ├── template.md                  # Template de spec (G/C/FC, user stories)
│   ├── plan-template.md             # Template de plano
│   └── tasks-template.md            # Template de tasks
├── .github/
│   ├── workflows/ci.yml             # CI pipeline (lint + test + arch-check)
│   ├── copilot-instructions.md      # Instrucoes para Copilot
│   └── gemini.md                    # Instrucoes para Gemini CLI
└── scripts/
    ├── check_arch.py                # Linter arquitetural (4 checagens AST)
    ├── hooks/
    │   ├── session-start.sh         # Marcador de sessao
    │   ├── session-end.sh           # Memoria automatica
    │   └── pre-prompt.sh            # Contexto git por prompt
    └── specs/
        └── create-feature.sh        # Bootstrap de nova feature
```

A hierarquia e deliberada e segue dois principios: (1) configuracoes de ambiente ficam em `~/.claude/` (nao versionadas, especificas do desenvolvedor), e (2) artefatos de processo ficam no repositorio (versionados, consistentes para todos). O contrato constitucional, os templates de spec, o linter, os hooks e as instrucoes multi-agente sao todos versionados -- um novo desenvolvedor que clona o repositorio recebe o processo completo.

### O que e versionado vs o que e local

Uma distincao critica para reprodutibilidade:

| Artefato | Versionado (git) | Local (~/.claude/) |
|----------|-------------------|--------------------|
| Contrato constitucional (CLAUDE.md) | Sim | -- |
| Templates de specs (`.specs/`) | Sim | -- |
| Linter arquitetural (`check_arch.py`) | Sim | -- |
| CI pipeline (`ci.yml`) | Sim | -- |
| Hooks de lifecycle (`scripts/hooks/`) | Sim | -- |
| Instrucoes multi-agente (`.github/`) | Sim | -- |
| Slash commands (`.claude/commands/`) | Sim | -- |
| Config de hooks (`.claude/settings.json`) | Sim | -- |
| Permissoes (`.claude/settings.local.json`) | -- | Sim |
| Memorias de projeto | -- | Sim |
| Regras de delegacao | -- | Sim |
| Configuracao de plugins/MCP | -- | Sim |
| Documentacao do projeto | Sim | -- |
| Testes e codigo | Sim | -- |

A separacao evoluiu significativamente. Na versao anterior, apenas o contrato constitucional e o codigo eram versionados. Agora, a maioria dos artefatos de processo (specs, linter, CI, hooks, instrucoes multi-agente) tambem sao versionados. Isso significa que um novo desenvolvedor que clona o repositorio recebe nao apenas o contrato, mas o **processo completo**: templates de spec, linter arquitetural, pipeline CI, hooks de lifecycle e instrucoes para outros agentes.

O que permanece local sao configuracoes especificas do ambiente (permissoes, memorias, plugins, regras de delegacao). Essa divisao reflete a diferenca entre **processo** (compartilhado) e **ambiente** (individual).

---

## Apendice D: Glossario de termos

| Termo | Definicao neste contexto |
|-------|--------------------------|
| **Agent** | Modelo de IA operando dentro de um ambiente configurado (Claude Code, GPT Codex) |
| **Contrato constitucional** | Arquivo claude.md que define regras inviolaveis para o agente |
| **Context rot** | Degradacao gradual do alinhamento entre agente e projeto ao longo do tempo |
| **Delegacao** | Transferencia de uma tarefa do agente principal (Claude) para um especialista (GPT) |
| **DX** | Developer Experience -- a qualidade da experiencia do desenvolvedor |
| **Gate** | Checkpoint obrigatorio num pipeline de qualidade (ring-dev-team, ring-pm-team) |
| **Hook** | Script automatico executado em eventos do sistema (SessionStart, SessionEnd, UserPromptSubmit) |
| **Linter arquitetural** | Script AST (`check_arch.py`) que valida invariantes arquiteturais programaticamente |
| **MCP** | Model Context Protocol -- padrao de comunicacao entre agentes e servicos externos |
| **Memoria persistente** | Sistema de arquivos que mantem decisoes e convencoes entre sessoes |
| **Plan mode** | Modo de operacao onde o agente propoe e o humano aprova antes da execucao |
| **Ring** | Marketplace de plugins para Claude Code com times especializados |
| **Skill** | Instrucao processual que governa como o agente executa um tipo de tarefa |
| **Superpowers** | Plugin que fornece skills processuais para qualidade de desenvolvimento |
| **Trigger** | Condicao que ativa automaticamente uma skill ou delegacao |

---

## Apendice E: Leitura relacionada

Para aprofundamento nos temas abordados neste documento:

### Documentacao do projeto
- [README principal (pt-BR)](docs/pt/README.md) -- Visao geral do MiniAutoGen, conceitos de primeira classe
- [Retrospectiva arquitetural](docs/architecture-retrospective.md) -- Comparacao v0 vs arquitetura atual
- [Analise competitiva](docs/competitive-landscape.md) -- Posicionamento contra 10+ frameworks
- [Anatomia do agente](docs/pt/architecture/07-agent-anatomy.md) -- 5 layers, comparacao com protocolos de mercado

### Arquitetura do ambiente
- [Regras de delegacao](~/.claude/rules/delegator/) -- 4 arquivos que governam delegacao multi-modelo
- [Contrato constitucional](claude.md) -- Regras inviolaveis e workflow mandatorio
- [Memorias de projeto](~/.claude/projects/*/memory/) -- Decisoes e convencoes acumuladas

### Referencias externas
- Model Context Protocol (MCP) -- Padrao de comunicacao para integracao de ferramentas com LLMs
- Claude Code CLI -- Interface de desenvolvimento assistida por IA da Anthropic
- Codex CLI -- Interface de linha de comando para modelos GPT da OpenAI

---

## Apendice F: Evolucao provavel do ambiente

### Tendencias observaveis

Com base na configuracao atual e nas lacunas identificadas, e possivel projetar evolucoes provaveis:

**Ja implementado** (previsoes de curto prazo que se concretizaram):
- ~~Criacao do diretorio `.specs/` e template~~ -- Implementado com 3 templates, script e 3 slash commands
- ~~Hooks mais sofisticados~~ -- 3 lifecycle hooks com captura automatica de artefatos
- ~~Integracao com CI/CD~~ -- Pipeline CI com lint, test e arch-check

**Curto prazo (1-3 meses):**
- Adicao de metricas basicas de eficacia (invocacoes de skills, taxa de sucesso de delegacoes)
- Documentacao de precedencia entre skills e rings
- Expansao do linter arquitetural com novas regras (ex: validacao de taxonomia de erros)

**Medio prazo (3-6 meses):**
- Memoria hierarquica com mecanismo de expiracao
- Script de bootstrap para onboarding de novos desenvolvedores
- Adicao de MCP servers para monitoramento e observabilidade

**Longo prazo (6-12 meses):**
- O ambiente provavelmente evoluira para ter **multiplos agentes locais** coordenados (nao apenas delegacao singleshot ao GPT), espelhando a propria evolucao do MiniAutoGen em direcao a orquestracao multi-agente mais sofisticada
- Hooks adaptativos que ajustem o conjunto de skills ativas ao tipo de tarefa
- Pipeline de CI que inclua validacao de specs e coerencia entre testes e especificacoes

### O paradoxo final

Ha um paradoxo inerente a este tipo de ambiente: quanto mais sofisticado ele se torna, mais dificil e distinguir a contribuicao do agente da contribuicao do ambiente. Quando o agente produz codigo de alta qualidade, e porque o modelo e bom ou porque as skills, delegacoes e memorias compensam suas fraquezas?

A resposta, provavelmente, e que a pergunta esta mal formulada. O valor nao esta no modelo nem no ambiente isoladamente -- esta na **composicao**. Um modelo poderoso sem ambiente produz "vibes". Um ambiente sofisticado com modelo fraco produz friccao sem resultado. A combinacao certa dos dois produz desenvolvimento de qualidade reprodutivel.

E esse e, talvez, o maior insight deste ambiente: **a qualidade de software assistido por agentes nao e uma propriedade do modelo. E uma propriedade do sistema.**

### Contexto competitivo

A análise de 7 concorrentes (AutoGen, LangGraph, CrewAI, DeerFlow, Open SWE, Bit Office, padrões Anthropic) validou as 3 teses centrais do MiniAutoGen e informou o design do AgentRuntime. Detalhes em [análises de concorrentes](../../../.specs/analysis-competitors-deep-dive.md) e no [README estratégico](pt/README.md#validação-de-mercado).

---

*Documento gerado como analise do ambiente de desenvolvimento do MiniAutoGen. Reflete a configuracao observada em marco de 2026. A analise foi feita por observacao direta dos arquivos de configuracao, regras de delegacao, memorias de projeto e contrato constitucional.*
