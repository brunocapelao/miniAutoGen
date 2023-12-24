# MiniAutoGen

![](miniautogen.png)

## Descrição
O principal objetivo do MiniAutoGen é habilitar aplicações de próxima geração para Modelos de Linguagem de Grande Escala (LLMs) por meio de [conversas multi-agentes](docs/chat-mult-agent.md). O framework oferece uma estrutura flexível para a criação e experimentação com sistemas multi-agentes, permitindo a personalização de agentes conversacionais, a gestão de padrões flexíveis de conversação e a automação de processos. Este objetivo é atingido pela implementação de uma interface de conversação unificada entre os agentes e mecanismos de resposta automática, explorando as capacidades dos LLMs otimizados para chat, e acomodando uma ampla gama de aplicações práticas.

Este projeto é inspirado no [AutoGen](https://github.com/microsoft/autogen) 

## Funcionalidades

O MiniAutoGen se caracteriza por ser uma plataforma para aplicações de Modelos de Linguagem de Grande Escala (LLMs) em conversas multi-agentes. Sua descrição principal inclui:

1. **Conversação Multi-Agentes:** Capacidade de realizar conversas envolvendo múltiplos agentes, cada um com habilidades distintas, aumentando a complexidade e sofisticação das interações.

2. **Customização de Agentes:** Permite ajustar os agentes para atender a requisitos específicos, incluindo comportamento, reações e padrões de resposta.

3. **Padrões de Conversação Flexíveis:** Suporta diversos estilos de conversação, incluindo a possibilidade de agentes iniciarem diálogos, reagirem automaticamente ou solicitarem intervenção humana.

4. **Coordenação entre Agentes:** Fornece um framework para que os agentes colaborem eficientemente, visando atingir objetivos comuns.


## Como Usar
### Pré-requisitos
- Chave de API da OpenAI.


### Configuração
1. Clone o repositório para o seu sistema local.
2. Instale as dependências necessárias usando `pip install -r requirements.txt`.
3. Defina sua chave de API da OpenAI em um arquivo `.env` como `OPENAI_API_KEY=<sua_chave>`.


### Executando o Chatbot
## Exemplo de Uso

Este exemplo demonstra como configurar e iniciar um chat interativo com dois agentes e um mestre humano. O objetivo é planejar uma viagem de 15 dias para a Argentina. O primeiro agente, "Mestre das Rotas", é um assistente virtual especializado em viagens, enquanto o segundo agente, "Dany", representa um viajante empolgado com sua primeira viagem internacional. O mestre do chat, neste caso, é um humano que guia a conversa e toma decisões sobre o andamento do chat.
git s
```python
# Criação dos agentes e do mestre
agente1 = Agent("Mestre das rotas", "<detalhes do agente Mestre das Rotas>")
agente2 = Agent("Dany", "A romântica, muito empolgada em fazer sua primeira viagem internacional.")

mestre_chat = HumanoMestre("Mestre")

# Configuração inicial do chat
contexto_inicial = "Definir o roteiro de uma viagem para a Argentina."
chat = Chat("Programar uma viagem de 15 dias para Argentina", "/caminho/para/salvar/o/chat")
chat.contexto = contexto_inicial
chat.adicionar_participante(agente1)
chat.adicionar_participante(agente2)
chat.mestre = mestre_chat

# Execução do chat
chat.run()


## Estrutura do Código
- `Agent`: Classe base para os agentes participantes do chat.
- `Mestre`: Subclasse de `Agent` para o agente mestre do chat.
- `HumanoMestre`: Classe para representar um mestre humano no chat.
- `Chat`: Classe principal que gerencia o fluxo do chat, incluindo a persistência e carregamento de conversas.
- `prompt_manager`: Módulo que contém funções para gerar prompts para a API da OpenAI.
