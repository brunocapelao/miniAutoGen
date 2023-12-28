from openai import OpenAI
import openai
import os
import logging
from dotenv import load_dotenv
from .pipeline import PipelineComponent
import time

load_dotenv()

# Configuração do Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Exceção personalizada para saída do usuário
class UserExitException(Exception):
    pass

class UserResponseComponent(PipelineComponent):
    def process(self, state):
        """
        Processa a entrada do usuário, atualizando o estado com a resposta do usuário.

        Args:
            state (PipelineState): Estado atual do pipeline.

        Returns:
            PipelineState: Estado atualizado do pipeline.
        """
        try:
            reply = input("Digite a resposta: ")
            state.update_state(reply=reply)
        except Exception as e:
            print(f"Erro ao capturar resposta do usuário: {e}")

        return reply


class UserInputNextAgent(PipelineComponent):
    def process(self, state):
        group_chat = state.get_state().get('group_chat')
        if not group_chat or not group_chat.agentList:
            raise ValueError("GroupChat inválido ou sem agentes.")

        for i, agent in enumerate(group_chat.agentList):
            print(f"{i + 1}: {agent.name}")

        next_agent = input(
            "Digite o número correspondente ao agente (ou 'sair' para cancelar): ")

        if next_agent.lower() == 'exit':
            raise UserExitException("Usuário optou por sair")

        try:
            next_agent_index = int(next_agent) - 1
            if 0 <= next_agent_index < len(group_chat.agentList):
                next_agent = group_chat.agentList[next_agent_index]
                state.update_state(selected_agent=next_agent)
            else:
                print("Escolha inválida.")
        except ValueError:
            print("Entrada inválida. Por favor, digite um número.")

        return state

class NextAgentSelectorComponent(PipelineComponent):
    def process(self, state):
        """
        Processa o estado atual para selecionar o próximo agente.

        Args:
            state (PipelineState): Estado atual do pipeline.

        Returns:
            PipelineState: Estado atualizado do pipeline.
        """
        # Acessa o estado atual para obter informações necessárias
        group_chat = state.get_state().get('group_chat')
        if not group_chat or not hasattr(group_chat, 'agentList'):
            raise ValueError("GroupChat inválido ou sem agentes.")

        # Implementação do processo de seleção do próximo agente
        try:
            # Exemplo: Selecionar o próximo agente com base na lógica específica
            # Aqui você pode adicionar sua lógica de seleção de agentes
            next_agent = self.select_next_agent(group_chat)
            state.update_state(selected_agent=next_agent)
        except Exception as e:
            print(f"Erro ao selecionar o próximo agente: {e}")

        return state

    def select_next_agent(self, group_chat):
        """
        Implementa a lógica específica para selecionar o próximo agente.

        Args:
            group_chat (GroupChat): Objeto GroupChat contendo a lista de agentes.

        Returns:
            Agent: O agente selecionado.
        """
        # Exemplo de lógica de seleção
        # Esta função deve ser personalizada conforme as suas necessidades
        last_message = group_chat.get_messages(type='json')[-1] if group_chat.get_messages(type='json') else None
        if last_message:
            last_sender_id = last_message['sender_id']
            # Encontra o índice do último agente que enviou uma mensagem
            last_agent_index = next((i for i, agent in enumerate(group_chat.agentList) if agent.agent_id == last_sender_id), -1)
            # Seleciona o próximo agente na lista
            next_agent_index = (last_agent_index + 1) % len(group_chat.agentList)
        else:
            # Se não houver mensagens, começa com o primeiro agente
            next_agent_index = 0

        return group_chat.agentList[next_agent_index]


class AgentReplyComponent(PipelineComponent):
    def process(self, state):
        """
        Processa a resposta do agente atual e adiciona essa resposta ao chat em grupo.

        Args:
            state (PipelineState): Estado atual do pipeline.

        Returns:
            PipelineState: Estado atualizado do pipeline.
        """
        # Acessa o estado atual para obter informações necessárias
        agent = state.get_state().get('selected_agent')
        group_chat = state.get_state().get('group_chat')
        if not agent or not group_chat:
            raise ValueError("Agent e GroupChat são necessários para AgentReplyComponent.")
        # Implementação da geração da resposta do agente
        try:
            reply = agent.generate_reply(state)
            print(reply)
            group_chat.add_message(sender_id=agent.agent_id, message=reply)
        except Exception as e:
            print(f"Erro ao processar a resposta do agente: {e}")

        return state


