from abc import ABC, abstractmethod
from typing import Any

class PipelineComponent(ABC):
    """
    Abstract base class for individual pipeline components.
    """

    @abstractmethod
    async def process(self, state: Any) -> Any:
        """
        Processes the data and returns the result asynchronously.

        Args:
            state (PipelineState): Instance of the pipeline state to be accessed or modified.
        """
        pass
