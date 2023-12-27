from agent import Agent
from pipeline.pipeline import Pipeline, ChatPipelineState
import logging

# Configuração básica do logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class ChatAdmin(Agent):
    def __init__(self, agent_id, name, role, pipeline, group_chat, goal, max_rounds):
        super().__init__(agent_id, name, role)
        self.pipeline = pipeline
        self.group_chat = group_chat
        self.goal = goal
        self.round = 0
        self.max_rounds = max_rounds
        self.running = False
        self.logger = logging.getLogger(__name__)

    def start(self):
        self.running = True
        self.logger.info("Chat Admin started.")

    def stop(self):
        self.running = False
        self.logger.info("Chat Admin stopped.")

    def run(self):
        self.start()
        state = ChatPipelineState(group_chat=self.group_chat, chat_admin=self)
        while self.round < self.max_rounds and self.running:
            self.execute_round(state)
        self.stop()

    def execute_round(self, state):
        self.logger.info(f"Executing round {self.round + 1}")
        state = self.pipeline.run(state)
        self.round += 1
        self.group_chat.persist()  # Salva o estado atual do chat

    @staticmethod
    def from_json(json_data, pipeline, group_chat, goal, max_rounds):
        """
        Cria uma instância de ChatAdmin a partir de um dicionário JSON.

        Args:
            json_data (dict): Dicionário contendo dados do ChatAdmin.
            pipeline (Pipeline): Pipeline a ser usado pelo ChatAdmin.
            group_chat (GroupChat): O chat em grupo associado ao ChatAdmin.
            goal (any): Objetivo do ChatAdmin.
            max_rounds (int): Número máximo de rodadas.

        Returns:
            ChatAdmin: Uma nova instância de ChatAdmin.
        """
        required_keys = ['agent_id', 'name', 'role']
        if not all(key in json_data for key in required_keys):
            raise ValueError("JSON deve conter as chaves 'agent_id', 'name', e 'role'.")

        agent_id = json_data['agent_id']
        name = json_data['name']
        role = json_data['role']

        return ChatAdmin(agent_id, name, role, pipeline, group_chat, goal, max_rounds)
