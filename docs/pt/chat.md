# Módulo `chat.py`

Para a visão arquitetural completa, consulte [C4 Nível 2: Containers lógicos](architecture/02-containers.md) e [C4 Nível 3: Componentes internos](architecture/03-componentes.md).

## Visão geral

`Chat` é o núcleo de conversação da biblioteca. No estado atual, ele não persiste mensagens em arquivo nem usa DataFrame como mecanismo principal. Em vez disso, delega armazenamento a uma implementação de `ChatRepository`.

## Responsabilidades

- registrar mensagens com `add_message`;
- consultar histórico com `get_messages`;
- manter a lista de agentes ativos na conversa;
- manter um `ChatState` local;
- sincronizar o histórico local com o repositório.

## Persistência atual

O `Chat` recebe um `repository` opcional no construtor:

- se nenhum for informado, usa `InMemoryChatRepository`;
- se um repositório assíncrono SQL for informado, passa a persistir mensagens nesse backend.

## Principais métodos

### `add_message(sender_id, content, additional_info=None)`

- cria um objeto `Message`;
- persiste a mensagem via `repository.add_message`;
- adiciona a mensagem a `context.messages`.

### `get_messages(limit=100)`

- consulta o repositório e retorna uma lista de `Message`.

### `add_agent(agent)` e `remove_agent(agent_id)`

- gerenciam os participantes registrados no chat.

## Uso típico

```python
from miniautogen.chat.chat import Chat
from miniautogen.storage.in_memory_repository import InMemoryChatRepository

chat = Chat(repository=InMemoryChatRepository())
```
