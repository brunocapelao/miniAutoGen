import os
import pandas as pd
from openai import OpenAI
import json
from prompt_manager import role_play_prompt, prompt_conclusao, prompt_proximo, prompt_resumo_contexto, system_role_play
import logging
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(filename='chatbot.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
)


class Agent:
    def __init__(self, name, system):
        self.name = name
        self.model = "gpt-3.5-turbo-16k"
        self.system = system
        self.temperature = 1
        self.max_tokens = 256
        self.top_p = 1
        self.frequency_penalty = 0
        self.presence_penalty = 0

    def send(self, content, system=None):
        if not system:
            system = self.system
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system,
                },
                {
                    "role": "user",
                    "content": content,
                }
            ],
            model="gpt-4-1106-preview",
        )
        response = chat_completion.choices[0].message.content
        print(f"{self.name}: {response}")
        return response


class Mestre(Agent):
    def __init__(self, name):
        super().__init__(name, system)
        self.model = "gpt-3.5-turbo"

    def send(self, content):
        # Implementação específica para o Mestre
        response = super().send(content)
        return response


class HumanoMestre:
    def __init__(self, nome):
        self.nome = nome

    def mediar_conversa(self):
        while True:
            resposta = input("A conversa alcançou o objetivo? (True/False): ")
            if resposta in ["True", "False"]:
                if resposta == "True":
                    return True
                return False
            else:
                print("Resposta inválida. Por favor, responda com 'True' ou 'False'.")

    def escolher_proximo(self, participantes):
        print("Escolha o próximo agente a participar:")
        for i, agente in enumerate(participantes):
            print(f"{i + 1}: {agente.name}")
        while True:
            try:
                escolha = int(
                    input("Digite o número correspondente ao agente: ")) - 1
                if 0 <= escolha < len(participantes):
                    return participantes[escolha]
                else:
                    print("Número inválido. Tente novamente.")
            except ValueError:
                print("Entrada inválida. Por favor, insira um número.")


