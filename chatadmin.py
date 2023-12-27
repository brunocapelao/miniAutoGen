from agent import Agent
import logging

# Configuração básica do logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Cria um logger
logger = logging.getLogger(__name__)


class ChatAdmin(Agent):
    def __init__(self, agent_id, name, role, pipeline, group_chat, goal, max_rounds):
        super().__init__(agent_id, name, role, pipeline)
        self.group_chat = group_chat
        self.goal = goal
        self.round = 0
        self.max_rounds = max_rounds
        self.running = True

    def start(self):
        self.running = True
        logger.info("Chat Admin started.")

    def stop(self):
        self.running = False
        logger.info("Chat Admin stopped.")

    def run(self):
        self.start()
        while self.round < self.max_rounds and self.running:
            self.execute_round()
        self.stop()
        logger.info("Chat Admin is running.")

    def execute_round(self):
        if self.round < self.max_rounds and self.running:
            # Passando o group_chat como parte dos kwargs
            self.generate_reply(groupchat=self.group_chat, groupchatadmin=self)
            self.group_chat.persist()
            self.round += 1
        else:
            self.stop()
            logger.info("Stopping execution as conditions are met.")
