from typing import Optional, List
from ..pipeline.pipeline import Pipeline
from ..tools.tool import Tool


class Agent:
    """
    Represents an agent in the system.

    Attributes:
        agent_id (str): The ID of the agent.
        name (str): The name of the agent.
        role (str): The role of the agent.
        pipeline (Optional[Pipeline]): The pipeline used to process the state. Defaults to None.
        tools (List[Tool]): A list of tools the agent can use. Defaults to an empty list.
        status (str): The status of the agent. Defaults to "available".
    """

    def __init__(self, agent_id: str, name: str, role: str, pipeline: Optional[Pipeline] = None, tools: Optional[List[Tool]] = None):
        """
        Initializes a new instance of the Agent class.

        Args:
            agent_id (str): The ID of the agent.
            name (str): The name of the agent.
            role (str): The role of the agent.
            pipeline (Optional[Pipeline]): The pipeline used to process the state. Defaults to None.
            tools (Optional[List[Tool]]): A list of tools the agent can use. Defaults to None.
        """
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.pipeline = pipeline
        self.tools = tools if tools is not None else []
        self.status = "available"

    def generate_reply(self, state):
        """
        Generates a reply based on the given state.

        Args:
            state (State): The state to process.

        Returns:
            str: The generated reply.
        """
        if self.pipeline:
            reply = self.pipeline.run(state)
        else:
            reply = f"{self.name}: I'm active and ready to respond, but I don't have a pipeline."

        self.status = 'available'
        return reply

    def get_status(self):
        """
        Gets the status of the agent.

        Returns:
            str: The status of the agent.
        """
        return self.status

    @staticmethod
    def from_json(json_data):
        """
        Creates an Agent instance from JSON data.

        Note: This method does not currently support initializing tools from JSON.
        Tools should be added programmatically after creating the agent.

        Args:
            json_data (dict): The JSON data representing the agent.

        Returns:
            Agent: The created Agent instance.

        Raises:
            ValueError: If the JSON data is missing required keys.
        """
        required_keys = ['agent_id', 'name', 'role']
        if not all(key in json_data for key in required_keys):
            raise ValueError("JSON must contain the keys 'agent_id', 'name' and 'role'.")

        agent_id = json_data['agent_id']
        name = json_data['name']
        role = json_data['role']

        return Agent(agent_id, name, role)