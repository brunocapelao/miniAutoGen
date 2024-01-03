from ..agent.agent import Agent
from ..pipeline.pipeline import ChatPipelineState
import logging

# Basic logger configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class ChatAdmin(Agent):
    def __init__(self, agent_id, name, role, pipeline, group_chat, max_rounds):
        """
        Initializes a ChatAdmin object.

        Args:
            agent_id (str): The ID of the agent.
            name (str): The name of the agent.
            role (str): The role of the agent.
            pipeline (Pipeline): The pipeline to be used for processing chat messages.
            group_chat (GroupChat): The group chat object.
            max_rounds (int): The maximum number of chat rounds to execute.
        """
        super().__init__(agent_id, name, role)
        self.pipeline = pipeline
        self.group_chat = group_chat
        self.round = 0
        self.max_rounds = max_rounds
        self.running = False
        self.logger = logging.getLogger(__name__)

    def start(self):
        """
        Starts the Chat Admin.
        """
        self.running = True
        self.logger.info("Chat Admin started.")

    def stop(self):
        """
        Stops the Chat Admin.
        """
        self.running = False
        self.logger.info("Chat Admin stopped.")

    def run(self):
        """
        Runs the chat rounds until the maximum number of rounds is reached or the Chat Admin is stopped.
        """
        self.start()
        state = ChatPipelineState(group_chat=self.group_chat, chat_admin=self)
        while self.round < self.max_rounds and self.running:
            self.execute_round(state)
        self.stop()

    def execute_round(self, state):
        """
        Executes a single round of the chat.

        Args:
            state (ChatPipelineState): The current state of the chat pipeline.
        """
        self.logger.info(f"Executing round {self.round + 1}")
        state = self.pipeline.run(state)
        self.round += 1
        self.group_chat.persist()  # Save the current chat state

    @staticmethod
    def from_json(json_data, pipeline, group_chat, goal, max_rounds):
        """
        Creates a ChatAdmin object from JSON data.

        Args:
            json_data (dict): The JSON data containing the agent information.
            pipeline (Pipeline): The pipeline to be used for processing chat messages.
            group_chat (GroupChat): The group chat object.
            goal (str): The goal of the chat.
            max_rounds (int): The maximum number of chat rounds to execute.

        Returns:
            ChatAdmin: The created ChatAdmin object.

        Raises:
            ValueError: If the JSON data is missing any of the required keys.
        """
        required_keys = ['agent_id', 'name', 'role']
        if not all(key in json_data for key in required_keys):
            raise ValueError("JSON must contain 'agent_id', 'name', and 'role' keys.")

        agent_id = json_data['agent_id']
        name = json_data['name']
        role = json_data['role']

        return ChatAdmin(agent_id, name, role, pipeline, group_chat, goal, max_rounds)
