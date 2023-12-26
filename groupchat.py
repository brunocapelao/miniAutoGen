import json
import os
from storage.chatstorage import ChatStorage
import pandas as pd


class GroupChat:
    def __init__(self, storage_path='groupchat_data', custom_df=None):
        self.storage_path = storage_path
        self.db_path = os.path.join(storage_path, 'groupchat.db')
        self.agentList = []
        self.context = {}

        self.context_path = os.path.join(storage_path, 'context.json')
        self.context = self._load_state()
        self.custom_df = custom_df  # Definindo custom_df como um atributo da classe

        if self.custom_df is not None:  # Usando o atributo da classe
            self.storage.create_custom_table_from_df(
                self.custom_df, "custom_messages")

        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)
        self.storage = ChatStorage(self.db_path)

    def _load_state(self):
        if os.path.exists(self.context_path):
            with open(self.context_path, 'r') as file:
                return json.load(file)
        return {}

    def persist(self):
        with open(self.context_path, 'w') as file:
            json.dump(self.context, file)

    def add_message(self, sender_id, message):
        self.storage.add_message(sender_id, message)

    def remove_message(self, message_id):
        self.storage.remove_message(message_id)

    def get_messages(self):
        """
        Retorna todas as mensagens do armazenamento como um DataFrame.

        Returns:
            pd.DataFrame: Um DataFrame contendo todas as mensagens.
        """
        messages = self.storage.get_messages()

        # Convert the list of message objects to a DataFrame
        df = pd.DataFrame([
            {
                'id': message.id,
                'sender_id': message.sender_id,
                'message': message.message,
                'timestamp': message.timestamp
            }
            for message in messages
        ])

        return df

    def get_current_context(self):
        """
        Retorna o contexto atual da conversa.
        """
        return self.context

    def update_context(self, new_context):
        """
        Atualiza o contexto da conversa com novas informações.

        Args:
            new_context (dict): Um dicionário contendo as informações atualizadas do contexto.
        """
        self.context.update(new_context)

    def add_agent(self, agent):
        """
        Adiciona um novo agente à conversa.

        Args:
            agent (Agent): Objeto Agent a ser adicionado.
        """
        self.agentList.append(agent)

    def remove_agent(self, agent_id):
        """
        Remove um agente da conversa com base em seu identificador.

        Args:
            agent_id (str): Identificador do agente a ser removido.
        """
        self.agentList = [
            agent for agent in self.agentList if agent.agent_id != agent_id]
