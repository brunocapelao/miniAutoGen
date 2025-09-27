from abc import ABC, abstractmethod

class Tool(ABC):
    """
    Abstract base class for all tools that can be used by an agent.

    Attributes:
        name (str): The name of the tool. This should be a short, descriptive
                    string, ideally a single word.
        description (str): A detailed description of what the tool does, what
                           its arguments are, and what it returns. This is
                           critical for the LLM to decide when to use the tool.
    """

    def __init__(self, name: str, description: str):
        """
        Initializes a new instance of the Tool class.

        Args:
            name (str): The name of the tool.
            description (str): The description of the tool.
        """
        self.name = name
        self.description = description

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """
        Executes the tool with the given arguments.

        This method must be implemented by any concrete tool class.

        Args:
            **kwargs: The arguments required by the tool, which will be
                      provided by the LLM.

        Returns:
            str: A string representation of the tool's output.
        """
        pass