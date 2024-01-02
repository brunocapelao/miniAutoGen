from openai import OpenAI
import openai
import os
import logging
from dotenv import load_dotenv
from .pipeline import PipelineComponent
import time
from jinja2 import Environment, select_autoescape
import json

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
        last_message = group_chat.get_messages(
            type='json')[-1] if group_chat.get_messages(type='json') else None
        if last_message:
            last_sender_id = last_message['sender_id']
            # Encontra o índice do último agente que enviou uma mensagem
            last_agent_index = next((i for i, agent in enumerate(
                group_chat.agentList) if agent.agent_id == last_sender_id), -1)
            # Seleciona o próximo agente na lista
            next_agent_index = (last_agent_index +
                                1) % len(group_chat.agentList)
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
            raise ValueError(
                "Agent e GroupChat são necessários para AgentReplyComponent.")
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
            raise ValueError(
                "Assistant ID não definido para OpenAIThreadComponent.")

        if not self.thread:
            self.thread = self._create_thread()

        try:
            # Obter informações necessárias do estado
            chat = state.get_state().get('group_chat')
            agent = state.get_state().get('selected_agent')

            if not chat or not agent:
                raise ValueError(
                    "group_chat e selected_agent são necessários para OpenAIThreadComponent.")

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
        messages = self.client.beta.threads.messages.list(
            thread_id=thread.id, order="asc")
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


class Jinja2TemplatesComponent(PipelineComponent):
    def __init__(self):
        self.templates = []
        self.variables = {}
        self.env = Environment(autoescape=select_autoescape())

    def add_template(self, template_str, role):
        """
        Adiciona um template à lista com seu respectivo papel.

        Args:
            template_str (str): String contendo o template Jinja2.
            role (str): Papel do template ('system', 'user', 'assistant').
        """
        self.templates.append({'template': template_str, 'role': role})

    def set_variables(self, variables):
        self.variables = variables

    def _generate_combined_result(self):
        """
        Gera o resultado combinado dos templates renderizados.

        Returns:
            str: String JSON combinada.
        """
        combined_result = []
        for item in self.templates:
            template_str = item['template']
            role = item['role']
            template = self.env.from_string(template_str)
            rendered_content = template.render(self.variables)
            # Aqui, garantimos que cada item é um dicionário válido para JSON
            combined_result.append({"role": role, "content": rendered_content})

        # Convertendo a lista de dicionários em uma string JSON
        return json.dumps(combined_result)

    def process(self, state):
        chat = state.get_state().get('group_chat')
        agent = state.get_state().get('selected_agent')
        messages = json.loads(chat.get_messages()[
                              ['sender_id', 'message']].to_json(orient='records'))

        # Verifica se as variáveis foram definidas
        if self.variables is None:
            self.variables = state.get_state().get('variables', {})

        self.variables['chat'] = chat
        self.variables['agent'] = agent
        self.variables['messages'] = messages
        combined_json_str = self._generate_combined_result()
        # Converte a string JSON em um objeto Python para atualizar o estado
        combined_json = json.loads(combined_json_str)
        print(combined_json)
        state.update_state(prompt=combined_json)

        return state


class NextAgentMessageComponent(PipelineComponent):
    def __init__(self):
        self.alternative_next = NextAgentSelectorComponent()

    def set_alternative_next(self, alternative_next):
        """
        Configura o próximo componente a ser executado caso não seja encontrado um agente
        na última mensagem.

        Args:
            alternative_next (PipelineComponent): Próximo componente a ser executado.
        """
        self.alternative_next = alternative_next

    def process(self, state):
        """
        Processa a seleção do próximo agente com base na última mensagem do chat.

        Args:
            state (PipelineState): Estado atual do pipeline.

        Returns:
            PipelineState: Estado atualizado do pipeline.
        """
        chat = state.get_state().get('group_chat')
        agents = chat.agentList

        # Obtém a última mensagem do chat
        messages = chat.get_messages()
        last_message = messages.iloc[-1].message if not messages.empty else None

        next_agent = None
        if last_message:
            # Procura pelo agent_id de cada agente na última mensagem
            for agent in agents:
                if agent.agent_id in last_message:
                    next_agent = agent
                    break

        # Atualiza o estado com o próximo agente selecionado, se encontrado
        if next_agent:
            state.update_state(selected_agent=next_agent)
        else:
            print("Nenhum agente correspondente encontrado na última mensagem.")
            self.alternative_next.process(state)

        return state


