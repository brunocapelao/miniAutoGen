import openai
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from litellm import acompletion

# Interface for the LLM client
class LLMClientInterface(ABC):
    @abstractmethod
    async def get_model_response(self, prompt: List[Dict[str, str]], model_name: Optional[str] = None, temperature: float = 1.0) -> Optional[str]:
        """
        Retrieves a model response based on the given prompt asynchronously.

        Args:
            prompt (List[Dict[str, str]]): The input prompt for the model (list of messages).
            model_name (str, optional): The name of the model to use.
            temperature (float, optional): The temperature parameter for model generation.

        Returns:
            str: The generated model response.
        """
        pass

# Concrete implementation for the OpenAI client
class OpenAIClient(LLMClientInterface):
    def __init__(self, api_key: str):
        """
        Initializes the OpenAI client.

        Args:
            api_key (str): The API key for accessing the OpenAI service.
        """
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    async def get_model_response(self, prompt: List[Dict[str, str]], model_name: str = "gpt-3.5-turbo", temperature: float = 1.0) -> str:
        """
        Retrieves a model response using the OpenAI API asynchronously.
        """
        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=prompt,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Error calling the OpenAI API: {e}")
            raise  # Fail fast, let the caller handle the error

class LiteLLMClient(LLMClientInterface):
    def __init__(self, default_model: str):
        """
        Initializes the LiteLLM client.

        Args:
            default_model (str): The default LiteLLM model to use if none is provided in the call.
        """
        self.logger = logging.getLogger(__name__)
        self.default_model = default_model

    async def get_model_response(self, prompt: List[Dict[str, str]], model_name: Optional[str] = None, temperature: float = 1.0) -> str:
        """
        Retrieves a model response using the LiteLLM API asynchronously.
        """
        model = model_name if model_name else self.default_model
        try:
            response = await acompletion(model=model, messages=prompt, temperature=temperature)
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Error calling the LiteLLM API: {e}")
            raise
