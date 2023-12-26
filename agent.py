class Agent:
    """
    Classe que representa um agente autônomo no GroupChat.

    Atributos:
        agent_id (str): Identificador único do agente.
        name (str): Nome representativo do agente.
        role (str): Função ou especialização do agente.
        status (str): Estado atual do agente (ativo, inativo, processando).
        pipeline (Pipeline): Estrutura para processar mensagens.
        context (dict): Informações contextuais do agente.

    Métodos:
        send_message(group_chat, message): Envia uma mensagem para o GroupChat.
        receive_message(message): Recebe e processa uma mensagem do GroupChat.
        run_pipeline(data): Executa o pipeline de processamento com dados fornecidos.
        update_context(new_context): Atualiza o contexto do agente.
        get_status(): Retorna o status atual do agente.
    """

    def __init__(self, agent_id, name, role, pipeline):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.status = "ativo"  # Pode ser 'ativo', 'inativo' ou 'processando'
        self.pipeline = pipeline
        self.context = {}

    def generate_reply(self, **kwargs):
        self.status = 'processando'
        reply = self.run_pipeline(**kwargs)
        return reply

    def run_pipeline(self, **kwargs):
        return self.pipeline.run(**kwargs)

    def update_context(self, new_context):
        self.context.update(new_context)

    def get_status(self):
        return self.status