class Chat():
    def __init__(self, goal, diretorio_salvamento=None):
        self.mestre = None
        self.conversa = []
        self.conversa_ativa = []
        self.participantes = []
        self.goal = goal
        self.contexto = ""
        self.round = 0
        self.max_rounds = 9
        self.max_tokens = 1000
        self.running = True
        self.diretorio_salvamento = diretorio_salvamento
        if self.diretorio_salvamento:
            self.criar_diretorio()
            self.salvar_estado_json()

    def criar_diretorio(self):
        if not os.path.exists(self.diretorio_salvamento):
            os.makedirs(self.diretorio_salvamento)
            print(
                f"Diretório {self.diretorio_salvamento} criado para salvamento de dados.")

    def salvar_estado_json(self):
        estado = {
            'goal': self.goal,
            'participantes': [p.name for p in self.participantes],
            'mestre': self.mestre,
            'contexto': self.contexto,
            'round': self.round,
            'max_rounds': self.max_rounds,
            'max_tokens': self.max_tokens
        }
        with open(os.path.join(self.diretorio_salvamento, "estado_chat.json"), 'w') as f:
            json.dump(estado, f, indent=4)
            print(
                f"Estado do chat salvo em JSON no diretório {self.diretorio_salvamento}.")

    def atualizar_csvs(self):
        # Verificar se a persistência está habilitada
        if not self.diretorio_salvamento:
            return

        # Atualizar CSV de conversa ativa
        conversa_ativa_df = pd.DataFrame(
            self.conversa_ativa, columns=['role', 'content'])
        conversa_ativa_csv_path = os.path.join(
            self.diretorio_salvamento, "conversa_ativa.csv")
        conversa_ativa_df.to_csv(conversa_ativa_csv_path, index=False)

        # Atualizar CSV de conversa
        conversa_df = pd.DataFrame(self.conversa, columns=['role', 'content'])
        conversa_csv_path = os.path.join(
            self.diretorio_salvamento, "conversa.csv")
        conversa_df.to_csv(conversa_csv_path, index=False)

    def adicionar_participante(self, agente):
        self.participantes.append(agente)

    def adicionar_mensagem(self, role, content):
        self.conversa.append({'role': role, 'content': content})

    def send(self, agente, content, system=None):
        response = agente.send(content, system)
        self.adicionar_mensagem(agente.name, response)
        return response

    def obter_estado_conversa(self):
        return self.conversa

    def role_play(self, agente):
        # Remove o agente da lista de participantes
        participantes_sem_agente = self.participantes.copy()
        participantes_sem_agente.remove(agente)
        content = role_play_prompt(
            agente, self.goal, self.contexto, self.conversa, participantes_sem_agente)
        system = system_role_play(agente)
        self.send(agente, content, system=system)

    def mediar_conversa(self):
        prompt = prompt_conclusao(
            self.conversa_ativa, self.participantes, self.goal, self.contexto)
        result = self.mestre.send(prompt)
        if result == True:
            self.stop()

    def escolher_proximo(self):
        # Gerar o prompt para o mestre
        prompt = prompt_proximo(self.conversa_ativa,
                                self.participantes, self.goal, self.contexto)

        # Enviar o prompt para o mestre e obter a resposta
        resposta_mestre = self.mestre.send(prompt)

        # Analisar a resposta para encontrar o nome do próximo agente
        nome_proximo_agente = self.analisar_resposta_mestre(resposta_mestre)

        # Encontrar o agente correspondente na lista de participantes
        proximo_agente = next(
            (agente for agente in self.participantes if agente.name == nome_proximo_agente), None)
        return proximo_agente

    def analisar_resposta_mestre(self, resposta):
        # Implementar lógica para extrair o nome do próximo agente da resposta do mestre
        # Esta é uma implementação simplificada. Você precisará ajustar com base no formato exato da resposta do mestre.
        # Exemplo: assumindo que o primeiro elemento da resposta é o nome do agente
        return resposta.split()[0]

    def entender_contexto(self, content):
        prompt = prompt_resumo_contexto(
            self.conversa_ativa, self.participantes, self.goal, self.contexto)
        self.contexto = self.mestre.send(prompt)

    def remover_participante(self, agent):
        try:
            self.participantes.remove(agent)
            # Adicionar aqui qualquer lógica adicional necessária após a remoção
        except ValueError:
            # Lidar com o caso em que o participante não está na lista
            # Por exemplo, registrar um log ou notificar o administrador
            print(f"Participante {agent.name} não encontrado na lista.")

    def start(self):
        print("Chat iniciado. Objetivo atual:", self.goal)

    def stop(self):
        print("Parando o chat...")
        self.running = False  # Define a flag de execução como False para parar o loop
        print("Chat finalizado. Resumo da conversa:", self.contexto)

    def execute_round(self):
        print(f"Iniciando rodada {self.round}.")
        # Verificar se o mestre é humano ou automático
        if isinstance(self.mestre, HumanoMestre):
            # Usar os métodos do HumanoMestre
            atingiu_objetivo = self.mestre.mediar_conversa()
            if atingiu_objetivo:
                print("Objetivo alcançado. Encerrando a conversa.")
                self.stop()
                return
            proximo = self.mestre.escolher_proximo(self.participantes)
        else:
            # Usar os métodos automáticos para mediação e escolha do próximo agente
            atingiu_objetivo = self.mediar_conversa()
            if atingiu_objetivo:
                self.stop()
                return
            proximo = self.escolher_proximo()
        print(f"Próximo agente a participar: {proximo.name}")
        self.role_play(proximo)
        self.round += 1
        self.atualizar_csvs()

    def run(self):
        self.start()  # Inicia o chat
        while self.round < self.max_rounds and self.running:
            self.execute_round()  # Executa um ciclo da conversa
        self.stop()  # Finaliza o chat

    def carregar_conversa(self, diretorio_carregamento):
        # Carregar o estado do chat a partir de um arquivo JSON
        try:
            with open(os.path.join(diretorio_carregamento, "estado_chat.json"), 'r') as f:
                estado = json.load(f)
                self.goal = estado.get("goal", "")
                # Restaurar outros estados necessários
        except FileNotFoundError:
            print("Arquivo de estado não encontrado.")

        # Carregar mensagens da conversa a partir dos arquivos CSV
        try:
            with open(os.path.join(diretorio_carregamento, "conversa.csv"), 'r') as f:
                reader = csv.DictReader(f)
                self.conversa = [row for row in reader]
        except FileNotFoundError:
            print("Arquivo de conversa não encontrado.")

        try:
            with open(os.path.join(diretorio_carregamento, "conversa_ativa.csv"), 'r') as f:
                reader = csv.DictReader(f)
                self.conversa_ativa = [row for row in reader]
        except FileNotFoundError:
            print("Arquivo de conversa ativa não encontrado.")
