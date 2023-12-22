# MiniAutoGen

![](miniautogen.png)

## Descrição
Este projeto implementa um chatbot interativo usando a API da OpenAI. O sistema permite a interação entre agentes automatizados e um mestre, que pode ser tanto um agente automatizado quanto um humano, para discutir um tema específico, neste caso, "Discutir um destino de viagem".


## Funcionalidades
- Chat interativo com suporte para múltiplos agentes.
- Mestre do chat que pode ser um agente automatizado ou um humano.
- Capacidade de persistir a conversa em arquivos CSV.
- Funcionalidades para carregar o estado do chat a partir de arquivos salvos.
- Integração com a API da OpenAI para respostas baseadas em GPT-3.5.


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
