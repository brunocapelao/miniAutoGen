from abc import ABC, abstractmethod
from miniautogen.pipeline.components.pipelinecomponent import PipelineComponent

class Pipeline:
    """
    Class that represents a data processing pipeline.

    Attributes:
        components (list of PipelineComponent): List of pipeline components.
    """

    def __init__(self, components=None):
        """
        Initializes the pipeline with a list of components.

        Args:
            components (list of PipelineComponent): List of pipeline components.
        """
        self.components = components if components is not None else []

    def add_component(self, component):
        """
        Adds a component to the pipeline.

        Args:
            component (PipelineComponent): Component to be added to the pipeline.
        """
        if not issubclass(type(component), PipelineComponent):
            raise TypeError("Component must be a subclass of PipelineComponent")
        self.components.append(component)

    def run(self, state):
        """
        Executes the pipeline on the provided state, passing the state of each component to the next.

        Args:
            state (ChatPipelineState): State of the chat to be processed.

        Returns:
            ChatPipelineState: State of the chat after processing all components.
        """
        for component in self.components:
            state = component.process(state)
        return state


class PipelineState(ABC):
    """
    Abstract class to manage the state during pipeline execution.
    """

    @abstractmethod
    def get_state(self):
        """
        Retrieves the current state.
        """
        pass

    @abstractmethod
    def update_state(self, **kwargs):
        """
        Updates the state with new data.

        Args:
            **kwargs: Keyword arguments containing the data to update the state.
        """
        pass

class ChatPipelineState(PipelineState):
    """
    Dynamic implementation of PipelineState for chat.
    """

    def __init__(self, **kwargs):
        self.state_data = kwargs

    def get_state(self):
        return self.state_data

    def update_state(self, **kwargs):
        self.state_data.update(kwargs)
