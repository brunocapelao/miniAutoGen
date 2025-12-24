import asyncio
import logging
from typing import List, Dict, Optional, Any
from miniautogen.chat.chat import Chat
from miniautogen.agent.agent import Agent
from miniautogen.chat.chatadmin import ChatAdmin
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.pipeline.components.components import (
    NextAgentSelectorComponent, AgentReplyComponent, TerminateChatComponent,
    LLMResponseComponent
)
from miniautogen.llms.llm_client import LLMClientInterface
from miniautogen.storage.in_memory_repository import InMemoryChatRepository

# 1. Mock LLM Client to simulate responses without API keys
class MockLLMClient(LLMClientInterface):
    async def get_model_response(self, prompt: List[Dict[str, str]], model_name: Optional[str] = None, temperature: float = 1.0) -> str:
        # Simulate network latency
        await asyncio.sleep(0.5)
        # Determine response based on last message to simulate conversation flow
        last_msg = prompt[-1]['content'] if prompt else ""
        if "hello" in last_msg.lower():
            return "Hi there! How can I help you structurally today?"
        elif "bye" in last_msg.lower():
            return "TERMINATE"
        else:
            return f"I processed: {last_msg}"

# 2. Setup Logging
logging.basicConfig(level=logging.INFO)

async def main():
    print("--- Starting Async Architecture Demo ---")

    # Initialize Repository and Chat
    repo = InMemoryChatRepository()
    chat = Chat(repository=repo)

    # Initialize Mock LLM
    mock_llm = MockLLMClient()

    # Define Agents
    # User Agent (simulated pipeline)
    user_agent = Agent("user_1", "User", "User Role")
    # For the user, we can just inject a predefined message via context or input component.
    # But for this automated demo, let's just seed the chat with a message.

    # Bot Agent with Pipeline
    # Pipeline: Select Next -> Generate Reply -> Terminate Check
    # Actually, Agent pipeline usually generates the CONTENT.
    # The Admin pipeline manages the TURN.

    # Let's fix the Agent Pipeline: It should take the conversation history and produce a reply string.
    # We need a component that formats history for LLM + LLM Component.

    class SimplePromptBuilder(Pipeline): # Simplified inline component/pipeline
        pass

    # We will use the existing LLMResponseComponent but we need to feed it a 'prompt' in the state.
    # Let's make a custom component for this demo to glue things together.
    from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent
    class HistoryToPromptComponent(PipelineComponent):
        async def process(self, state: Any) -> Any:
            chat = state.get_state().get('group_chat')
            msgs = await chat.get_messages(limit=10)
            # Format for LLM
            prompt = [{"role": "user", "content": m.content} for m in msgs]
            state.update_state(prompt=prompt)
            return state

    bot_pipeline = Pipeline([
        HistoryToPromptComponent(),
        LLMResponseComponent(mock_llm)
    ])

    bot_agent = Agent("bot_1", "Assistant", "Helpful Assistant", pipeline=bot_pipeline)

    chat.add_agent(user_agent)
    chat.add_agent(bot_agent)

    # Seed Chat
    print("Seeding chat...")
    await chat.add_message("user_1", "Hello assistant!")

    # Setup Admin to manage the loop
    # Admin Pipeline: Select Next Agent -> Execute Agent's Reply -> Check Termination
    admin_pipeline = Pipeline([
        NextAgentSelectorComponent(),
        AgentReplyComponent(),
        TerminateChatComponent()
    ])

    admin = ChatAdmin("admin", "Admin", "Admin Role", admin_pipeline, chat, "Test Goal", max_rounds=5)

    # Run the Loop
    print("Running Admin Loop...")
    await admin.run()

    # Verification
    msgs = await chat.get_messages()
    print("\n--- Final Message History ---")
    for m in msgs:
        print(f"[{m.timestamp}] {m.sender_id}: {m.content}")

    assert len(msgs) >= 2
    print("\n--- Success: Async Flow Verified ---")

if __name__ == "__main__":
    asyncio.run(main())
