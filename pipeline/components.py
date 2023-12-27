from openai import OpenAI
from dotenv import load_dotenv
from pipeline.pipeline import PipelineComponent
import os
import logging

load_dotenv()


class UserExitException(Exception):
    pass


class UserResponseComponent(PipelineComponent):
    """
    Componente de Pipeline que captura e retorna a resposta do usuário.

    Este componente é responsável por exibir a última mensagem do chat ao usuário
    e capturar a resposta do usuário através da entrada padrão do console.

    Métodos:
        process(data): Recebe o estado atual do chat, exibe ao usuário e captura a resposta.
    """

    def process(self, **kwargs):
        data = kwargs.get('groupchat')
        data = data.get_messages()
        resposta = input("Digite a resposta: ")
        return resposta


class UserInputNextAgent(PipelineComponent):
    def process(self, **kwargs):
        groupchat = kwargs.get('groupchat')
        if not groupchat or not groupchat.agentList:
            raise ValueError("GroupChat inválido ou sem agentes.")

        for i, agent in enumerate(groupchat.agentList):
            print(f"{i + 1}: {agent.name}")

        escolha = input(
            "Digite o número correspondente ao agente (ou 'sair' para cancelar): ")

        if escolha.lower() == 'exit':
            raise UserExitException("Usuário optou por sair")

        try:
            escolha = int(escolha) - 1
            if 0 <= escolha < len(groupchat.agentList):
                kwargs['agent'] = groupchat.agentList[escolha]
            else:
                print("Escolha inválida.")
        except ValueError:
            print("Entrada inválida. Por favor, digite um número.")

        return kwargs


class NextAgentSelectorComponent(PipelineComponent):
    def process(self, **kwargs):
        groupchat = kwargs.get('groupchat')
        last_message = groupchat.get_messages(
            type='json')[-1] if groupchat.get_messages(type='json') else None

        if not groupchat or not groupchat.agentList:
            raise ValueError("GroupChat inválido ou sem agentes.")

        if last_message:
            last_sender_id = last_message['sender_id']
            # Encontrar o índice do último agente que enviou uma mensagem
            last_agent_index = next((i for i, agent in enumerate(
                groupchat.agentList) if agent.agent_id == last_sender_id), -1)
            # Selecionar o próximo agente na lista
            next_agent_index = (last_agent_index +
                                1) % len(groupchat.agentList)
        else:
            # Se não houver mensagens, comece com o primeiro agente
            next_agent_index = 0

        kwargs['agent'] = groupchat.agentList[next_agent_index]
        return kwargs


class AgentReplyComponent(PipelineComponent):
    """
    Componente de Pipeline para processar e adicionar a resposta do agente ao chat em grupo.

    Este componente obtém a resposta do agente atual e adiciona essa resposta ao chat em grupo.
    Assumindo que o agente já foi definido em 'next', e o chat em grupo em 'groupchat'.

    Métodos:
        process(**kwargs): Processa a resposta do agente com base nas mensagens do grupo de chat
        e adiciona a nova mensagem ao grupo de chat.
    """

    def process(self, **kwargs):
        agent = kwargs.get('agent')
        group_chat = kwargs.get('groupchat')
        if not agent:
            raise ValueError("Agent is required for AgentReplyComponent")
        print
        reply = agent.generate_reply(**kwargs)
        print(reply)
        group_chat.add_message(sender_id=agent.agent_id, message=reply)


class OpenAIResponseComponent(PipelineComponent):
    """
    Componente de Pipeline para gerar respostas utilizando o modelo de linguagem da OpenAI.
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.logger = logging.getLogger(__name__)

    def process(self, **kwargs):
        try:
            group_chat = kwargs.get('groupchat')
            agent = kwargs.get('agent')

            if not group_chat or not agent:
                raise ValueError(
                    "groupchat e agent são obrigatórios para OpenAIResponseComponent.")
            messages = group_chat.get_messages('json')
            prompt = self._construct_prompt(group_chat, agent)
            response = self._call_openai_api(prompt)
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Erro em OpenAIResponseComponent: {e}")
            raise

    def _construct_prompt(self, group_chat, agent):
        messages = group_chat.get_messages('json')
        formatted_messages = [{'role': 'system', 'content': agent.role}]
        for item in messages:
            role = 'assistant' if item['sender_id'] == agent.agent_id else 'user'
            content = item['message']
            formatted = {'role': role, 'content': content}
            formatted_messages.append(formatted)
        return formatted_messages  # Mova esta linha de volta para fora do loop 'for'

    def _call_openai_api(self, prompt):
        """ Realiza a chamada à API da OpenAI. """
        try:
            return self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=prompt,
                temperature=1
            )
        except Exception as e:
            self.logger.error(f"Erro ao chamar a API da OpenAI: {e}")
            raise


# class OpenAIResponseComponent(PipelineComponent):
#     """
#     Componente de Pipeline para gerar respostas utilizando o modelo de linguagem da OpenAI.
#     """

#     def __init__(self):
#         self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
#         self.logger = logging.getLogger(__name__)

#     def process(self, **kwargs):
#         try:
#             group_chat = kwargs.get('groupchat')
#             agent = kwargs.get('agent')

#             if not group_chat or not agent:
#                 raise ValueError("groupchat e agent são obrigatórios para OpenAIResponseComponent.")

#             prompt = self._construct_prompt(group_chat, agent)
#             response = self._call_openai_api(prompt)
#             return response.choices[0].message.content
#         except Exception as e:
#             self.logger.error(f"Erro em OpenAIResponseComponent: {e}")
#             raise

#     def _construct_prompt(self, group_chat, agent):
#         """ Constrói o prompt para a API da OpenAI. """
#         # Construa o prompt com base em group_chat e agent
#         # Por exemplo:
#         prompt = "Seu prompt aqui..."
#         return prompt

#     def _call_openai_api(self, prompt):
#         """ Realiza a chamada à API da OpenAI. """
#         try:
#             return self.client.chat.completions.create(
#                 model="gpt-3.5-turbo-16k",
#                 messages=prompt,
#                 temperature=1
#             )
#         except Exception as e:
#             self.logger.error(f"Erro ao chamar a API da OpenAI: {e}")
#             raise
