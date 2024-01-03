from abc import ABC, abstractmethod

class PipelineComponent(ABC):
    """
    Abstract base class for individual pipeline components.
    """

    @abstractmethod
    def process(self, state):
        """
        Processes the data and returns the result.

        Args:
            state (PipelineState): Instance of the pipeline state to be accessed or modified.
        """
        pass