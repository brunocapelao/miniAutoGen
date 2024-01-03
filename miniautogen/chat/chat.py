import json
import os
import pandas as pd
from ..storage.chatstorage import ChatStorage

class Chat:
    def __init__(self, storage_path='groupchat_data', custom_df=None):
        """
        Initializes a Chat object.

        Parameters:
        - storage_path (str): The path to the storage directory. Default is 'groupchat_data'.
        - custom_df (pandas.DataFrame): A custom DataFrame to create a custom table in the storage. Default is None.
        """
        self.storage_path = storage_path
        self._ensure_storage_directory_exists()
        self.db_path = os.path.join(storage_path, 'groupchat.db')
        self.storage = ChatStorage(self.db_path)
        self.agentList = []
        self.context_path = os.path.join(storage_path, 'context.json')
        self.context = self._load_state()
        self.custom_df = custom_df

        if self.custom_df is not None:
            self.storage.create_custom_table_from_df(
                self.custom_df, "custom_messages")

    def _ensure_storage_directory_exists(self):
        """
        Ensures that the storage directory exists. If it doesn't exist, it creates the directory.
        """
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)

    def _load_state(self):
        """
        Loads the chat context from the context file.

        Returns:
        - dict: The loaded chat context.
        """
        if os.path.exists(self.context_path):
            try:
                with open(self.context_path, 'r') as file:
                    return json.load(file)
            except json.JSONDecodeError as e:
                return {}
        return {}

    def persist(self):
        """
        Persists the chat context to the context file.
        """
        with open(self.context_path, 'w') as file:
            json.dump(self.context, file)

    def add_message(self, sender_id, message, additional_info=None):
        """
        Adds a message to the chat storage.

        Parameters:
        - sender_id (str): The ID of the message sender.
        - message (str): The message content.
        - additional_info (dict): Additional information related to the message. Default is None.
        """
        self.storage.add_message(sender_id, message, additional_info)

    def add_messages(self, messages):
        """
        Adds multiple messages to the chat storage.

        Parameters:
        - messages (pandas.DataFrame or list): The messages to be added. It can be a pandas DataFrame or a list of dictionaries.
        """
        if isinstance(messages, pd.DataFrame):
            for _, row in messages.iterrows():
                self.add_message(
                    row['sender_id'], row['message'], row.get('additional_info'))
        elif isinstance(messages, list) and all(isinstance(m, dict) for m in messages):
            for message in messages:
                self.add_message(
                    message['sender_id'], message['message'], message.get('additional_info'))
        else:
            raise ValueError(
                "Messages must be a pandas DataFrame or a list of dictionaries.")

    def remove_message(self, message_id):
        """
        Removes a message from the chat storage.

        Parameters:
        - message_id (int): The ID of the message to be removed.
        """
        self.storage.remove_message(message_id)

    def get_messages(self, type='dataframe'):
        """
        Retrieves the messages from the chat storage.

        Parameters:
        - type (str): The type of the returned messages. It can be 'dataframe' or 'json'. Default is 'dataframe'.

        Returns:
        - pandas.DataFrame or list: The retrieved messages.
        """
        try:
            messages = self.storage.get_messages()

            if type == 'dataframe':
                return self._messages_to_dataframe(messages)
            elif type == 'json':
                return self._messages_to_json(messages)
            else:
                raise ValueError(
                 "Unknown type. Use 'dataframe' or 'json'.")
        except Exception as e:
            # Error handling (Consider logging)
            raise

    def _messages_to_dataframe(self, messages):
        """
        Converts the messages to a pandas DataFrame.

        Parameters:
        - messages (list): The messages to be converted.

        Returns:
        - pandas.DataFrame: The converted messages as a DataFrame.
        """
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
        """
        Converts the messages to a JSON format.

        Parameters:
        - messages (list): The messages to be converted.

        Returns:
        - list: The converted messages in JSON format.
        """
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
        """
        Retrieves the current chat context.

        Returns:
        - dict: The current chat context.
        """
        return self.context

    def update_context(self, new_context):
        """
        Updates the chat context with new values.

        Parameters:
        - new_context (dict): The new chat context values to be updated.
        """
        self.context.update(new_context)

    def add_agent(self, agent):
        """
        Adds an agent to the chat.

        Parameters:
        - agent (Agent): The agent to be added.
        """
        if agent.agent_id not in [a.agent_id for a in self.agentList]:
            self.agentList.append(agent)

    def remove_agent(self, agent_id):
        """
        Removes an agent from the chat.

        Parameters:
        - agent_id (str): The ID of the agent to be removed.
        """
        self.agentList = [
            agent for agent in self.agentList if agent.agent_id != agent_id]
