class PipelineComponent:
    """
    Classe base para componentes individuais do pipeline.
    """
    def process(self, data):
        """
        Processa os dados e retorna o resultado.

        Args:
            data (any): Dados de entrada para serem processados.

        Returns:
            any: Resultado do processamento, que será usado como entrada para o próximo componente.
        """
        raise NotImplementedError("Cada componente deve implementar seu próprio método de processamento.")

class Pipeline:
    """
    Classe que representa um pipeline de processamento de dados.

    Attributes:
        components (list): Lista de componentes do pipeline.
    """
    def __init__(self, components=[]):
        """
        Inicializa o pipeline com uma lista de componentes.

        Args:
            components (list, optional): Lista de componentes do pipeline. Defaults to [].
        """
        self.components = components

    def add_component(self, component):
        """
        Adiciona um componente ao pipeline.

        Args:
            component (PipelineComponent): Componente a ser adicionado ao pipeline.
        """
        self.components.append(component)

    def run(self, **kwargs):
        """
        Executa o pipeline nos dados fornecidos, passando o resultado de cada componente para o próximo.

        Args:
            **kwargs: Dicionário de argumentos de palavras-chave. 'data' deve ser uma das chaves.

        Returns:
            dict: kwargs atualizado após o processamento de todos os componentes.
        """
        for component in self.components:
            kwargs = component.process(**kwargs)
        return kwargs

# # Exemplo de componentes específicos do pipeline
# # Componentes do Pipeline
# class DataPreprocessing(PipelineComponent):
#     def process(self, data):
#         print("Pré-processamento dos dados:", data)
#         return data.upper()  # Exemplo de pré-processamento

# class DataAnalysis(PipelineComponent):
#     def process(self, data):
#         print("Analisando dados:", data)
#         return f"Análise concluída para {data}"

# class DecisionMaking(PipelineComponent):
#     def process(self, data):
#         print("Tomando decisão baseada nos dados:", data)
#         return f"Decisão tomada com base em {data}"

# # Criando um pipeline
# pipeline = Pipeline()
# pipeline.add_component(DataPreprocessing())
# pipeline.add_component(DataAnalysis())
# pipeline.add_component(DecisionMaking())

# # Dados de entrada
# input_data = "Dados de Exemplo"

# # Executando o pipeline
# result = pipeline.run(input_data)
# print("Resultado do Pipeline:", result)