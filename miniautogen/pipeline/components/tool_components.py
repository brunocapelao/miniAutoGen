import json
import logging
from .pipelinecomponent import PipelineComponent
from ...llms.llm_client import LLMClientInterface

# Basic logger configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ToolSelectionComponent(PipelineComponent):
    """
    A pipeline component that uses an LLM to decide whether to use a tool.

    This component analyzes the conversation and the available tools for an agent.
    It then prompts an LLM to determine if a tool should be called. If so, it
    updates the pipeline state with the selected tool's name and arguments.
    """

    def __init__(self, llm_client: LLMClientInterface, model_name: str = "gpt-4"):
        """
        Initializes the ToolSelectionComponent.

        Args:
            llm_client (LLMClientInterface): The LLM client to use for deciding.
            model_name (str): The name of the model to use.
        """
        self.llm_client = llm_client
        self.model_name = model_name

    def process(self, state):
        """
        Processes the state to select a tool.

        Args:
            state (ChatPipelineState): The current state of the pipeline.

        Returns:
            ChatPipelineState: The updated state.
        """
        agent = state.get_state().get('selected_agent')
        if not agent or not agent.tools:
            logger.info("Agent has no tools, skipping tool selection.")
            state.update_state(tool_call=None)
            return state

        chat = state.get_state().get('group_chat')
        messages = chat.get_messages('json')

        # We only need the last message for this decision, but context could be added.
        last_message = messages[-1]['message'] if messages else ""

        prompt = self._build_prompt(agent.tools, last_message)

        try:
            response_text = self.llm_client.get_model_response(prompt, self.model_name)
            tool_call = self._parse_llm_response(response_text)
            state.update_state(tool_call=tool_call)
            if tool_call:
                logger.info(f"LLM decided to call tool: {tool_call['name']}")
        except Exception as e:
            logger.error(f"Error during tool selection LLM call: {e}")
            state.update_state(tool_call=None)

        return state

    def _build_prompt(self, tools, last_message):
        """Builds the prompt for the LLM to select a tool."""
        tools_json = json.dumps([{"name": tool.name, "description": tool.description} for tool in tools], indent=2)

        system_prompt = f"""You are an intelligent assistant that can use tools to answer questions.
You have access to the following tools:
{tools_json}

Based on the user's last message, should you use one of these tools?
- If YES, respond with a JSON object with "name" and "arguments" keys. Example: {{"name": "tool_name", "arguments": {{"arg1": "value1"}}}}.
- If NO, respond with the word "None".

Do not add any extra explanation.
"""

        # The prompt format expects a list of messages
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": last_message}
        ]

    def _parse_llm_response(self, response: str):
        """
        Parses the LLM's response to find a tool call.
        Handles responses wrapped in markdown code fences.
        """
        if not response or response.strip().lower() == "none":
            return None

        # Clean the response by removing markdown fences and stripping whitespace
        clean_response = response.strip()
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]
        clean_response = clean_response.strip()

        try:
            tool_call_data = json.loads(clean_response)
            # Basic validation to ensure it's a valid tool call structure
            if isinstance(tool_call_data, dict) and "name" in tool_call_data and "arguments" in tool_call_data:
                return tool_call_data
            else:
                logger.warning(f"Parsed JSON is not a valid tool call object: {clean_response}")
                return None
        except json.JSONDecodeError:
            logger.warning(f"Failed to decode LLM response as JSON for tool call: {response}")
            return None


class ToolExecutionComponent(PipelineComponent):
    """
    A pipeline component that executes a selected tool.

    This component checks the pipeline state for a `tool_call`. If found, it
    finds the corresponding tool in the agent's tool list, executes it,
    and adds the output to the state.
    """

    def process(self, state):
        """
        Processes the state to execute a tool.

        Args:
            state (ChatPipelineState): The current state of the pipeline.

        Returns:
            ChatPipelineState: The updated state.
        """
        tool_call = state.get_state().get('tool_call')
        if not tool_call:
            state.update_state(tool_output=None)
            return state

        agent = state.get_state().get('selected_agent')
        if not agent or not agent.tools:
            logger.warning("Tool call requested but agent has no tools.")
            state.update_state(tool_output=None)
            return state

        tool_name = tool_call.get('name')
        tool_args = tool_call.get('arguments', {})

        # Find the tool by name
        selected_tool = next((t for t in agent.tools if t.name == tool_name), None)

        if not selected_tool:
            error_message = f"Tool '{tool_name}' requested but not found in agent's tool list."
            logger.error(error_message)
            state.update_state(tool_output=error_message)
            return state

        try:
            logger.info(f"Executing tool '{tool_name}' with arguments: {tool_args}")
            output = selected_tool.execute(**tool_args)
            state.update_state(tool_output=output)
            logger.info(f"Tool '{tool_name}' executed successfully.")
        except Exception as e:
            error_message = f"Error executing tool '{tool_name}': {e}"
            logger.error(error_message)
            state.update_state(tool_output=error_message)

        return state