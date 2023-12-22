from abc import ABC, abstractmethod
import os
import csv
import json
from openai import OpenAI
import logging
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configuração de Logging
logging.basicConfig(filename='chatbot.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Classe abstrata Agent
class Agent(ABC):
    def __init__(self, name, system):
        self.name = name
        self.system = system

    @abstractmethod
    def send(self, content):
        pass

# Agente automatizado que interage com a API do OpenAI
class AutomatedAgent(Agent):
    def __init__(self, name, system):
        super().__init__(name, system)
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def send(self, content, system):
        # Implementação específica para um agente automatizado
        chat_completion = self.client.chat.completions.create(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": content}],
            model="gpt-3.5-turbo-16k",
        )
        response = chat_completion.choices[0].message.content
        logger.info(f"Resposta do {self.name}: {response}")
        return response

# Agente humano
class HumanAgent(Agent):
    def __init__(self, name, system):
        super().__init__(name, system)

    def send(self, content, system=None):
        # Implementação para interação humana
        print(f"{self.name}, você recebeu uma nova mensagem:\n{content}\n")
        response = input(f"{self.name}, sua resposta: ")
        return response
    
class AgenteMestre(Agent):
    def __init__(self, name, system):
        super().__init__(name, system)

    @abstractmethod
    def mediar_conversa(self):
        pass

    @abstractmethod
    def escolher_proximo(self, participantes):
        pass

    def send(self, content):
        # Implementação de send para AgenteMestre.
        # Como AgenteMestre não envia mensagens da mesma forma que outros agentes,
        # esta implementação pode ser deixada vazia ou usada para log, por exemplo.
        logger.info(f"{self.name} (Mestre) recebeu uma mensagem, mas não responde da mesma forma que outros agentes.")
        return "Mestre não responde diretamente."


class HumanMestre(AgenteMestre):
    def __init__(self, name, system='Mestre Humano'):
        super().__init__(name, system)

    def mediar_conversa(self):
        # Implementação de mediação humana
        resposta = input("A conversa alcançou o objetivo? (True/False): ")
        return resposta.lower() == 'true'

    def escolher_proximo(self, participantes):
        # Implementação humana de escolha do próximo agente
        print("Escolha o próximo agente a participar:")
        for i, agente in enumerate(participantes):
            print(f"{i + 1}: {agente.name}")
        escolha = int(input("Digite o número correspondente ao agente: "))
        return participantes[escolha - 1]


class AutomatedMestre(AgenteMestre):
    def __init__(self, name, system):
        super().__init__(name, system)
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def send(self, content):
        # Implementação específica para envio de mensagens automatizadas pelo mestre
        chat_completion = self.client.chat.completions.create(
            messages=[{"role": "system", "content": self.system},
                      {"role": "user", "content": content}],
            model="gpt-3.5-turbo-16k",
        )
        response = chat_completion.choices[0].message.content
        logger.info(f"Resposta do {self.name}: {response}")
        return response

    def mediar_conversa(self):
        # Implementação automatizada para decidir se a conversa atingiu o objetivo
        # Aqui, você pode definir um prompt específico para avaliar se o objetivo foi atingido
        prompt = "Avaliar se a conversa atingiu o objetivo."
        resposta = self.send(prompt)
        return resposta.lower() == 'true'

    def escolher_proximo(self, participantes):
        # Implementação automatizada para escolher o próximo agente
        # Aqui, você pode definir um prompt específico para escolher o próximo agente
        prompt = "Escolher o próximo agente a participar."
        nome_proximo_agente = self.send(prompt)
        proximo_agente = next((agente for agente in participantes if agente.name == nome_proximo_agente), None)
        return proximo_agente
