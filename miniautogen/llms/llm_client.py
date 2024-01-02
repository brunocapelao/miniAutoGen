import openai
import logging
from litellm import completion

# Interface para o cliente de LLM
class LLMClientInterface:
    def get_model_response(self, prompt, model_name="gpt-4", temperature=1):
        raise NotImplementedError

# Implementação concreta para o cliente OpenAI
class OpenAIClient(LLMClientInterface):
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    def get_model_response(self, prompt, model="gpt-3.5-turbo", temperature=1):
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=prompt,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Erro ao chamar a API da OpenAI: {e}")
            return None
        

class LiteLLMClient(LLMClientInterface):
    def __init__(self, model):
        self.logger = logging.getLogger(__name__)
        self.model = model

    def get_model_response(self, prompt, model="gpt-3.5-turbo"):
        try:
            response = completion(model=model, messages=prompt)
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Erro ao chamar a API da LiteLMM: {e}")
            return None