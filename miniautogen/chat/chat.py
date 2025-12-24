import asyncio
from typing import List, Optional, Dict, Any, Union
from miniautogen.storage.repository import ChatRepository
from miniautogen.storage.in_memory_repository import InMemoryChatRepository
from miniautogen.schemas import Message, ChatState
from miniautogen.agent.agent import Agent

class Chat:
    """
    Async Chat Orchestrator.
    """
    def __init__(self, repository: Optional[ChatRepository] = None):
        """
        Initializes a Chat object.

        Parameters:
        - repository (ChatRepository): The persistence layer. Defaults to InMemoryChatRepository.
        """
        self.repository = repository if repository else InMemoryChatRepository()
        self.agents: List[Agent] = []
        self.context = ChatState()

    async def add_message(self, sender_id: str, content: str, additional_info: Dict[str, Any] = None) -> Message:
        """
        Adds a message to the chat asynchronously.
        """
        msg = Message(sender_id=sender_id, content=content, additional_info=additional_info or {})
        await self.repository.add_message(msg)
        self.context.messages.append(msg) # Keep local context in sync if needed, or rely solely on repo
        return msg

    async def get_messages(self, limit: int = 100) -> List[Message]:
        """
        Retrieves the messages from the chat storage.
        """
        return await self.repository.get_messages(limit=limit)

    def add_agent(self, agent: Agent):
        """
        Adds an agent to the chat.
        """
        if agent.agent_id not in [a.agent_id for a in self.agents]:
            self.agents.append(agent)

    def remove_agent(self, agent_id: str):
        """
        Removes an agent from the chat.
        """
        self.agents = [agent for agent in self.agents if agent.agent_id != agent_id]
