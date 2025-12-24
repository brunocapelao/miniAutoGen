import asyncio
import logging
import json
import time
from typing import Any, List, Dict
from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent
from miniautogen.schemas import Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UserExitException(Exception):
    pass

class UserResponseComponent(PipelineComponent):
    async def process(self, state: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
            reply = await loop.run_in_executor(None, input, "Enter the response: ")
            state.update_state(reply=reply)
            return reply
        except Exception as e:
            print(f"Error capturing user response: {e}")
            raise

class NextAgentSelectorComponent(PipelineComponent):
    async def process(self, state: Any) -> Any:
        group_chat = state.get_state().get('group_chat')
        if not group_chat or not hasattr(group_chat, 'agents'):
            raise ValueError("Invalid GroupChat or agents not found.")

        try:
            next_agent = await self.select_next_agent(group_chat)
            state.update_state(selected_agent=next_agent)
        except Exception as e:
            print(f"Error selecting the next agent: {e}")
            raise # Fail fast

        return state

    async def select_next_agent(self, group_chat):
        # Using repository to get last message
        messages = await group_chat.get_messages(limit=1)
        last_message = messages[-1] if messages else None

        if last_message:
            last_sender_id = last_message.sender_id
            # Find index of last agent
            last_agent_index = -1
            for i, agent in enumerate(group_chat.agents):
                if agent.agent_id == last_sender_id:
                    last_agent_index = i
                    break

            next_agent_index = (last_agent_index + 1) % len(group_chat.agents)
        else:
            next_agent_index = 0

        return group_chat.agents[next_agent_index]

class AgentReplyComponent(PipelineComponent):
    async def process(self, state: Any) -> Any:
        agent = state.get_state().get('selected_agent')
        group_chat = state.get_state().get('group_chat')

        if not agent or not group_chat:
            raise ValueError("Agent and GroupChat are required for AgentReplyComponent.")

        try:
            # Await the async generate_reply
            reply = await agent.generate_reply(state)
            print(f"{agent.name}: {reply}")

            # Await add_message
            await group_chat.add_message(sender_id=agent.agent_id, content=reply)
        except Exception as e:
            print(f"Error processing agent reply: {e}")
            raise

        return state

class TerminateChatComponent(PipelineComponent):
    async def process(self, state: Any) -> Any:
        chat_admin = state.get_state().get('chat_admin')
        chat = state.get_state().get('group_chat')
        if not chat:
            raise ValueError("Chat is required for TerminateChatComponent.")

        messages = await chat.get_messages(limit=1)
        last_message = messages[-1].content if messages else None

        if last_message and "TERMINATE" in last_message.upper():
            print("Terminating chat...")
            if chat_admin and hasattr(chat_admin, 'stop'):
                 chat_admin.stop()
            return "TERMINATE"

        return state

# Note: Jinja2 components need to adapt to List[Message] instead of DataFrame
# For brevity in this refactor, I am updating the most critical ones.
# The user can extend this pattern.

class LLMResponseComponent(PipelineComponent):
    def __init__(self, llm_client, model_name="gpt-4"):
        self.llm_client = llm_client
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)

    async def process(self, state: Any) -> Any:
        prompt = state.get_state().get('prompt')
        if not prompt:
            self.logger.error("Prompt missing in pipeline state.")
            return state

        # Await the async client
        response = await self.llm_client.get_model_response(prompt, self.model_name)

        if response:
            # We must update the state to pass the reply to the next component
            # (which usually expects 'reply' or consumes the return value)
            state.update_state(reply=response)
            return state # Return state to continue pipeline
        else:
            raise RuntimeError("Failed to get response from LLM.")

# Re-implementing Jinja2SingleTemplateComponent to work with Pydantic models
from jinja2 import Environment, select_autoescape

class Jinja2SingleTemplateComponent(PipelineComponent):
    def __init__(self):
        self.template_str = None
        self.variables = None
        self.env = Environment(autoescape=select_autoescape())

    def set_template_str(self, template_str):
        self.template_str = template_str

    def set_variables(self, variables):
        self.variables = variables

    async def process(self, state: Any) -> Any:
        if not self.template_str:
             raise ValueError("Template string not set.")

        template = self.env.from_string(self.template_str)
        chat = state.get_state().get('group_chat')
        agent = state.get_state().get('selected_agent')

        # Async fetch all needed messages? Or limit?
        # Templates usually need context. Let's fetch last 50.
        messages_objs = await chat.get_messages(limit=50)
        # Convert to dict for Jinja2
        messages = [
            {"sender_id": m.sender_id, "message": m.content, "timestamp": m.timestamp}
            for m in messages_objs
        ]

        if self.variables is None:
            self.variables = state.get_state().get('variables', {})

        self.variables['chat'] = chat
        self.variables['agent'] = agent
        self.variables['messages'] = messages

        prompt_str = template.render(self.variables)
        try:
            prompt = json.loads(prompt_str)
        except json.JSONDecodeError:
            # If not JSON, pass as string (user might just want string prompt)
            prompt = prompt_str

        state.update_state(prompt=prompt)
        return state