class TerminateChatComponent(PipelineComponent):
    """
    Componente de Pipeline que verifica se a palavra 'TERMINATE' está presente
    na última mensagem e, em caso afirmativo, encerra o chat.
    """

    def process(self, state):
        chat_admin = state.get_state().get('chat_admin')
        chat = state.get_state().get('group_chat')
        if not chat:
            raise ValueError(
                "Chat é necessário para TerminateChatComponent.")
        messages = chat.get_messages()
        last_message = messages.iloc[-1].message if not messages.empty else None

        if last_message and "TERMINATE" in last_message.upper():
            print("Encerrando chat...")
            chat_admin.stop()  # Certifique-se de que o método stop() está implementado em GroupChat
            return "TERMINATE"

        # Continue o fluxo do pipeline normalmente se TERMINATE não estiver presente.
        return state


class OpenAIChatComponent(PipelineComponent):
    """
    Componente de Pipeline para gerar respostas utilizando o modelo de linguagem da OpenAI.
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.logger = logging.getLogger(__name__)

    def process(self, state):
        try:
            chat = state.get_state().get('group_chat')
            agent = state.get_state().get('selected_agent')

            if not chat or not agent:
                raise ValueError(
                    "groupchat e agent são obrigatórios para OpenAIResponseComponent.")
            messages = chat.get_messages('json')
            prompt = self._construct_prompt(agent, messages)
            print(prompt)
            response = self._call_openai_api(prompt)
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Erro em OpenAIResponseComponent: {e}")
            raise

    def _construct_prompt(self, agent, messages):
        formatted_messages = [{'role': 'system', 'content': agent.role}]
        for item in messages:
            role = 'assistant' if item['sender_id'] == agent.agent_id else 'user'
            content = item['message']
            formatted = {'role': role, 'content': content}
            formatted_messages.append(formatted)
        return formatted_messages

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

class OpenAIThreadComponent(PipelineComponent):
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.assistant_id = None  # Inicializa sem um assistant_id
        self.thread = None
        self.logger = logging.getLogger(__name__)

    def set_assistant_id(self, assistant_id):
        """
        Configura o ID do assistente para o componente.

        Args:
            assistant_id (str): ID do assistente da OpenAI.
        """
        self.assistant_id = assistant_id
    
    def set_thread(self, thread):
        """
        Configura o ID do assistente para o componente.

        Args:
            assistant_id (str): ID do assistente da OpenAI.
        """
        self.assistant_id = thread

    def process(self, state):
        """
        Processa o estado atual para interagir com a thread do assistente da OpenAI.

        Args:
            state (PipelineState): Estado atual do pipeline.

        Returns:
            PipelineState: Estado atualizado do pipeline.
        """
        if not self.assistant_id:
            raise ValueError("Assistant ID não definido para OpenAIThreadComponent.")
        
        if not self.thread:
            self.thread = self._create_thread()

        try:
            # Obter informações necessárias do estado
            chat = state.get_state().get('group_chat')
            agent = state.get_state().get('selected_agent')

            if not chat or not agent:
                raise ValueError("group_chat e selected_agent são necessários para OpenAIThreadComponent.")

            # Construção do prompt
            prompt = self._construct_prompt(chat)
            # Submissão da mensagem
            run = self._submit_message(self.assistant_id, self.thread, prompt)
            # Espera pela resposta
            run = self._wait_on_run(run, self.thread)
            # Obtenção da resposta
            response = self._get_response(self.thread, self.assistant_id)


        except Exception as e:
            self.logger.error(f"Erro em OpenAIThreadComponent: {e}")
            raise

        return response

    def _create_thread(self):
        thread = self.client.beta.threads.create()
        return thread
    
    def _construct_prompt(self, chat):
        message = chat.get_messages('json')[-1]['message']
        return message
    
    def _submit_message(self, assistant_id, thread, message):
        self.client.beta.threads.messages.create(
            thread_id=thread.id, role="user", content=message
        )
        return self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id,
        )

    def _get_response(self, thread, assistant_id):
        messages = self.client.beta.threads.messages.list(thread_id=thread.id, order="asc")
        for message in messages:
            if message.assistant_id == assistant_id:
                return message.content[0].text.value
        return None
    

    def _wait_on_run(self, run, thread):
        while run.status == "queued" or run.status == "in_progress":
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id,
            )
            time.sleep(0.5)
        return run