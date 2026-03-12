import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from miniautogen.adapters.llm import LiteLLMProvider, OpenAIProvider


# Interface for the LLM client
class LLMClientInterface(ABC):
    @abstractmethod
    async def get_model_response(
        self,
        prompt: List[Dict[str, str]],
        model_name: Optional[str] = None,
        temperature: float = 1.0,
    ) -> Optional[str]:
        """
        Retrieves a model response based on the given prompt asynchronously.

        Args:
            prompt (List[Dict[str, str]]): The input prompt for the model (list of messages).
            model_name (str, optional): The name of the model to use.
            temperature (float, optional): The temperature parameter for model generation.

        Returns:
            str: The generated model response.
        """
        raise NotImplementedError

# Concrete implementation for the OpenAI client
class OpenAIClient(OpenAIProvider, LLMClientInterface):
    def __init__(self, api_key: str | None = None, client: object | None = None):
        """
        Initializes the OpenAI client.

        Args:
            api_key (str): The API key for accessing the OpenAI service.
        """
        self.logger = logging.getLogger(__name__)
        super().__init__(api_key=api_key, client=client)

    async def get_model_response(
        self,
        prompt: List[Dict[str, str]],
        model_name: str = "gpt-3.5-turbo",
        temperature: float = 1.0,
    ) -> str:
        """
        Retrieves a model response using the OpenAI API asynchronously.
        """
        return await self.generate_response(prompt, model_name, temperature)

class LiteLLMClient(LiteLLMProvider, LLMClientInterface):
    def __init__(self, default_model: str, client: object | None = None):
        """
        Initializes the LiteLLM client.

        Args:
            default_model (str): The default LiteLLM model to use if none is provided in the call.
        """
        self.logger = logging.getLogger(__name__)
        super().__init__(default_model=default_model, client=client)

    async def get_model_response(
        self,
        prompt: List[Dict[str, str]],
        model_name: Optional[str] = None,
        temperature: float = 1.0,
    ) -> str:
        """
        Retrieves a model response using the LiteLLM API asynchronously.
        """
        return await self.generate_response(prompt, model_name, temperature)
