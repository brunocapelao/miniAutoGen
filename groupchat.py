import sqlite3
import pandas as pd
import json
import os
from datetime import datetime


class GroupChat:
    """
    Classe que representa um grupo de chat.

    Args:
        storage_path (str): Caminho para o diretório de armazenamento dos dados do grupo de chat.
        custom_df (pandas.DataFrame): DataFrame personalizado para criar tabelas customizadas no banco de dados.

    Attributes:
        storage_path (str): Caminho para o diretório de armazenamento dos dados do grupo de chat.
        db_path (str): Caminho para o arquivo do banco de dados.
        agent_list_path (str): Caminho para o arquivo que armazena a lista de agentes.
        context_path (str): Caminho para o arquivo que armazena o contexto da conversa.
        agentList (dict): Dicionário para armazenar informações dos agentes.
        context (dict): Dicionário para armazenar o contexto da conversa.
        connection (sqlite3.Connection): Conexão com o banco de dados.
        custom_schema (bool): Indica se o esquema do banco de dados é personalizado.

    Methods:
        _create_custom_tables(df): Cria tabelas com base nas colunas do DataFrame fornecido.
        _create_default_tables(): Cria a tabela padrão.
        _build_query(table, **kwargs): Constrói a query SQL para inserção de dados.
        _load_state(): Carrega o estado do grupo de chat a partir dos arquivos.
        persist(): Persiste o estado do grupo de chat nos arquivos.
        add_message(**kwargs): Adiciona uma mensagem ao grupo de chat.
        remove_message(message_id): Remove uma mensagem do grupo de chat.
        get_messages(): Retorna todas as mensagens do grupo de chat.
        get_current_context(): Retorna o contexto atual da conversa.
        update_context(new_context): Atualiza o contexto da conversa com novas informações.
        add_agent(agent_id, agent_info): Adiciona um novo agente à conversa.
        remove_agent(agent_id): Remove um agente da conversa.
    """

    def __init__(self, storage_path='groupchat_data', custom_df=None):
        self.storage_path = storage_path
        self.db_path = os.path.join(storage_path, 'groupchat.db')
        self.agent_list_path = os.path.join(storage_path, 'agent_list.txt')
        self.context_path = os.path.join(storage_path, 'context.json')
        self.agentList = []
        self.context = {}
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)

        with sqlite3.connect(self.db_path) as connection:
            self.connection = connection
            self.custom_schema = custom_df is not None
            if self.custom_schema:
                self._create_custom_tables(custom_df)
            else:
                self._create_default_tables()
            self._load_state()

    def _create_custom_tables(self, df):
        # Cria tabelas com base nas colunas do DataFrame fornecido
        columns = ', '.join([f"{col} TEXT" for col in df.columns])
        create_table_query = f"CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, {columns})"
        with self.connection:
            self.connection.execute(create_table_query)

    def _create_default_tables(self):
        # Cria a tabela padrão
        with self.connection:
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY,
                    sender_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp DATETIME NOT NULL
                )
            """)

    def _build_query(self, table, **kwargs):
        columns = ', '.join(kwargs.keys())
        placeholders = ', '.join(['?'] * len(kwargs))
        values = tuple(kwargs.values())
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        return query, values

    def _load_state(self):
        if os.path.exists(self.context_path):
            with open(self.context_path, 'r') as file:
                self.context = json.load(file)

    def persist(self):
        """
        Persiste os dados da lista de agentes e do contexto em arquivos JSON.
        """
        
        with open(self.context_path, 'w') as file:
            json.dump(self.context, file)

    def add_message(self, **kwargs):
        """
        Adiciona uma mensagem ao grupo de chat.

        Parâmetros:
        - sender_id (int): ID do remetente da mensagem.
        - message (str): Conteúdo da mensagem.

        Retorna:
        Nenhum.

        Exemplo:
        add_message(sender_id=1, message='Olá, mundo!')
        """
        if self.custom_schema:
            query, values = self._build_query('messages', **kwargs)
        else:
            # Lógica padrão para adicionar mensagens
            sender_id = kwargs.get('sender_id')
            message = kwargs.get('message')
            timestamp = datetime.now()
            query, values = self._build_query(
                'messages', sender_id=sender_id, message=message, timestamp=timestamp)

        with self.connection:
            self.connection.execute(query, values)

    def remove_message(self, message_id):
        """
        Remove a message from the database based on its ID.

        Args:
            message_id (int): The ID of the message to be removed.

        Returns:
            None
        """
        with self.connection:
            self.connection.execute("""
                DELETE FROM messages WHERE id = ?
            """, (message_id,))

    def get_messages(self):
        """
        Retrieves all messages from the database.

        Returns:
            pandas.DataFrame: A DataFrame containing all messages.
        """
        with self.connection:
            df = pd.read_sql_query("SELECT * FROM messages", self.connection)
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
        self.agentList = [agent for agent in self.agentList if agent.agent_id != agent_id]

    def __del__(self):
        if self.connection:
            self.connection.close()
