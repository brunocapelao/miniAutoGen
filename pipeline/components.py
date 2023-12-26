from openai import OpenAI
from dotenv import load_dotenv
from pipeline.pipeline import PipelineComponent
import os

load_dotenv()


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
        print(data.tail())
        resposta = input("Digite a resposta: ")
        return resposta


class UserInputNextAgent(PipelineComponent):
    """
    Componente de Pipeline para seleção do próximo agente pelo usuário.

    Este componente exibe a lista de agentes disponíveis no groupchat e permite ao usuário
    selecionar o próximo agente com o qual deseja interagir.

    Métodos:
        process(**kwargs): Usa o estado atual do groupchat para apresentar a lista de agentes
        e capturar a escolha do usuário.
    """

    def process(self, **kwargs):
        groupchat = kwargs.get('groupchat')
        groupchatadmin = kwargs.get('groupchatadmin')
        print(groupchatadmin)
        if not groupchat:
            raise ValueError("groupchat is required for UserInputNextAgent")
        if not groupchatadmin:
            raise ValueError("groupchat is required for UserInputNextAgent")

        agents = groupchat.agentList
        for i, agent in enumerate(agents):
            print(f"{i + 1}: {agent.name}")

        escolha = None
        while escolha is None:
            try:
                escolha_input = input(
                    "Digite o número correspondente ao agente: ")
                escolha = int(escolha_input)
                if escolha < 1 or escolha > len(agents):
                    print("Escolha inválida. Tente novamente.")
                    escolha = None
            except ValueError:
                print("Entrada inválida. Por favor, digite um número.")

        next_agent = agents[escolha - 1]
        kwargs['agent'] = next_agent
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
    Componente de Pipeline que utiliza um LLM (Modelo de Linguagem de Aprendizado Profundo)
    para gerar uma resposta baseada nas mensagens anteriores do chat.

    Este componente interage com a API de um LLM para obter respostas inteligentes e contextuais,
    que são então retornadas para o chat em grupo.

    Atributos:
        api_key (str): Chave de API necessária para autenticar as solicitações ao LLM.
        model_name (str): Nome do modelo LLM que será utilizado para gerar as respostas.

    Métodos:
        process(**kwargs): Recebe o estado atual do chat em grupo e utiliza o LLM para gerar uma resposta.
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


    def process(self, **kwargs):
        group_chat = kwargs.get('groupchat')
        agent = kwargs.get('agent')
        # Supondo que estas variáveis sejam fornecidas ou definidas anteriormente
        participantes_str = group_chat.agentList
        goal = kwargs.get('goal', 'Indefinido')
        contexto = kwargs.get('contexto', 'Indefinido')
        conversa_ativa = '\n'.join([f"{row['sender_id']}: {row['message']}" for index, row in group_chat.get_messages().iterrows()])

        system = f"""
            ### Objetivo Principal e Contexto:
            Você é {agent.name}, um Agente GPT Customizado projetado para colaborar na resolução de problemas em um ambiente de conversação com outros agentes especializados. Sua função principal é analisar, compreender e contribuir para a discussão, utilizando seu conhecimento específico para auxiliar na solução de questões complexas. Você deve interagir de forma eficaz com os outros agentes, respeitando seus perfis e áreas de especialização.

            ### Perfil e Especialização:
            Nome: {agent.name}
            Área de Especialização: {agent.role}

            ### Instruções de Engajamento:
            - **Colaboração Ativa**: Engaje-se ativamente com os outros agentes, oferecendo suas perspectivas e conhecimentos especializados para enriquecer a discussão.
            - **Respostas Contextualizadas**: Responda de forma contextualizada, considerando as contribuições anteriores dos agentes e o fluxo atual da conversa.
            - **Construção Conjunta de Soluções**: Colabore na construção de soluções, aproveitando os pontos fortes de cada agente para abordar o problema de maneira integrada.

            ### Formato de Respostas:
            - **Clareza e Concisão**: Suas respostas devem ser claras, concisas e focadas na tarefa em questão. Evite informações desnecessárias que não contribuam para a resolução do problema.
            - **Adaptação de Estilo de Comunicação**: Adapte seu estilo de comunicação conforme necessário, variando entre explicações técnicas e simplificadas, com base na natureza da conversa e nos agentes envolvidos.
            - **Coerência com a Especialização**: Mantenha a coerência com sua área de especialização, garantindo que suas contribuições sejam relevantes e fundamentadas.

            ### Considerações Finais:
            Lembre-se de que o objetivo é trabalhar em conjunto com os outros agentes para alcançar uma solução eficaz e bem fundamentada para o problema apresentado.
                
            SUA RESPOSTA DEVE SER APENAS UMA MENSAGEM QUE FAÇA SENTIDO NO CONTEXTO DA CONVERSA ATUAL. NÃO É NECESSÁRIO RESPONDER A TODAS AS MENSAGENS ANTERIORES. VOCÊ PODE IGNORAR AS MENSAGENS QUE NÃO SÃO RELEVANTES PARA A SUA RESPOSTA. NÃO ENVIE MENSAGEM COMO SE FOSSE UM OUTRO AGENTE.    
            """

        content = (
            f"Seu Nome: {agent.name}\n"
            f"Outros Participantes: {participantes_str}\n"
            f"Objetivo conversa: {goal}\n"
            f"Contexto Atual: {contexto}\n"
            f"Histórico da Conversa: {conversa_ativa}\n"
        )

        # Inicializa a lista prompt com o elemento de sistema
        prompt_list = [{"role": "system", "content": system + content}]

        # Configura a chamada para o LLM
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=prompt_list,
            temperature=1
        )

        # Extrai e retorna a resposta gerada pelo LLM
        reply = response.choices[0].message.content
        return reply
