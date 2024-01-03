class Agent:
    """
    Represents an agent in the system.

    Attributes:
        agent_id (int): The ID of the agent.
        name (str): The name of the agent.
        role (str): The role of the agent.
        pipeline (Pipeline, optional): The pipeline used to process the state. Defaults to None.
        status (str): The status of the agent. Defaults to "available".
    """

    def __init__(self, agent_id, name, role, pipeline=None):
        """
        Initializes a new instance of the Agent class.

        Args:
            agent_id (int): The ID of the agent.
            name (str): The name of the agent.
            role (str): The role of the agent.
            pipeline (Pipeline, optional): The pipeline used to process the state. Defaults to None.
        """
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.pipeline = pipeline
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
