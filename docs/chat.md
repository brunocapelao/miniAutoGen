# Módulo `chat.py`

## Visão Geral

O módulo `chat.py` é parte integrante do framework MiniAutoGen, responsável por gerenciar sessões de chat em grupo e manter um registro estruturado das interações. Este módulo lida com a armazenagem de mensagens, gestão de agentes participantes e manutenção do contexto da conversa.

## Classes e Métodos

### Classe `Chat`

#### Inicialização
- `__init__(self, storage_path='groupchat_data', custom_df=None)`: 
  - **Parâmetros**:
    - `storage_path` (str): Caminho para o diretório de armazenamento dos dados.
    - `custom_df` (pd.DataFrame, opcional): DataFrame personalizado para a criação de uma tabela customizada.
  - **Descrição**: Inicializa uma instância do chat, preparando o armazenamento e carregando o contexto existente.

#### Métodos Privados
- `_ensure_storage_directory_exists()`: Garante a existência do diretório de armazenamento.
- `_load_state()`: Carrega o estado atual do contexto do chat a partir de um arquivo JSON.

#### Persistência de Dados
- `persist()`: Salva o contexto atual do chat em um arquivo JSON.

#### Gestão de Mensagens
- `add_message(sender_id, message, additional_info=None)`: Adiciona uma mensagem individual ao chat.
- `add_messages(messages)`: Adiciona múltiplas mensagens ao chat, aceitando tanto DataFrames quanto listas de dicionários.
- `remove_message(message_id)`: Remove uma mensagem específica do chat.
- `get_messages(type='dataframe')`: Retorna todas as mensagens armazenadas no formato especificado ('dataframe' ou 'json').

#### Conversão de Mensagens
- `_messages_to_dataframe(messages)`: Converte mensagens para DataFrame do pandas.
- `_messages_to_json(messages)`: Converte mensagens para uma lista de dicionários no formato JSON.

#### Gestão de Contexto e Agentes
- `get_current_context()`: Retorna o contexto atual da conversa.
- `update_context(new_context)`: Atualiza o contexto da conversa com novas informações.
- `add_agent(agent)`: Adiciona um novo agente à conversa.
- `remove_agent(agent_id)`: Remove um agente da conversa com base em seu identificador.

## Uso do Módulo

Para utilizar o módulo `chat.py` no seu projeto, primeiro importe-o e inicialize uma instância do `Chat`. Você pode adicionar ou remover mensagens e agentes conforme necessário, além de atualizar o contexto da conversa. O módulo também permite que você recupere todas as mensagens armazenadas em diferentes formatos para análises ou relatórios.

## Exemplo de Uso

```python
from chat import Chat

# Inicializando o chat
chat_session = Chat()

# Adicionando uma mensagem
chat_session.add_message(sender_id="agent1", message="Olá, Mundo!")

# Recuperando mensagens
messages = chat_session.get_messages(type='json')
print(messages)

# Atualizando o contexto
chat_session.update_context({"tema": "Introdução ao MiniAutoGen"})
```

Este módulo é uma ferramenta essencial para desenvolvedores que trabalham com sistemas de conversação multi-agentes, fornecendo uma maneira estruturada e eficiente de gerenciar interações complexas em chats de grupo.