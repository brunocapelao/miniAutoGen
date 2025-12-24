from ..agent.agent import Agent
from ..pipeline.pipeline import ChatPipelineState
import logging
import asyncio

# Basic logger configuration
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

    async def run(self):
        """
        Runs the chat rounds until the maximum number of rounds is reached or the Chat Admin is stopped.
        """
        self.start()
        state = ChatPipelineState(group_chat=self.group_chat, chat_admin=self)
        while self.round < self.max_rounds and self.running:
            await self.execute_round(state)
        self.stop()

    async def execute_round(self, state):
        """
        Executes a single round of the chat asynchronously.
        """
        self.logger.info(f"Executing round {self.round + 1}")

        # Await the pipeline execution
        state = await self.pipeline.run(state)

        self.round += 1
        # No more manual persist needed with proper Repository, but if we wanted checkpoints, we'd do it here.
        # self.group_chat.persist() - removed as it was file-system based.
        # Persistence is now handled per-message by the Repository.

    @staticmethod
    def from_json(json_data, pipeline, group_chat, goal, max_rounds):
        required_keys = ['agent_id', 'name', 'role']
        if not all(key in json_data for key in required_keys):
            raise ValueError("JSON must contain 'agent_id', 'name', and 'role' keys.")

        return ChatAdmin(json_data['agent_id'], json_data['name'], json_data['role'], pipeline, group_chat, goal, max_rounds)
