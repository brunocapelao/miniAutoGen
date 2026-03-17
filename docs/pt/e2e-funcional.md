# Especificação funcional E2E -- MiniAutoGen CLI-First

Documento de especificação funcional end-to-end do framework MiniAutoGen, descrevendo a jornada completa do utilizador num paradigma CLI-First de gestão de recursos. O terminal é o plano de controlo único: criar, modificar, listar e orquestrar qualquer recurso do sistema sem nunca abrir um editor de texto.

**Versão:** 3.1.0
**Data:** 2026-03-17
**Escopo:** Jornada E2E do desenvolvedor no MiniAutoGen CLI como Control Plane de recursos

---

## Índice

- [Parte 1: Story Map -- Nova Jornada E2E CLI-First](#parte-1-story-map----nova-jornada-e2e-cli-first)
- [Parte 2: Especificação BDD dos fluxos E2E](#parte-2-especificação-bdd-dos-fluxos-e2e)
- [Parte 3: Especificação funcional](#parte-3-especificação-funcional)

---

# Parte 1: Story Map -- Nova Jornada E2E CLI-First

O Story Map a seguir descreve a jornada completa de um desenvolvedor que utiliza o MiniAutoGen CLI como plano de controlo para gerir todos os recursos do sistema multiagente. Cada etapa representa um "Job to be Done" concreto, onde o terminal é a interface única de interação. O objectivo estratégico: um novo desenvolvedor tem um pipeline multiagente a funcionar com LLM local em menos de 3 minutos, usando apenas o terminal.

---

## Etapa 1: Bootstrap (Inicialização)

**User Story:**
> Como desenvolvedor, quero criar rapidamente a estrutura de um projecto multiagente com um único comando, para começar a trabalhar imediatamente sem configuração manual.

### Ações técnicas

O desenvolvedor executa o comando CLI `miniautogen init` para gerar o scaffold completo do projecto.

**Comando:**

```
miniautogen init meu-projecto
```

**O que acontece:**

1. O CLI cria o diretório do projecto com a estrutura padrão.
2. Gera o ficheiro `miniautogen.yml` com a configuração base (vazio, pronto para receber recursos).
3. Cria os diretórios `agents/`, `pipelines/` e `templates/`.
4. Exibe mensagem de sucesso com próximos passos sugeridos (criar um motor).

**Política de diretório não vazio:**

- Se o diretório de destino já existir e não estiver vazio, o comando bloqueia por defeito com mensagem de erro.
- Com `--force`, o sistema preserva os ficheiros existentes e adiciona apenas os que faltam na estrutura padrão.
- O sistema nunca sobrescreve ficheiros existentes sem `--force`.

**Estrutura gerada:**

```
meu-projecto/
  miniautogen.yml
  agents/
  pipelines/
  templates/
```

**Resultado:** O desenvolvedor tem um projecto válido e vazio, pronto para receber recursos via CLI.

---

## Etapa 2: Gestão de Motores LLM (Backends)

**User Story:**
> Como desenvolvedor, quero configurar motores de IA via terminal sem editar ficheiros YAML manualmente, para que a configuração seja guiada, validada e livre de erros de sintaxe.

### Modo Interactivo (sem flags)

Quando o desenvolvedor não fornece todos os parâmetros, o CLI inicia um assistente passo-a-passo:

**Comando:**

```
miniautogen engine create openai-gpt4
```

**O que acontece:**

1. O CLI detecta que faltam parâmetros obrigatórios.
2. Inicia o modo interactivo (wizard):
   - Pergunta o tipo de provedor (OpenAI, Gemini CLI Gateway, vLLM, outro).
   - Pergunta o modelo específico.
   - Pergunta o endpoint (com valor padrão por provedor).
   - Pergunta a chave de API (com opção de referenciar variável de ambiente).
   - Pergunta as capacidades suportadas (chat, completion, embedding).
3. O wizard aceita a chave temporariamente para validar a conexão, mas grava apenas a referência a variável de ambiente (formato: `${NOME_DA_VARIAVEL}`). O sistema nunca grava chaves de API em texto limpo nos ficheiros de configuração.
4. Valida o esquema completo do motor (BackendConfig) antes de gravar.
5. Escreve a configuração na secção `engines` do `miniautogen.yml`.
6. Exibe resumo do motor criado.

### Modo Silencioso (todas as flags)

Para automação e CI/CD, todos os parâmetros podem ser fornecidos via flags:

**Comando:**

```
miniautogen engine create openai-gpt4 --provider openai --model gpt-4o --api-key $OPENAI_API_KEY
```

**O que acontece:**

1. O CLI recebe todos os parâmetros necessários.
2. Não exibe nenhum prompt interactivo.
3. Valida o esquema, grava e retorna código de saída 0 (sucesso) ou 1 (erro com mensagem).

### Listagem, Inspeção e Atualização

```
miniautogen engine list
```

Exibe tabela com todos os motores configurados: nome, provedor, modelo, capacidades.

```
miniautogen engine show <name>
```

Exibe detalhes completos de um motor específico: nome, provedor, modelo, endpoint, capacidades, variáveis de ambiente referenciadas. Suporta `--format json` para saída estruturada.

```
miniautogen engine update openai-gpt4 --model gpt-4o-mini
```

Le o YAML existente, altera apenas a chave solicitada, regrava preservando comentários e indentação original. Suporta `--dry-run` que mostra a diferença entre o estado actual e o proposto, sem aplicar alterações.

**Resultado:** O desenvolvedor tem motores LLM configurados e validados, prontos para vincular a agentes.

---

## Etapa 3: Gestão do Servidor (Gateway)

**User Story:**
> Como desenvolvedor, quero iniciar, parar e verificar o estado do gateway local do MiniAutoGen via terminal, para não precisar de gerir processos manualmente.

O gateway é um servidor HTTP local que encapsula backends LLM (como o Gemini CLI) e os expõe como API HTTP compatível com OpenAI em `/v1/chat/completions`. É este gateway que permite ao AgentAPIDriver comunicar com backends LLM locais. Sem o gateway em execução, motores configurados com endpoint local não são acessíveis.

### Comandos de Gestão do Servidor

**Arranque do gateway:**

```
miniautogen server start
```

Inicia o gateway local. Suporta dois modos de execução:
- **Foreground (padrão):** O gateway corre no terminal com logs em tempo real. Útil para desenvolvimento e depuração.
- **Daemon (`--daemon`):** O gateway corre em segundo plano com PID registado em `.miniautogen/server.pid`. Útil para sessões de trabalho prolongadas.

Antes de iniciar em modo daemon, o sistema verifica se já existe um processo activo (via PID registado). Se o PID existir mas o processo não estiver activo (PID stale), o ficheiro é limpo automaticamente antes de iniciar.

Parâmetros configuráveis via flags: `--port` (porta, padrão 8080), `--host` (interface, padrão 127.0.0.1), `--timeout` (timeout de pedidos), `--max-concurrency` (concorrência máxima).

**Paragem do gateway:**

```
miniautogen server stop
```

Para o gateway em execução (modo daemon). Termina o processo de forma limpa, libertando a porta e recursos associados.

**Estado do gateway:**

```
miniautogen server status
```

Mostra o estado operacional do gateway. Estados possíveis:
- `running` -- activo e health check OK.
- `degraded` -- processo activo mas health check falhando.
- `unreachable` -- PID registado mas processo não responde.
- `stopped` -- nenhum processo activo.

Informações adicionais: porta, PID, uptime e resultado do health check.

**Logs do gateway:**

```
miniautogen server logs
```

Mostra logs recentes do gateway quando em execução em modo daemon. Útil para diagnóstico sem ter de reiniciar em modo foreground.

### Integração com Validação de Projecto

Quando um motor está configurado com endpoint local (ex: `localhost:8080`), o comando `miniautogen check` deve verificar que o gateway está acessível. Se não estiver, reporta aviso com sugestão para executar `miniautogen server start`.

**Resultado:** O desenvolvedor gere o ciclo de vida do gateway local sem recorrer a comandos manuais de gestão de processos.

---

## Etapa 4: Gestão de Agentes

**User Story:**
> Como desenvolvedor, quero criar agentes com identidade, papel e vínculo a motor via terminal, para definir as capacidades de cada participante do pipeline sem editar ficheiros.

### Criação de Agente

**Comando (modo interactivo):**

```
miniautogen agent create analyst
```

**O que acontece:**

1. O CLI inicia o wizard de criação de agente:
   - Pergunta o papel (Role) do agente.
   - Pergunta o objectivo (Goal).
   - Lista os motores disponíveis e pede para selecionar um.
   - Se não existirem motores configurados, sugere criar um primeiro (`miniautogen engine create`).
   - Pergunta configurações adicionais opcionais (temperatura, tokens máximos).
2. Valida contra o esquema AgentSpec.
3. Grava o ficheiro `agents/analyst.yml`.
4. Exibe resumo do agente criado.

**Comando (modo silencioso):**

```
miniautogen agent create analyst --role "Analista de dados" --goal "Analisar datasets" --engine openai-gpt4
```

### Listagem, Inspeção, Atualização e Exclusão

```
miniautogen agent list
```

Exibe tabela com todos os agentes: nome, papel, motor vinculado.

```
miniautogen agent show <name>
```

Exibe detalhes completos de um agente específico: nome, papel, objectivo, motor vinculado, configurações de geração. Suporta `--format json` para saída estruturada.

```
miniautogen agent update analyst --role "Analista senior de dados"
```

Atualização in-place: le o YAML, altera apenas o campo solicitado, preserva estrutura. Suporta `--dry-run` que mostra a diferença entre o estado actual e o proposto, sem aplicar alterações.

```
miniautogen agent delete analyst
```

**Exclusão segura:**

1. Verifica se o agente está referenciado em algum pipeline.
2. Se estiver em uso, bloqueia a exclusão e informa quais pipelines o referenciam.
3. Se não estiver em uso, remove o ficheiro e confirma.

**Resultado:** O desenvolvedor tem agentes definidos, validados e vinculados a motores, prontos para participar em pipelines.

---

## Etapa 5: Gestão de Pipelines (Coordenação)

**User Story:**
> Como desenvolvedor, quero montar planos de coordenação multiagente via terminal, escolhendo o modo de execução e os participantes sem escrever configuração manualmente.

### Criação de Pipeline

O CLI suporta três modos de coordenação, cada um com fluxo de configuração específico:

**Modo Workflow (cadeia sequencial):**

```
miniautogen pipeline create etl --mode workflow
```

Wizard pergunta: quais agentes encadear e em que ordem.

**Modo Deliberação (líder + pares):**

```
miniautogen pipeline create research --mode deliberation --leader analyst --participants reviewer,writer
```

Wizard pergunta (se faltar flags): quem é o líder, quem são os pares, quantas rondas de deliberação.

**Modo Loop Agêntico (roteador + participantes):**

```
miniautogen pipeline create support --mode loop
```

Wizard pergunta: qual agente é o roteador, quais são os participantes, condição de terminação.

**Modo Composite (composição de modos):**

```
miniautogen pipeline create complexo --mode composite
```

O wizard lista pipelines existentes e permite selecionar quais encadear. Para cada pipeline selecionado, permite definir mapeadores de entrada/saída opcionais. Gera os CompositionStep correspondentes com a configuração de encadeamento.

### Listagem, Inspeção e Atualização

```
miniautogen pipeline list
```

Exibe tabela com pipelines: nome, modo, agentes participantes.

```
miniautogen pipeline show <name>
```

Exibe detalhes completos de um pipeline específico: nome, modo de coordenação, agentes participantes, parâmetros do modo (líder, rondas, condição de terminação), composição (se aplicável). Suporta `--format json` para saída estruturada.

```
miniautogen pipeline update research --add-participant fact-checker
```

Adiciona ou remove agentes de um pipeline existente. Suporta `--dry-run` que mostra a diferença entre o estado actual e o proposto, sem aplicar alterações.

**Resultado:** O desenvolvedor tem pipelines configurados com modos de coordenação e participantes validados.

---

## Etapa 6: Validação e Execução (QA e Ação)

**User Story:**
> Como desenvolvedor, quero validar a consistência de todo o projecto antes de executar, para detectar erros de configuração antecipadamente.

### Validação Completa

```
miniautogen check
```

**O que válida:**

O comando `check` executa dois tipos de validação:

**Validação de configuração:**
1. **Motores:** Todos os motores referenciados por agentes existem na configuração.
2. **Agentes:** Todos os ficheiros em `agents/` são válidos contra o esquema AgentSpec.
3. **Pipelines:** Todos os agentes referenciados em pipelines existem. Configuração do modo é consistente.
4. **Dependências cruzadas:** Não existem referências circulares ou órfãs.
5. **Integridade de ficheiros:** Esquemas válidos, referências cruzadas consistentes.

**Validação de runtime:**
1. **Gateway:** Se existirem motores com endpoint local, verifica a acessibilidade do gateway.
2. **Resolução de motores:** Verifica que os motores configurados são resolúveis.
3. **Conectividade:** Testa acessibilidade dos endpoints configurados.

O comando executa ambas as válidações por defeito. Futuro: `--config-only`, `--runtime-only`.

**Saída:** Relatório com status por recurso (válido/inválido) e mensagens de erro detalhadas.

### Execução

```
miniautogen run research
```

**Fornecimento de entrada:**

O comando `run` suporta três formas de fornecer entrada ao pipeline:
- `--input "texto"` -- fornece entrada directamente como argumento.
- `--input @caminho/arquivo.txt` -- le entrada de ficheiro (prefixo `@` indica caminho).
- Se nenhum `--input` for fornecido, le de stdin.

**O que acontece:**

1. O CLI carrega a configuração do pipeline `research`.
2. Resolve todas as dependências (motores, agentes, políticas).
3. Delega ao PipelineRunner a execução.
4. O PipelineRunner:
   - Gera um `run_id` único.
   - Emite evento `RUN_STARTED`.
   - Instancia o runtime adequado ao modo (WorkflowRuntime, DeliberationRuntime, AgenticLoopRuntime).
   - Executa os componentes conforme a estrategia de coordenação.
   - Aplica políticas laterais (timeout, budget, retry).
   - Emite eventos ao longo do ciclo de vida.
   - Ao terminar, emite `RUN_FINISHED` com o RunResult final.
5. O CLI exibe o resultado: status (FINISHED, FAILED, CANCELLED, TIMED_OUT), duração, métricas.

**Resultado:** O desenvolvedor executa pipelines validados com visibilidade completa do ciclo de vida.

---

## Etapa 7: Recuperação e Retomada (Execução Durável)

**User Story:**
> Como desenvolvedor, quero retomar execuções interrompidas a partir de checkpoints, para não perder progresso em pipelines longos.

### Mecanismo de Recuperação

1. Durante a execução, o PipelineRunner persiste checkpoints periódicos via CheckpointStore.
2. Cada checkpoint contém: estado do RunContext, último componente concluído, mensagens acumuladas.
3. Se uma execução falhar ou for interrompida:

```
miniautogen run research --resume <run_id>
```

4. O SessionRecovery:
   - Localiza o último checkpoint válido.
   - Reconstrói o RunContext.
   - Retoma a execução a partir do componente seguinte ao último checkpoint.
   - Emite evento `RUN_RESUMED` com referência ao `run_id` original.

**Resultado:** Execuções longas são resilientes a falhas, com retomada transparente.

---

## Etapa 8: Operação e Observabilidade (Pós-Ação)

**User Story:**
> Como desenvolvedor, quero consultar o histórico de execuções e gerir sessões antigas via terminal.

### Gestão de Sessões

```
miniautogen sessions list
```

Exibe tabela com execuções: `run_id`, pipeline, status, data de início, duração.

```
miniautogen sessions list --status FAILED --since 7d
```

Filtragem por status e período.

```
miniautogen sessions show <run_id>
```

Exibe detalhes completos de uma execução específica: estado actual, eventos emitidos, mensagens trocadas, checkpoints registados. Suporta `--format json` para saída estruturada.

```
miniautogen sessions clean --older-than 30d
```

Remove sessões com mais de 30 dias. Solicita confirmação antes de apagar.

### Observabilidade

Todas as execuções produzem eventos com `correlation_id` e `timestamp`, armazenados de forma estruturada. A taxonomia canônica de eventos de execução (versão 1) cobre todo o ciclo de vida: desde `RUN_STARTED` até `RUN_FINISHED`, passando por `COMPONENT_STARTED`, `COMPONENT_FINISHED`, `RETRY_ATTEMPTED`, `BUDGET_EXCEEDED`, `APPROVAL_REQUESTED`, entre outros. A taxonomia abrange as categorias de ciclo de vida de execução, componentes, ferramentas, políticas, modos de coordenação, backend drivers e aprovações.

**Resultado:** O desenvolvedor tem visibilidade total sobre o histórico e pode gerir o ciclo de vida das sessões via terminal.

---

## Separação Conceptual do CLI

O CLI do MiniAutoGen organiza-se em dois domínios funcionais distintos:

### CLI Administrativo

Comandos de gestão de recursos e configuração do projecto:

- `miniautogen init` -- inicialização do projecto
- `miniautogen engine create|list|show|update` -- gestão de motores
- `miniautogen agent create|list|show|update|delete` -- gestão de agentes
- `miniautogen pipeline create|list|show|update` -- gestão de pipelines
- `miniautogen server start|stop|status|logs` -- gestão do gateway
- `miniautogen check` -- validação do projecto

### CLI de Operações/Runtime

Comandos de execução e gestão do ciclo de vida de sessões:

- `miniautogen run <pipeline> [--input] [--resume]` -- execução de pipelines
- `miniautogen sessions list|show|clean` -- gestão de sessões

---

# Parte 2: Especificação BDD dos fluxos E2E

Os cenários seguintes descrevem o comportamento esperado do sistema em formato Gherkin (Dado/Quando/Então), cobrindo toda a jornada CLI-First.

---

## Cenário 1: Inicialização de projecto via CLI

```gherkin
Funcionalidade: Inicialização de projeto

  Cenário: Criar projeto com scaffold completo
    Dado que o diretório "meu-projeto" não existe
    Quando o utilizador executa "miniautogen init meu-projeto"
    Então o diretório "meu-projeto" é criado
    E o ficheiro "meu-projeto/miniautogen.yml" é gerado com esquema válido
    E os diretórios "agents/", "pipelines/" e "templates/" são criados
    E a saída exibe mensagem de sucesso com próximos passos

  Cenário: Init em diretório não vazio sem force
    Dado que o diretório "meu-projeto" existe e contém ficheiros
    Quando o utilizador executa "miniautogen init meu-projeto"
    Então o comando bloqueia com mensagem de erro
    E nenhum ficheiro é modificado ou criado
    E o código de saída é 1

  Cenário: Init em diretório não vazio com force
    Dado que o diretório "meu-projeto" existe e contém ficheiros
    Quando o utilizador executa "miniautogen init meu-projeto --force"
    Então os ficheiros existentes são preservados
    E apenas os ficheiros em falta na estrutura padrão são adicionados
    E o código de saída é 0
```

---

## Cenário 2: Criação de motor LLM em modo interactivo

```gherkin
Funcionalidade: Gestão de motores LLM

  Cenário: Criar motor sem flags (modo interactivo)
    Dado que o projeto "meu-projeto" está inicializado
    E não existem motores configurados
    Quando o utilizador executa "miniautogen engine create meu-motor"
    Então o CLI inicia o wizard interactivo
    E pergunta o tipo de provedor
    E pergunta o modelo
    E pergunta o endpoint com valor padrão
    E pergunta a chave de API
    E pergunta as capacidades suportadas
    E valida o esquema BackendConfig antes de gravar
    E grava apenas a referência a variável de ambiente, não a chave em texto limpo
    E adiciona o motor a secção "engines" do miniautogen.yml
    E exibe resumo do motor criado
```

---

## Cenário 3: Criação de motor LLM em modo silencioso

```gherkin
  Cenário: Criar motor com todas as flags (modo silencioso para CI/CD)
    Dado que o projeto "meu-projeto" está inicializado
    Quando o utilizador executa "miniautogen engine create gpt4 --provider openai --model gpt-4o --api-key $KEY"
    Então nenhum prompt interactivo é exibido
    E o esquema BackendConfig é validado
    E o motor é gravado no miniautogen.yml
    E o código de saída é 0
```

---

## Cenário 4: Listagem de motores configurados

```gherkin
  Cenário: Listar motores existentes
    Dado que existem 2 motores configurados: "openai-gpt4" e "gemini-local"
    Quando o utilizador executa "miniautogen engine list"
    Então a saída exibe uma tabela com 2 linhas
    E cada linha contém: nome, provedor, modelo, capacidades
```

---

## Cenário 5: Criação de agente com vínculo a motor existente

```gherkin
Funcionalidade: Gestão de agentes

  Cenário: Criar agente vinculado a motor existente
    Dado que o motor "openai-gpt4" está configurado
    Quando o utilizador executa "miniautogen agent create analyst --role 'Analista de dados' --engine openai-gpt4"
    Então o esquema AgentSpec é validado
    E o ficheiro "agents/analyst.yml" é criado
    E o agente referencia o motor "openai-gpt4"
    E a saída exibe resumo do agente criado
```

---

## Cenário 6: Criação de agente sem motores disponíveis

```gherkin
  Cenário: Criar agente quando não existem motores
    Dado que não existem motores configurados no projeto
    Quando o utilizador executa "miniautogen agent create analyst"
    Então o CLI exibe aviso: "Nenhum motor configurado"
    E sugere executar "miniautogen engine create" primeiro
    E a criação do agente é interrompida
```

---

## Cenário 7: Exclusão segura de agente

```gherkin
  Cenário: Excluir agente em uso por pipeline
    Dado que o agente "analyst" está referenciado no pipeline "research"
    Quando o utilizador executa "miniautogen agent delete analyst"
    Então a exclusão é bloqueada
    E a saída informa que o agente está em uso pelo pipeline "research"
    E sugere remover o agente do pipeline antes de excluir

  Cenário: Excluir agente sem uso
    Dado que o agente "analyst" não está referenciado em nenhum pipeline
    Quando o utilizador executa "miniautogen agent delete analyst"
    Então o ficheiro "agents/analyst.yml" é removido
    E a saída confirma a exclusão
```

---

## Cenário 8: Criação de pipeline Workflow via CLI interactivo

```gherkin
Funcionalidade: Gestão de pipelines

  Cenário: Criar pipeline Workflow em modo interactivo
    Dado que existem 3 agentes configurados: "extractor", "transformer", "loader"
    Quando o utilizador executa "miniautogen pipeline create etl --mode workflow"
    Então o CLI pergunta quais agentes encadear
    E pergunta a ordem de execução
    E valida que todos os agentes referenciados existem
    E grava o ficheiro de pipeline
    E exibe resumo com modo "workflow" e cadeia de agentes
```

---

## Cenário 9: Criação de pipeline Deliberação com líder e pares

```gherkin
  Cenário: Criar pipeline Deliberação com flags completas
    Dado que existem os agentes "analyst", "reviewer" e "writer"
    Quando o utilizador executa "miniautogen pipeline create research --mode deliberation --leader analyst --participants reviewer,writer"
    Então o pipeline é criado com modo "deliberation"
    E o líder é "analyst"
    E os pares são "reviewer" e "writer"
    E todos os agentes referenciados são validados
    E o ficheiro de pipeline é gravado
```

---

## Cenário 10: Validação completa do projecto

```gherkin
Funcionalidade: Validação do projeto

  Cenário: Check detecta problemas de configuração
    Dado que o agente "analyst" referencia o motor "motor-inexistente"
    E o pipeline "research" referencia o agente "agente-removido"
    Quando o utilizador executa "miniautogen check"
    Então a saída reporta erro: motor "motor-inexistente" não encontrado
    E reporta erro: agente "agente-removido" não encontrado no pipeline "research"
    E o código de saída é diferente de 0

  Cenário: Check valida projeto consistente
    Dado que todos os motores, agentes e pipelines estão corretamente configurados
    Quando o utilizador executa "miniautogen check"
    Então a saída reporta todos os recursos como válidos
    E o código de saída é 0
```

---

## Cenário 11: Execução E2E de Workflow com sucesso

```gherkin
Funcionalidade: Execução de pipelines

  Cenário: Fluxo completo init-engine-agent-pipeline-check-run
    Dado que o utilizador executou "miniautogen init meu-projeto"
    E criou o motor "openai-gpt4" via "miniautogen engine create"
    E criou os agentes "extractor" e "transformer" vinculados ao motor
    E criou o pipeline "etl" em modo workflow com os agentes encadeados
    E executou "miniautogen check" com resultado válido
    Quando o utilizador executa "miniautogen run etl"
    Então o PipelineRunner gera um run_id único
    E emite o evento RUN_STARTED
    E o WorkflowRuntime executa "extractor" seguido de "transformer"
    E cada componente emite COMPONENT_STARTED e COMPONENT_FINISHED
    E o RunResult final tem status FINISHED
    E a saída exibe duração e métricas da execução
```

---

## Cenário 12: Deliberação multiagente com convergência

```gherkin
  Cenário: Deliberação converge em consenso
    Dado que o pipeline "research" está configurado em modo deliberation
    E o líder é "analyst" com pares "reviewer" e "writer"
    Quando o utilizador executa "miniautogen run research"
    Então o DeliberationRuntime inicia a deliberação
    E o líder "analyst" propõe uma decisão inicial
    E cada par emite a sua avaliação
    E o líder sintetiza as contribuições
    E a deliberação converge dentro do número máximo de rondas
    E o RunResult final tem status FINISHED
```

---

## Cenário 13: Agentic loop com terminação controlada

```gherkin
  Cenário: Loop agêntico termina por condição de paragem
    Dado que o pipeline "support" está configurado em modo loop
    E o roteador é "coordinator" com participantes "researcher" e "responder"
    E a condição de terminação é "task_complete"
    Quando o utilizador executa "miniautogen run support"
    Então o AgenticLoopRuntime inicia o ciclo
    E o roteador decide qual participante ativar em cada iteração
    E o ciclo termina quando a condição de paragem é satisfeita
    E o RunResult final tem status FINISHED
    E os eventos registam cada iteração do loop
```

---

## Cenário 14: Composição de modos em sequência

```gherkin
  Cenário: CompositeRuntime executa modos encadeados
    Dado que o pipeline "complexo" está configurado como composição
    E a primeira fase é um Workflow com agentes de recolha
    E a segunda fase é uma Deliberação com agentes de análise
    Quando o utilizador executa "miniautogen run complexo"
    Então o CompositeRuntime executa a primeira fase (Workflow)
    E passa o resultado como entrada da segunda fase (Deliberação)
    E cada fase emite os seus próprios eventos de ciclo de vida
    E o RunResult final agrega os resultados de ambas as fases
```

---

## Cenário 15: Execução com aprovação humana

```gherkin
  Cenário: ApprovalGate pausa execução para aprovação
    Dado que o pipeline "deploy" contém um ApprovalGate entre as fases
    Quando a execução atinge o ApprovalGate
    Então o sistema emite o evento APPROVAL_REQUESTED
    E a execução é suspensa
    E o estado é persistido via CheckpointStore

    Quando o operador aprova a continuação
    Então a execução retoma a partir do checkpoint
    E emite o evento APPROVAL_GRANTED
    E prossegue para a fase seguinte
```

---

## Cenário 16: Retomada de execução a partir de checkpoint

```gherkin
Funcionalidade: Execução durável

  Cenário: Retomar execução interrompida
    Dado que a execução "run-abc123" foi interrompida no componente 3 de 5
    E existe um checkpoint válido para "run-abc123"
    Quando o utilizador executa "miniautogen run research --resume run-abc123"
    Então o SessionRecovery localiza o último checkpoint
    E reconstrói o RunContext
    E emite o evento RUN_RESUMED
    E a execução retoma a partir do componente 4
    E os componentes 1, 2 e 3 não são re-executados
    E o RunResult final tem status FINISHED
```

---

## Cenário 17: Orçamento excedido

```gherkin
  Cenário: BudgetPolicy interrompe execução
    Dado que o pipeline "research" tem um limite de orçamento configurado
    E a execução acumula custos acima do limite
    Quando o próximo componente tenta executar
    Então a BudgetPolicy intercepta a execução
    E emite o evento BUDGET_EXCEEDED
    E o RunResult final tem status CANCELLED
    E a mensagem indica "orçamento excedido"
```

---

## Cenário 18: Gestão de sessões

```gherkin
Funcionalidade: Gestão de sessões

  Cenário: Listar sessões com filtros
    Dado que existem 5 sessões: 3 FINISHED, 1 FAILED, 1 CANCELLED
    Quando o utilizador executa "miniautogen sessions list --status FAILED"
    Então a saída exibe apenas 1 sessão com status FAILED
    E inclui run_id, pipeline, data de início e duração

  Cenário: Limpar sessões antigas
    Dado que existem sessões com mais de 30 dias
    Quando o utilizador executa "miniautogen sessions clean --older-than 30d"
    Então o sistema solicita confirmação
    E após confirmação, remove as sessões antigas
    E exibe o número de sessões removidas
```

---

## Cenário 19: Atualização in-place de agente

```gherkin
Funcionalidade: Atualização de recursos

  Cenário: Atualizar propriedade de agente preservando YAML
    Dado que o agente "analyst" tem o papel "Analista junior"
    E o ficheiro "agents/analyst.yml" contém comentários e formatação personalizada
    Quando o utilizador executa "miniautogen agent update analyst --role 'Analista senior'"
    Então apenas o campo "role" é alterado para "Analista senior"
    E os comentários existentes no YAML são preservados
    E a indentação original é mantida
    E os restantes campos permanecem inalterados
```

---

## Cenário 20: Integração com Gemini CLI Gateway

```gherkin
Funcionalidade: Integração com backends

  Cenário: Configurar e usar Gemini CLI Gateway como motor
    Dado que o Gemini CLI Gateway está disponível localmente
    Quando o utilizador executa "miniautogen engine create gemini-local --provider gemini-cli --endpoint localhost:8080"
    E cria o agente "researcher" vinculado ao motor "gemini-local"
    E cria o pipeline "local-research" em modo workflow com o agente
    E executa "miniautogen run local-research"
    Então o PipelineRunner comunica com o Gemini CLI Gateway
    E a execução completa com status FINISHED
    E os eventos registam a interação com o backend local
```

---

## Cenário 21: Inicialização do gateway em modo foreground

```gherkin
Funcionalidade: Gestão do servidor gateway

  Cenário: Inicialização do gateway em modo foreground
    Dado que o projeto está inicializado e um motor está configurado com endpoint local
    Quando o desenvolvedor executa o comando de arranque do servidor
    Então o gateway deve iniciar na porta configurada
    E o endpoint de saúde deve responder com estado operacional
    E os logs devem ser exibidos no terminal em tempo real
```

---

## Cenário 22: Gestão do gateway em modo daemon

```gherkin
  Cenário: Gestão do gateway em modo daemon
    Dado que o gateway está configurado para execução em segundo plano
    Quando o desenvolvedor inicia o servidor em modo daemon
    Então o processo deve ser iniciado em segundo plano com PID registado em .miniautogen/server.pid
    E o comando de estado deve reportar o gateway como ativo
    E o comando de paragem deve terminar o processo de forma limpa
```

---

## Cenário 23: Validação de projecto com gateway inacessivel

```gherkin
  Cenário: Validação de projeto com gateway inacessível
    Dado que um motor está configurado com endpoint local do gateway
    E que o gateway não está em execução
    Quando o desenvolvedor executa a validação do projeto
    Então o sistema deve reportar aviso de que o gateway local não está acessível
    E deve sugerir a execução do comando de arranque do servidor
```

---

## Cenário 24: Execução com entrada via --input

```gherkin
Funcionalidade: Fornecimento de entrada para execução

  Cenário: Executar pipeline com entrada direta
    Dado que o pipeline "etl" está configurado e válido
    Quando o utilizador executa "miniautogen run etl --input 'Analisar vendas Q4'"
    Então o PipelineRunner recebe o texto como entrada inicial
    E a execução procede normalmente com a entrada fornecida

  Cenário: Executar pipeline com entrada de ficheiro
    Dado que o pipeline "etl" está configurado e válido
    E existe o ficheiro "dados/prompt.txt" com conteúdo
    Quando o utilizador executa "miniautogen run etl --input @dados/prompt.txt"
    Então o conteúdo do ficheiro é lido como entrada inicial
    E a execução procede normalmente

  Cenário: Executar pipeline com entrada de stdin
    Dado que o pipeline "etl" está configurado e válido
    Quando o utilizador fornece texto via stdin e executa "miniautogen run etl"
    Então o conteúdo de stdin é lido como entrada inicial
    E a execução procede normalmente
```

---

## Cenário 25: Inspeção de recursos via show

```gherkin
Funcionalidade: Inspeção detalhada de recursos

  Cenário: Inspecionar motor em formato JSON
    Dado que o motor "openai-gpt4" está configurado
    Quando o utilizador executa "miniautogen engine show openai-gpt4 --format json"
    Então a saída é um objeto JSON válido
    E contém todos os campos do motor: nome, provedor, modelo, endpoint, capacidades

  Cenário: Inspecionar sessão de execução
    Dado que existe uma sessão com run_id "run-abc123"
    Quando o utilizador executa "miniautogen sessions show run-abc123"
    Então a saída exibe estado, eventos emitidos, mensagens e checkpoints
    E suporta --format json para saída estruturada
```

---

## Cenário 26: Dry-run de atualização

```gherkin
Funcionalidade: Pré-visualização de alterações

  Cenário: Dry-run mostra diferença sem aplicar
    Dado que o agente "analyst" tem o papel "Analista junior"
    Quando o utilizador executa "miniautogen agent update analyst --role 'Analista senior' --dry-run"
    Então a saída mostra a diferença entre o estado atual e o proposto
    E nenhuma alteração é aplicada ao ficheiro
    E o código de saída é 0
```

---

# Parte 3: Especificação funcional

## 1. Título e Contexto

**Produto:** MiniAutoGen CLI-First E2E
**Versão:** 3.1.0

**Visão:** O MiniAutoGen CLI é uma plataforma de orquestração multiagente 100% gerida via terminal. O CLI funciona como plano de controlo (Control Plane) único, permitindo ao desenvolvedor criar, modificar, listar, validar e executar todos os recursos do sistema -- motores LLM, agentes, pipelines -- sem nunca abrir um editor de texto.

**Objectivo Estratégico:** Um novo desenvolvedor consegue ter um pipeline multiagente a funcionar com LLM local em menos de 3 minutos, usando apenas o terminal. A experiência é guiada por wizards interactivos quando necessário e completamente silenciosa para automação CI/CD.

**Posicionamento Competitivo:** O MiniAutoGen combina as melhores práticas de ferramentas de referência:
- Auto-descoberta de contexto de projecto e extensibilidade via plugins (inspiração de CLIs modernos de desenvolvimento).
- Onboarding guiado via wizard, diagnósticos tipo `doctor`, gestão CRUD de recursos, configuração declarativa com overrides imperativos, modo dual interactivo/flags (inspiração de CLIs de gestão de infraestrutura).

**Execução Durável:** O sistema suporta execução durável com checkpoints, permitindo retomar pipelines interrompidos sem perda de progresso. Este diferenciador é crítico para pipelines longos com interações LLM custosas.

---

## 2. User Scenarios e Testing

### História Principal

> Como desenvolvedor de sistemas de IA, quero gerir todo o ciclo de vida de pipelines multiagente via terminal -- desde a configuração de motores LLM até a execução e monitoramento -- para ter controlo total, reprodutibilidade e integração com os meus fluxos de trabalho existentes.

### Cenários de Aceitação por Tipo de Recurso

**Motores (Engines):**
- Criar motor em modo interactivo com todas as perguntas guiadas.
- Criar motor em modo silencioso sem nenhum prompt.
- Listar motores configurados com detalhes.
- Inspecionar motor individual com `engine show`.
- Atualizar parâmetro de motor preservando configuração existente.
- Pré-visualizar atualização com `--dry-run`.

**Agentes:**
- Criar agente vinculado a motor existente.
- Impedir criação de agente sem motores disponíveis.
- Excluir agente que não está em uso.
- Bloquear exclusão de agente referenciado em pipeline.
- Inspecionar agente individual com `agent show`.
- Atualizar propriedade de agente preservando YAML.
- Pré-visualizar atualização com `--dry-run`.

**Pipelines:**
- Criar pipeline em cada modo (workflow, deliberation, loop, composite).
- Validar que todos os agentes referenciados existem.
- Adicionar/remover participantes de pipeline existente.
- Inspecionar pipeline individual com `pipeline show`.
- Pré-visualizar atualização com `--dry-run`.
- Configurar composição via wizard de seleção de pipelines.

**Servidor (Gateway):**
- Iniciar gateway em modo foreground com logs em tempo real.
- Iniciar gateway em modo daemon com PID registado em `.miniautogen/server.pid`.
- Parar gateway de forma limpa.
- Consultar estado operacional do gateway (running, degraded, unreachable, stopped).
- Validar acessibilidade do gateway via `miniautogen check`.

**Execução:**
- Executar pipeline com resultado FINISHED.
- Fornecer entrada via `--input`, `--input @ficheiro` ou stdin.
- Retomar execução a partir de checkpoint.
- Respeitar políticas de timeout, budget e retry.
- Pausar para aprovação humana e retomar.

**Operações:**
- Listar sessões com filtros.
- Inspecionar sessão individual com `sessions show`.
- Limpar sessões antigas.

---

## 3. Requisitos Funcionais

### Fase 1 -- Fundação e Motores (Sprint A)

**FR-001: Scaffolding via init**
O sistema deve criar a estrutura completa de um projecto multiagente com um único comando. O scaffold inclui o ficheiro de configuração principal (`miniautogen.yml`), os diretórios para agentes, pipelines e templates. O projecto gerado deve ser imediatamente válido para receber recursos. Se o diretório de destino não estiver vazio, o comando bloqueia por defeito. Com `--force`, preserva ficheiros existentes e adiciona apenas os que faltam. O sistema nunca sobrescreve ficheiros existentes sem `--force`.

**FR-002: Engine CRUD (create, list, show, update)**
O sistema deve suportar a gestão completa de motores LLM via CLI:
- **create:** Regista um novo motor com provedor, modelo, endpoint, chave de API e capacidades. Valida o esquema BackendConfig antes de gravar. Grava apenas referência a variável de ambiente para credenciais.
- **list:** Exibe todos os motores configurados em formato tabular com nome, provedor, modelo e capacidades.
- **show:** Exibe detalhes completos de um motor específico. Suporta `--format json`.
- **update:** Modifica parâmetros individuais de um motor existente, preservando os demais campos e a estrutura do ficheiro. Suporta `--dry-run`.

**FR-003: Modo dual (interactivo/silencioso) para comandos de motores**
Todos os comandos de criação e atualização de motores devem operar em dois modos:
- **Interactivo:** Quando parâmetros obrigatórios estão em falta, o CLI inicia um wizard passo-a-passo que guia o utilizador.
- **Silencioso:** Quando todos os parâmetros são fornecidos via flags, o comando executa sem nenhum prompt interactivo, retornando apenas o código de saída.

**FR-004: Atualizações in-place com preservação de YAML**
Ao atualizar qualquer recurso, o sistema deve:
- Ler o ficheiro YAML existente.
- Alterar apenas o(s) campo(s) solicitado(s).
- Regravar o ficheiro preservando comentários, indentação e ordem das chaves.
- Não reorganizar ou reformatar seccoes não modificadas.

**FR-005: Validação de esquema antes da escrita**
Toda operação de criação ou atualização de recurso deve validar o objecto resultante contra o esquema correspondente (BackendConfig, AgentSpec, PipelineConfig) antes de o persistir em disco. Dados inválidos nunca devem ser gravados.

**FR-006: Validação de projecto via check (expandido)**
O comando `miniautogen check` deve validar a integridade completa do projecto em dois níveis:

Validação de configuração:
- Motores referenciados por agentes existem na configuração.
- Agentes são válidos contra o esquema AgentSpec.
- Pipelines referenciam agentes que existem.
- Configuração de modo de pipeline é consistente (ex: deliberation tem líder definido).
- Não existem dependências circulares ou referências órfãs.

Validação de runtime:
- Se existirem motores com endpoint local, verifica a acessibilidade do gateway.
- Resolução de motores e conectividade de endpoints.

O comando executa ambas por defeito. Futuro: `--config-only`, `--runtime-only`. O comando deve retornar código de saída 0 para projecto válido é diferente de 0 para projecto com erros, com relatório detalhado.

### Fase 2 -- Agentes (Sprint B)

**FR-007: Agent CRUD (create, list, show, update, delete)**
O sistema deve suportar a gestão completa de agentes via CLI:
- **create:** Cria definição de agente com papel, objectivo, motor vinculado e configurações adicionais. Grava em `agents/<nome>.yml`.
- **list:** Exibe todos os agentes em formato tabular com nome, papel e motor vinculado.
- **show:** Exibe detalhes completos de um agente específico. Suporta `--format json`.
- **update:** Modifica propriedades individuais do agente, preservando estrutura YAML. Suporta `--dry-run`.
- **delete:** Remove o agente com verificação de segurança.

**FR-008: Vínculo de motor durante criação de agente**
A criação de agente deve obrigatoriamente vincular o agente a um motor existente. Em modo interactivo, o sistema lista os motores disponíveis para seleção. Em modo silencioso, o motor é especificado via flag `--engine`.

**FR-009: Exclusão segura com verificação de uso**
Antes de excluir um agente, o sistema deve:
- Verificar se o agente está referenciado em algum pipeline.
- Se estiver em uso, bloquear a exclusão e informar quais pipelines o referenciam.
- Se não estiver em uso, proceder com a exclusão.

**FR-010: Modo dual para comandos de agentes**
Os comandos de criação e atualização de agentes seguem o mesmo paradigma dual descrito em FR-003. Adicionalmente, se não existirem motores configurados, o modo interactivo deve sugerir a criação de um motor antes de prosseguir.

**FR-011: Validação de agente contra esquema AgentSpec**
Todo agente criado ou atualizado deve ser validado contra o esquema AgentSpec, que define campos obrigatórios (nome, papel, motor) e opcionais (objectivo, temperatura, tokens máximos).

### Fase 3 -- Pipelines e Coordenação (Sprint C)

**FR-012: Pipeline CRUD (create, list, show, update)**
O sistema deve suportar a gestão completa de pipelines via CLI:
- **create:** Cria configuração de pipeline com modo de coordenação e agentes participantes.
- **list:** Exibe pipelines em formato tabular com nome, modo e participantes.
- **show:** Exibe detalhes completos de um pipeline específico. Suporta `--format json`.
- **update:** Adiciona ou remove agentes, modifica parâmetros de coordenação. Suporta `--dry-run`.

**FR-013: Wizard de configuração específico por modo**
Cada modo de coordenação tem um fluxo de configuração interactivo distinto:
- **Workflow:** Pergunta quais agentes encadear e em que ordem.
- **Deliberation:** Pergunta quem é o líder, quem são os pares e o número máximo de rondas.
- **Loop:** Pergunta qual agente é o roteador, quais são os participantes e a condição de terminação.
- **Composite:** Lista pipelines existentes e permite selecionar quais encadear. Para cada pipeline, permite definir mapeadores de entrada/saída opcionais. Gera os CompositionStep correspondentes.

**FR-014: Validação de referências de agentes em pipelines**
A criação e atualização de pipelines deve validar que todos os agentes referenciados existem no diretório `agents/`. Referências a agentes inexistentes devem ser rejeitadas com mensagem de erro específica.

**FR-015: Modo dual para comandos de pipelines**
Os comandos de criação e atualização de pipelines seguem o paradigma dual. Em modo silencioso, todos os parâmetros (modo, agentes, configuração específica) são fornecidos via flags.

### Fase 4 -- Execução e Runtime

**FR-016: Execução de pipeline via PipelineRunner**
O comando `miniautogen run <pipeline>` deve delegar a execução ao PipelineRunner, que:
- Gera um `run_id` único para cada execução.
- Carrega a configuração do pipeline e resolve todas as dependências.
- Instancia o runtime adequado ao modo de coordenação.
- Gere o ciclo de vida completo da execução.
- Produz um RunResult com status final, duração e métricas.

O comando suporta fornecimento de entrada via `--input "texto"` (entrada directa), `--input @caminho/ficheiro.txt` (leitura de ficheiro) ou stdin (quando nenhum `--input` é fornecido).

**FR-017: Eventos de ciclo de vida (taxonomia canônica v1)**
O PipelineRunner deve emitir eventos estruturados ao longo de todo o ciclo de vida da execução. A taxonomia canônica de eventos de execução (versão 1) cobre:
- Ciclo de vida de execução (RUN_STARTED, RUN_FINISHED, RUN_RESUMED).
- Componentes (COMPONENT_STARTED, COMPONENT_FINISHED).
- Ferramentas e interações.
- Retentativas (RETRY_ATTEMPTED, RETRY_EXHAUSTED).
- Políticas (BUDGET_EXCEEDED, TIMEOUT_REACHED).
- Aprovações (APPROVAL_REQUESTED, APPROVAL_GRANTED, APPROVAL_DENIED).
- Recuperação (CHECKPOINT_CREATED).
- Modos de coordenação.
- Backend drivers.

Cada evento contém: `event_type`, `timestamp`, `correlation_id`, `run_id`, `payload`.

**FR-018: Aplicação de timeout**
O PipelineRunner deve aplicar limites de tempo configurados:
- Timeout global por execução.
- Timeout por componente individual.
Ao exceder o limite, a execução é cancelada com status TIMED_OUT e emissão do evento correspondente.

**FR-019: Portões de aprovação (human-in-the-loop)**
O sistema deve suportar ApprovalGate como componente de pipeline que:
- Pausa a execução e emite APPROVAL_REQUESTED.
- Persiste o estado via checkpoint.
- Retoma após aprovação do operador.
- Suporta aprovação (APPROVAL_GRANTED) ou rejeição (APPROVAL_DENIED).

**FR-020: Política de retentativa**
O sistema deve implementar RetryPolicy que:
- Actua apenas em erros transientes e de adaptador.
- Respeita número máximo de tentativas e backoff configurado.
- Emite RETRY_ATTEMPTED a cada tentativa.
- Emite RETRY_EXHAUSTED quando esgota tentativas.
- Não retenta erros permanentes, de validação ou de configuração.

**FR-021: Política de orçamento**
O sistema deve implementar BudgetPolicy que:
- Monitoriza custos acumulados durante a execução.
- Compara com o limite configurado após cada componente.
- Ao exceder o limite, cancela a execução com evento BUDGET_EXCEEDED.
- O RunResult reflecte status CANCELLED com motivo de orçamento.

**FR-022: Execução dos modos de coordenação**
O sistema deve suportar quatro modos de coordenação:
- **Workflow (WorkflowRuntime):** Execução sequencial de agentes em cadeia. Saída de um componente alimenta o seguinte.
- **Deliberation (DeliberationRuntime):** Líder propõe, pares avaliam, líder sintetiza. Repete até convergência ou limite de rondas.
- **Agentic Loop (AgenticLoopRuntime):** Roteador decide qual participante activar em cada iteração. Ciclo repete até condição de terminação.
- **Composite (CompositeRuntime):** Encadeia múltiplos modos em sequência. Resultado de uma fase alimenta a seguinte.

### Fase 5 -- Persistência e Operação

**FR-023: Persistência de estado**
O sistema deve persistir três tipos de dados via stores dedicados:
- **RunStore:** Metadados de execuções (run_id, status, timestamps, métricas).
- **MessageStore:** Mensagens trocadas entre agentes durante a execução.
- **CheckpointStore:** Snapshots do estado da execução para recuperação.

**FR-024: Recuperação de sessão a partir de checkpoints**
O SessionRecovery deve:
- Localizar o último checkpoint válido para um dado `run_id`.
- Reconstruir o RunContext completo.
- Retomar a execução a partir do componente seguinte ao último checkpoint.
- Emitir RUN_RESUMED com referência ao `run_id` original.
- Não re-executar componentes já concluídos.

**FR-025: Listagem e inspeção de sessões**
O comando `miniautogen sessions list` deve suportar:
- Listagem de todas as sessões em formato tabular.
- Filtragem por status (FINISHED, FAILED, CANCELLED, TIMED_OUT).
- Filtragem por período (ex: `--since 7d`).
- Exibição de: run_id, pipeline, status, data de início, duração.

O comando `miniautogen sessions show <run_id>` deve exibir detalhes completos da execução: estado actual, eventos emitidos, mensagens trocadas, checkpoints registados. Suporta `--format json`.

**FR-026: Limpeza de sessões por idade**
O comando `miniautogen sessions clean` deve:
- Aceitar parâmetro `--older-than` para especificar a idade mínima.
- Solicitar confirmação antes de apagar.
- Remover sessões (metadados, mensagens e checkpoints associados).
- Exibir o número de sessões removidas.

**FR-027: Observabilidade de eventos (taxonomia canônica v1)**
Todos os eventos emitidos pelo sistema devem:
- Conter `correlation_id` para rastreio transversal.
- Conter `timestamp` com precisão adequada.
- Ser armazenados de forma estruturada e consultável.
- Cobrir a taxonomia canônica de eventos de execução (versão 1) sem lacunas no ciclo de vida.

### Fase 6 -- Servidor e Gateway

**FR-028 [Servidor - Arranque]: Arranque do gateway local**
O sistema deve permitir iniciar o gateway local em modo foreground (com output de logs no terminal) ou em modo daemon (em segundo plano com PID registado em `.miniautogen/server.pid`). Em modo daemon, o sistema verifica se já existe um processo activo antes de iniciar. PID stale é limpo automaticamente. Parâmetros configuráveis incluem: porta, host, timeout de pedidos e concorrência máxima.

**FR-029 [Servidor - Paragem]: Paragem do gateway local**
O sistema deve permitir parar um gateway em execução de forma limpa, libertando a porta e terminando o processo. A paragem deve ser graciosa, aguardando a conclusão de pedidos em curso antes de terminar.

**FR-030 [Servidor - Estado]: Estado operacional do gateway**
O sistema deve reportar o estado operacional do gateway com os seguintes estados:
- `running` -- activo e health check OK.
- `degraded` -- processo activo mas health check falhando.
- `unreachable` -- PID registado mas processo não responde.
- `stopped` -- nenhum processo activo.

Informações adicionais: porta, PID, uptime e resultado do health check.

**FR-031 [Servidor - Validação Integrada]: Validação de acessibilidade do gateway**
O comando de validação do projecto (`miniautogen check`) deve verificar a acessibilidade do gateway quando existir um motor configurado com endpoint local. Se o gateway não estiver acessível, deve reportar aviso e sugerir a execução do comando de arranque do servidor.

---

## 4. Requisitos Não Funcionais

**NFR-001: Modo dual (interactivo/silencioso)**
Todo comando de criação e atualização de recurso deve suportar dois modos de operação:
- **Interactivo:** Wizard passo-a-passo quando parâmetros obrigatórios estão em falta.
- **Silencioso:** Execução sem prompts quando todos os parâmetros são fornecidos via flags.
O modo é determinado automaticamente pela presença ou ausência de flags obrigatórias. Não existe flag explícita para alternar entre modos.

**NFR-002: Preservação de YAML in-place**
As operações de atualização devem preservar:
- Comentários existentes no ficheiro YAML.
- Indentação original.
- Ordem das chaves não modificadas.
- Linhas em branco e formatação estrutural.
O sistema deve usar técnicas de manipulação de YAML que respeitem a estrutura documental, não apenas os dados.

**NFR-003: Validação de esquema antes da escrita (< 100ms)**
Toda validação de esquema (BackendConfig, AgentSpec, PipelineConfig) deve completar em menos de 100 milissegundos. Dados inválidos nunca devem ser persistidos em disco.

**NFR-004: Observabilidade -- 100% de eventos com correlation_id e timestamp**
Todo evento emitido pelo sistema deve conter obrigatoriamente `correlation_id` e `timestamp`. Não devem existir eventos sem estes campos. A cobertura da taxonomia canônica de eventos de execução (versão 1) deve ser completa, sem lacunas no ciclo de vida.

**NFR-005: Desempenho de políticas (< 10ms por componente)**
As políticas laterais (RetryPolicy, BudgetPolicy, TimeoutPolicy) devem introduzir no máximo 10 milissegundos de overhead por componente executado. As políticas operam como observadores laterais e não devem bloquear o fluxo principal desnecessariamente.

**NFR-006: Isolamento de erros de adaptador**
Falhas em adaptadores de backend (motores LLM) não devem corromper o RunContext nem o estado interno do PipelineRunner. Erros de adaptador devem ser encapsulados, classificados e propagados sem efeitos colaterais no estado da execução.

**NFR-007: Determinismo**
Dada a mesma entrada (configuração, dados, seed), o sistema deve produzir a mesma sequência de eventos. A ordem de emissão de eventos é determinística para o mesmo grafo de execução. Não-determinismo introduzido pelos LLMs (respostas variadas) não inválida esta propriedade -- o determinismo refere-se a lógica de orquestração, não ao conteudo gerado.

**NFR-008: Tempo até primeiro pipeline (< 3 minutos)**
Um novo desenvolvedor deve conseguir ir de zero a um pipeline multiagente em execução em menos de 3 minutos, usando apenas o terminal. O fluxo completo (init, engine create, agent create, pipeline create, check, run) deve ser fluido é guiado.

**NFR-009 [Servidor - Arranque Rápido]: Tempo de arranque do gateway (< 3 segundos)**
O gateway deve estar operacional e a responder ao health check em menos de 3 segundos após o comando de arranque. Este requisito é essencial para manter a fluidez do fluxo de trabalho do desenvolvedor.

**NFR-010: Dry-run para comandos de atualização**
Todo comando de atualização (`update`) deve suportar `--dry-run` que mostra a diferença entre o estado actual e o proposto, sem aplicar alterações. A saída deve permitir ao utilizador verificar o impacto antes de confirmar.

**NFR-011: Segurança de credenciais**
O sistema nunca grava segredos (chaves de API, tokens, passwords) em texto limpo em ficheiros de configuração. O sistema nunca exibe segredos em logs, outputs ou mensagens de erro. Credenciais são resolvidas exclusivamente via variáveis de ambiente em tempo de execução. O formato de referência e `${NOME_DA_VARIAVEL}`.

**NFR-012: Contrato de UX de erros**
O CLI deve seguir um contrato rigoroso de experiência de erros:
- Codigos de saída padronizados: 0 (sucesso), 1 (erro de validação), 2 (erro de configuração), 3 (erro de execução), 4 (erro de IO/ficheiro).
- Mensagens de erro acionáveis com sugestão de resolução. Exemplo: "Motor 'xyz' não encontrado. Crie um com `miniautogen engine create`."
- O CLI nunca exibe stack traces por defeito. Stack traces só são visiveis com `--verbose`.

**NFR-013: Backup antes de escrita YAML**
Antes de cada escrita que modifique ficheiro existente, o sistema cria copia de segurança (`.bak`). A escrita é atômica: completa com sucesso ou nenhuma alteração é aplicada. O ficheiro original só é substituído após a escrita completa do novo conteudo.

**NFR-014: Formato de saída**
Inglês como língua nativa do CLI (output e logs). Documentação multilingue. Output estruturado em JSON disponível via `--format json` em todos os comandos de listagem e inspeção. Na Fase 1, inglês é a única língua do terminal, sem sistema de internacionalização.

**NFR-015: Modo offline**
O sistema é totalmente funcional offline quando o desenvolvedor utiliza apenas motores locais (gateway local, motores locais). O CLI, validação, execução e gestão de sessões operam sem acesso a internet. Apenas motores com endpoints remotos requerem conectividade.

**NFR-016: Sem restrições lógicas de recursos**
O sistema não impõe limites ao número de agentes, motores ou pipelines por projecto. A restrição é a capacidade do sistema operativo (memória, disco, processos).

---

## 5. Entidades-Chave

O modelo de domínio do MiniAutoGen CLI-First organiza-se em torno das seguintes entidades:

**Engine (BackendConfig)**
Motor LLM configurado no sistema. Contém: nome, provedor, modelo, endpoint, credenciais (referência a variável de ambiente), capacidades. É a entidade de primeira classe para integração com backends de IA. Cada agente deve estar vinculado a exactamente um motor.

**AgentSpec**
Definição de um agente com identidade e capacidades. Contém: nome, papel (role), objectivo (goal), motor vinculado (engine), configurações de geração (temperatura, tokens máximos). Gravado como ficheiro individual em `agents/`.

**PipelineConfig**
Configuração de um pipeline de coordenação multiagente. Contém: nome, modo de coordenação (workflow, deliberation, loop, composite), lista de agentes participantes, parâmetros específicos do modo (líder, rondas, condição de terminação). Define como os agentes colaboram.

**PipelineRunner**
Executor central de pipelines. Responsável por: gerar run_id, resolver dependências, instanciar o runtime adequado, gerir o ciclo de vida, aplicar políticas, emitir eventos, produzir RunResult.

**RunContext**
Estado mutável de uma execução em curso. Contém: run_id, mensagens acumuladas, metadados, métricas parciais. Flui entre componentes durante a execução.

**RunResult**
Resultado final de uma execução. Contém: status (FINISHED, FAILED, CANCELLED, TIMED_OUT), duração, métricas agregadas, erros (se aplicável).

**ExecutionEvent**
Evento estruturado do ciclo de vida. Contém: event_type (da taxonomia canônica v1), timestamp, correlation_id, run_id, payload específico. Imutável após emissão.

**ExecutionPolicy**
Política lateral que observa e reage a eventos da execução. Tipos: RetryPolicy, BudgetPolicy, TimeoutPolicy. Operam como observadores -- não fazem parte do fluxo principal.

**Runtimes de Coordenação**
Estratégias de execução que implementam modos de coordenação:
- WorkflowRuntime: cadeia sequencial.
- DeliberationRuntime: líder + pares + convergência.
- AgenticLoopRuntime: roteador + participantes + condição de terminação.
- CompositeRuntime: composição de modos.

**ApprovalGate**
Componente de pipeline que pausa a execução para aprovação humana. Persiste estado via checkpoint e retoma após decisão do operador.

**SessionRecovery**
Mecanismo de recuperação que reconstrói o RunContext a partir de checkpoints e retoma execuções interrompidas.

**Stores (RunStore, MessageStore, CheckpointStore)**
Camada de persistência para metadados de execução, mensagens e checkpoints respectivamente.

**Servidor/Gateway**
Servidor HTTP local que encapsula backends LLM e os expõe como API HTTP compatível com OpenAI. Gere o ciclo de vida do processo (arranque, paragem, estado), regista PID em `.miniautogen/server.pid` em modo daemon e fornece endpoint de saúde para verificação de acessibilidade. É o intermediário que permite ao AgentAPIDriver comunicar com backends locais.

---

## 6. Decisões de Arquitectura Pendentes

**DA-001: UX do wizard interactivo versus flags puras**
- **Questão:** Qual o equilíbrio entre guia interactivo e configuração via flags?
- **Recomendação:** Adotar modo dual (NFR-001). O modo é determinado automaticamente. Wizards interactivos guiam novos utilizadores; flags completas servem automação. Ambos os modos produzem exactamente o mesmo resultado em disco.

**DA-002: Preservação de YAML em atualizações**
- **Questão:** Como garantir que atualizações in-place preservam comentários e formatação?
- **Recomendação:** Utilizar técnicas de manipulação de YAML que operem sobre a árvore documental (preservando comentários e formatação) em vez de serializar/deserializar apenas os dados. A implementação deve tratar o YAML como documento, não como estrutura de dados simples.

**DA-003: Comportamento de exclusão de recursos**
- **Questão:** Soft delete (marcar como inactivo) ou hard delete (remover ficheiro)?
- **Recomendação:** Hard delete com verificações de segurança. Antes de excluir, o sistema verifica dependências (agente em uso por pipeline, motor em uso por agente). Se existirem dependências, a exclusão é bloqueada com mensagem informativa. Esta abordagem é mais simples e alinha-se com o paradigma de ficheiros em disco.

**DA-004: Complexidade de configuração de pipelines**
- **Questão:** Como gerir a complexidade de configuração para modos avançados (composite, loop com condições complexas)?
- **Recomendação:** Para modos simples (workflow), o wizard cobre 100% da configuração. Para modos complexos (composite, loop com lógica avançada), o wizard gera um esqueleto de configuração que o utilizador pode refinar. O modo silencioso via flags aceita a configuração completa para todos os modos.

---

## 7. Decisões Tomadas (Clarificações Resolvidas)

As seguintes questões foram resolvidas com decisões concretas:

**DT-001: Conflitos de atualização YAML**
Política de last-write-wins com aviso. O sistema verifica a data de modificação do ficheiro antes de gravar. Se houve alteração externa desde a leitura, exibe aviso mas permite forçar com `--force`. Backup automático antes de cada escrita (`.bak`).

**DT-002: Limites de recursos**
Sem restrições lógicas. O sistema não impõe limites ao número de agentes, motores ou pipelines. A restrição é a capacidade do sistema operativo.

**DT-003: Migração de versão do esquema**
Fora de escopo para Fase 1. A validação estrita rejeita schemas incompatíveis. Futuro: comando `miniautogen migrate`.

**DT-004: Segredos e credenciais**
O sistema nunca grava chaves de API em texto limpo nos ficheiros de configuração. O wizard interactivo aceita a chave temporariamente para validar a conexão, mas grava apenas a referência a variável de ambiente (formato: `${NOME_DA_VARIAVEL}`). O motor resolve em tempo de execução.

**DT-005: Modo offline**
Totalmente funcional offline quando o desenvolvedor utiliza apenas motores locais (gateway local, motores locais). O CLI, validação, execução e gestão de sessões operam sem acesso a internet.

**DT-006: Formato de saída**
Inglês como língua nativa do CLI (output e logs). Documentação multilingue. Output estruturado em JSON disponível via `--format json`.

**DT-007: Internacionalização**
Inglês como única língua do terminal na Fase 1. Sem sistema de internacionalização por agora.

---

## 8. Dependências e Pressupostos

**Dependências:**
- O sistema depende de pelo menos um backend LLM acessível (local ou remoto) para execução de pipelines.
- A estrutura do projecto segue convenções de diretório definidas pelo comando `init`.
- Os ficheiros de configuração usam formato YAML.
- O CLI opera num terminal com suporte a entrada interactiva (para modo wizard).

**Pressupostos:**
- O desenvolvedor tem o MiniAutoGen instalado e acessível via `miniautogen` no PATH.
- O sistema de ficheiros permite leitura e escrita nos diretórios do projecto.
- Para backends remotos, existe conectividade de rede.
- Para modo silencioso, o ambiente fornece as variáveis de ambiente necessárias (ex: chaves de API).

---

## 9. Fora de Escopo

Os seguintes itens não fazem parte desta especificação:

- Interface gráfica (GUI) ou dashboard web.
- Gestão de utilizadores, autenticação ou controlo de acesso.
- Distribuição de execuções em múltiplas máquinas (execução distribuída).
- Marketplace de agentes ou templates.
- Integração directa com repositórios de código (Git hooks, CI/CD pipelines).
- Versionamento de recursos (agentes, pipelines).
- Hot-reload de configuração durante execução.
- Métricas de desempenho agregadas entre execuções (analytics).
- Migração automática de esquemas entre versões (Fase 1).

---

## 10. Riscos Conhecidos

**R-001: Complexidade do modo dual**
Manter paridade entre modo interactivo e silencioso para todos os comandos CRUD aumenta a superfície de testes. Cada comando tem efetivamente dois caminhos de execução que devem produzir resultados idênticos.
- **Mitigação:** Abstrair a recolha de parâmetros (wizard ou flags) da lógica de negócio. A camada de validação e persistência é partilhada.

**R-002: Preservação de YAML**
A manipulação de YAML com preservação de comentários e formatação é tecnicamente desafiadora. Erros nesta camada podem corromper ficheiros de configuração.
- **Mitigação:** Testes extensivos com ficheiros YAML que contém comentários, indentação variada e estruturas complexas. Backups automáticos antes de escrita (NFR-013).

**R-003: Consistência de referências cruzadas**
Com motores, agentes e pipelines como entidades separadas, a integridade referencial depende de verificações em tempo de escrita e do comando `check`.
- **Mitigação:** Validação obrigatória antes de persistência (FR-005). Comando `check` como rede de segurança. Exclusão segura (FR-009).

**R-004: Experiência do wizard para modos complexos**
Modos avançados (composite, loop com lógica condicional) podem ser difíceis de configurar via wizard interactivo sem sobrecarregar o utilizador.
- **Mitigação:** Wizards geram esqueletos para modos complexos (DA-004). Documentação com exemplos para cada modo.

**R-005: Tempo até primeiro pipeline**
O objectivo de < 3 minutos (NFR-008) é ambicioso e depende de fatores externos (velocidade de instalação, disponibilidade de backend).
- **Mitigação:** Medir e otimizar o fluxo crítico. Fornecer backends locais pré-configurados como opção rápida.

**R-006: Durabilidade de checkpoints**
Falhas durante a escrita de checkpoints podem resultar em estado inconsistente que impossibilita a recuperação.
- **Mitigação:** Escrita atômica de checkpoints (escrever em ficheiro temporário, renomear). Validação de integridade ao ler checkpoints.

---

## 11. Fontes Consultadas

- Arquitectura interna do MiniAutoGen: contratos de domínio, PipelineRunner, protocolos de coordenação.
- Especificação de backends e AgentAPIDriver.
- Padrões de CLI de referência:
  - Auto-descoberta de contexto, extensibilidade via plugins, ponto de entrada simples (benchmark de CLIs de desenvolvimento).
  - Onboarding guiado via wizard, diagnósticos tipo `doctor`, gestão CRUD de recursos, configuração declarativa com overrides imperativos, modo dual interactivo/flags (benchmark de CLIs de gestão de infraestrutura).
- Taxonomia canônica de erros do MiniAutoGen (transient, permanent, validation, timeout, cancellation, adapter, configuration, state_consistency).
- Taxonomia canônica de eventos de execução (versão 1).
- Padrões de execução durável e checkpoint-based recovery.

---

## 12. Review e Acceptance Checklist (GATE)

O documento é considerado aprovado quando todos os critérios seguintes forem satisfeitos:

| # | Critério | Status |
|---|----------|--------|
| 1 | Todos os comandos CLI (init, engine, agent, pipeline, check, run, sessions, server) estão especificados com entradas e saídas | APROVADO |
| 2 | Modo dual (interactivo/silencioso) está definido para todos os comandos CRUD | APROVADO |
| 3 | Cenários BDD cobrem os fluxos críticos identificados (26 cenários) | APROVADO |
| 4 | Requisitos funcionais estão agrupados por fase de entrega (6 fases) | APROVADO |
| 5 | Requisitos não funcionais incluem métricas mensuráveis (tempo, overhead, cobertura) | APROVADO |
| 6 | Entidades-chave incluem Engine e Servidor/Gateway como entidades de primeira classe | APROVADO |
| 7 | Decisões de arquitectura pendentes têm recomendação | APROVADO |
| 8 | Riscos conhecidos têm mitigação definida | APROVADO |
| 9 | Fora de escopo está explicitamente declarado | APROVADO |
| 10 | Documento descreve o sistema como caixa preta (sem nomes de bibliotecas de implementação) | APROVADO |
| 11 | Vocabulário de domínio preservado (PipelineRunner, WorkflowRuntime, RunContext, AgentSpec, etc.) | APROVADO |
| 12 | Objectivo de < 3 minutos para primeiro pipeline está documentado como NFR | APROVADO |
| 13 | Execução durável (checkpoints, recovery) está especificada | APROVADO |
| 14 | Exclusão segura com verificação de dependências está especificada | APROVADO |
| 15 | Preservação de YAML in-place está especificada como requisito | APROVADO |
| 16 | Gestão do ciclo de vida do gateway (server start/stop/status) está especificada | APROVADO |
| 17 | Comandos show/inspect estão especificados para todos os recursos | APROVADO |
| 18 | Dry-run para comandos de atualização está especificado | APROVADO |
| 19 | Contrato de UX de erros (exit codes, mensagens acionáveis) está definido | APROVADO |
| 20 | Segurança de credenciais está definida como NFR | APROVADO |
| 21 | Clarificações necessárias foram todas resolvidas com decisões concretas | APROVADO |
| 22 | Separação conceptual CLI Administrativo vs Operações está documentada | APROVADO |
| 23 | Backup antes de escrita YAML está especificado como NFR | APROVADO |
