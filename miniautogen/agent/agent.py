from typing import Optional, Dict, Any
from miniautogen.pipeline.pipeline import Pipeline, ChatPipelineState

class Agent:
    """
    Represents an agent in the system.

    Attributes:
        agent_id (str): The ID of the agent.
        name (str): The name of the agent.
        role (str): The role of the agent.
        pipeline (Pipeline, optional): The pipeline used to process the state. Defaults to None.
        status (str): The status of the agent. Defaults to "available".
    """

    def __init__(self, agent_id: str, name: str, role: str, pipeline: Optional[Pipeline] = None):
        """
        Initializes a new instance of the Agent class.
        """
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.pipeline = pipeline
        self.status = "available"

    async def generate_reply(self, state: ChatPipelineState) -> str:
        """
        Generates a reply based on the given state asynchronously.

        Args:
            state (ChatPipelineState): The state to process.

        Returns:
            str: The generated reply.
        """
        if self.pipeline:
            # Run the pipeline asynchronously
            final_state = await self.pipeline.run(state)

            # Assuming the pipeline puts the 'reply' in the state or returns it.
            # Based on previous code, the pipeline modifies the state.
            # We need to extract the reply. This logic depends on component implementation.
            # For now, let's assume 'reply' key in state data or just return a placeholder
            # if the pipeline design is purely side-effect based (which is risky).
            # Looking at previous examples, components modified state.

            # Let's standardize: The pipeline should populate a 'response' or similar field in state,
            # OR the last component return value is used.
            # To preserve flexibility:
            return final_state.get_state().get('reply', f"{self.name}: I processed the pipeline but found no 'reply' in state.")
        else:
            return f"{self.name}: I'm active and ready to respond, but I don't have a pipeline."

    def get_status(self) -> str:
        return self.status

    @staticmethod
    def from_json(json_data: Dict[str, Any]) -> 'Agent':
        required_keys = ['agent_id', 'name', 'role']
        if not all(key in json_data for key in required_keys):
            raise ValueError("JSON must contain the keys 'agent_id', 'name' and 'role'.")
        return Agent(json_data['agent_id'], json_data['name'], json_data['role'])
