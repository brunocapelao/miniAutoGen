from abc import ABC, abstractmethod

class Pipeline:
    """
    Classe que representa um pipeline de processamento de dados.
    """

    def __init__(self, components=None):
        """
        Inicializa o pipeline com uma lista de componentes.

        Args:
            components (list of PipelineComponent): Lista de componentes do pipeline.
        """
        self.components = components if components is not None else []

    def add_component(self, component):
        """
        Adiciona um componente ao pipeline.

        Args:
            component (PipelineComponent): Componente a ser adicionado ao pipeline.
        """
        if not issubclass(type(component), PipelineComponent):
            raise TypeError("Component must be a subclass of PipelineComponent")
        self.components.append(component)

    def run(self, state):
        """
        Executa o pipeline no estado fornecido, passando o estado de cada componente para o próximo.

        Args:
            state (ChatPipelineState): Estado do chat a ser processado.

        Returns:
            ChatPipelineState: Estado do chat após o processamento de todos os componentes.
        """
        for component in self.components:
            state = component.process(state)
        return state

class PipelineComponent(ABC):
    """
    Classe base abstrata para componentes individuais do pipeline.
    """

    @abstractmethod
    def process(self, state):
        """
        Processa os dados e retorna o resultado.

        Args:
            state (PipelineState): Instância do estado do pipeline para ser acessado ou modificado.
        """
        pass

class PipelineState(ABC):
    """
    Classe abstrata para gerenciar o estado durante a execução do pipeline.
    """

    @abstractmethod
    def get_state(self):
        """
        Recupera o estado atual.
        """
        pass

    @abstractmethod
    def update_state(self, **kwargs):
        """
        Atualiza o estado com novos dados.

        Args:
            **kwargs: Argumentos de palavra-chave contendo os dados para atualizar o estado.
        """
        pass

class ChatPipelineState(PipelineState):
    """
    Implementação dinâmica de PipelineState para o chat.
    """

    def __init__(self, **kwargs):
        self.state_data = kwargs

    def get_state(self):
        return self.state_data

    def update_state(self, **kwargs):
        self.state_data.update(kwargs)




# # Inicializando o estado do pipeline
# state = ChatPipelineState(group_chat=group_chat, chat_admin=chat_admin)

# # Criando componentes com argumentos customizados
# user_response_component = UserResponseComponent(novo_argumento="valor_do_argumento")

# # Criando e executando o pipeline
# pipeline = Pipeline([user_response_component])
# pipeline.run(state)