class UpdateNextAgentComponent(PipelineComponent):
    def __init__(self):
        """
        Inicializa o componente com a lista de agentes disponíveis.

        Args:
            agents (list): Lista de agentes disponíveis no sistema.
        """
        self.next_agent_id = None

    def set_next_agent_id(self, next_agent_id):
        """
        Configura o ID do próximo agente a ser definido no estado.

        Args:
            next_agent_id (str): ID do próximo agente.
        """
        self.next_agent_id = next_agent_id

    def process(self, state):
        """
        Atualiza o estado para indicar o próximo agente com base no agent_id fornecido.

        Args:
            state (PipelineState): Estado atual do pipeline.
            agent_id (str): ID do agente a ser definido como o próximo.

        Returns:
            PipelineState: Estado atualizado do pipeline.
        """
        chat = state.get_state().get('group_chat')
        agents = chat.agentList

        for agent in agents:
            if agent.agent_id in self.next_agent_id:
                next_agent = agent
                break

        if next_agent:
            state.update_state(selected_agent=next_agent)
            print(f"Próximo agente atualizado para: {self.next_agent_id}")
        else:
            raise ValueError(
                f"Agent ID '{self.next_agent_id}' não encontrado entre os agentes disponíveis.")

        return state


class Jinja2SingleTemplateComponent(PipelineComponent):
    def __init__(self):
        """
        Inicializa o componente sem um template ou variáveis.
        """
        self.template_str = None
        self.variables = None
        self.env = Environment(autoescape=select_autoescape())

    def set_template_str(self, template_str):
        """
        Configura a string do template para o componente.

        Args:
            template_str (str): String contendo o template Jinja2.
        """
        self.template_str = template_str

    def set_variables(self, variables):
        """
        Configura as variáveis para o componente.

        Args:
            variables (dict): Dicionário de variáveis para o template.
        """
        self.variables = variables

    def process(self, state):
        """
        Processa o estado atual do pipeline, substituindo as variáveis no template.

        Args:
            state (PipelineState): Estado atual do pipeline contendo as variáveis.

        Returns:
            PipelineState: Estado atualizado do pipeline.
        """
        template = self.env.from_string(self.template_str)
        chat = state.get_state().get('group_chat')
        agent = state.get_state().get('selected_agent')
        messages = json.loads(chat.get_messages()[
                              ['sender_id', 'message']].to_json(orient='records'))

        # Verifica se as variáveis foram definidas
        if self.variables is None:
            self.variables = state.get_state().get('variables', {})

        self.variables['chat'] = chat
        self.variables['agent'] = agent
        self.variables['messages'] = messages
        # Renderiza o template com as variáveis fornecidas
        prompt = template.render(self.variables)
        prompt = json.loads(prompt)
        print(prompt)

        # Atualiza o estado do pipeline com a saída renderizada
        state.update_state(prompt=prompt)

        return state


class LLMResponseComponent(PipelineComponent):
    def __init__(self, llm_client, model_name="gpt-4"):
        self.llm_client = llm_client
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)

    def process(self, state):
        prompt = state.get_state().get('prompt')
        if not prompt:
            self.logger.error("Prompt ausente no estado do pipeline.")
            return state

        response = self.llm_client.get_model_response(prompt, self.model_name)
        if response:
            return response
        else:
            self.logger.error("Falha ao obter resposta do LLM.")
            state.update_state({'error': "Falha ao obter resposta do LLM."})
            return state