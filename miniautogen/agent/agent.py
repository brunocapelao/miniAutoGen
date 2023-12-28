class Agent:
    """
    Classe que representa um agente autônomo.

    Atributos:
        agent_id (str): Identificador único do agente.
        name (str): Nome representativo do agente.
        role (str): Função ou especialização do agente.
        pipeline (Pipeline): Pipeline de processamento associado ao agente.
        status (str): Estado atual do agente (ativo, inativo, processando).

    Métodos:
        generate_reply(state): Gera uma resposta com base no estado atual.
        get_status(): Retorna o status atual do agente.
    """

    def __init__(self, agent_id, name, role, pipeline=None):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.pipeline = pipeline
        self.status = "ativo"  # Pode ser 'ativo', 'inativo' ou 'processando'

    def generate_reply(self, state):
        """
        Gera uma resposta com base no estado atual do pipeline.

        Args:
            state (PipelineState): O estado atual do pipeline.

        Returns:
            str: A resposta gerada pelo agente.
        """
        if self.pipeline:
            # Processa o estado através do pipeline
            reply = self.pipeline.run(state)
        else:
            reply = f"{self.name}: Estou ativo e pronto para responder, mas não possuo pipeline."

        self.status = 'ativo'
        return reply

    def get_status(self):
        """
        Retorna o status atual do agente.

        Returns:
            str: O status atual do agente.
        """
        return self.status

    @staticmethod
    def from_json(json_data):
        """
        Cria uma instância de Agent a partir de um dicionário JSON.

        Args:
            json_data (dict): Dicionário contendo dados do agente.

        Returns:
            Agent: Uma nova instância de Agent.
        """
        required_keys = ['agent_id', 'name', 'role']
        if not all(key in json_data for key in required_keys):
            raise ValueError("JSON deve conter as chaves 'agent_id', 'name' e 'role'.")

        agent_id = json_data['agent_id']
        name = json_data['name']
        role = json_data['role']

        return Agent(agent_id, name, role)
