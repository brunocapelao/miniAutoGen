import json
import os
from storage.chatstorage import ChatStorage
import pandas as pd

class Chat:
    def __init__(self, storage_path='groupchat_data', custom_df=None):
        self.storage_path = storage_path
        self._ensure_storage_directory_exists()
        self.db_path = os.path.join(storage_path, 'groupchat.db')
        self.storage = ChatStorage(self.db_path)
        self.agentList = []
        self.context_path = os.path.join(storage_path, 'context.json')
        self.context = self._load_state()
        self.custom_df = custom_df

        if self.custom_df is not None:
            self.storage.create_custom_table_from_df(self.custom_df, "custom_messages")

    def _ensure_storage_directory_exists(self):
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)

    def _load_state(self):
        if os.path.exists(self.context_path):
            try:
                with open(self.context_path, 'r') as file:
                    return json.load(file)
            except json.JSONDecodeError as e:
                # Handle JSON decoding error (Consider logging the error)
                return {}
        return {}

    def persist(self):
        with open(self.context_path, 'w') as file:
            json.dump(self.context, file)

    def add_message(self, sender_id, message, additional_info=None):
        self.storage.add_message(sender_id, message, additional_info)

    def remove_message(self, message_id):
        self.storage.remove_message(message_id)

    def get_messages(self, type='dataframe'):
        """
        Retorna todas as mensagens do armazenamento no formato especificado.
        Args:
            type (str): Especifica o formato do retorno ('dataframe' ou 'json').
        Returns:
            pd.DataFrame ou list: Dependendo do valor de type, retorna um DataFrame ou lista de dicionários.
        """
        try:
            messages = self.storage.get_messages()

            if type == 'dataframe':
                return self._messages_to_dataframe(messages)
            elif type == 'json':
                return self._messages_to_json(messages)
            else:
                raise ValueError("Tipo desconhecido. Use 'dataframe' ou 'json'.")
        except Exception as e:
            # Tratamento de erro (Considere logging)
            raise

    def _messages_to_dataframe(self, messages):
        """ Converte mensagens para DataFrame. """
        return pd.DataFrame([
            {
                'id': message.id,
                'sender_id': message.sender_id,
                'message': message.message,
                'timestamp': message.timestamp,
                'additional_info': message.get_additional_info()
            }
            for message in messages
        ])

    def _messages_to_json(self, messages):
        """ Converte mensagens para lista de dicionários no formato JSON. """
        return [
            {
                'id': message.id,
                'sender_id': message.sender_id,
                'message': message.message,
                'timestamp': message.timestamp.isoformat(),
                'additional_info': message.get_additional_info()
            }
            for message in messages
        ]

    def get_current_context(self):
        """ Retorna o contexto atual da conversa. """
        return self.context

    def update_context(self, new_context):
        """ Atualiza o contexto da conversa com novas informações. """
        self.context.update(new_context)

    def add_agent(self, agent):
        """ Adiciona um novo agente à conversa, se ainda não estiver presente. """
        if agent.agent_id not in [a.agent_id for a in self.agentList]:
            self.agentList.append(agent)

    def remove_agent(self, agent_id):
        """ Remove um agente da conversa com base em seu identificador. """
        self.agentList = [agent for agent in self.agentList if agent.agent_id != agent_id]
