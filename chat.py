import os
import json
import pandas as pd
from prompt_manager import role_play_prompt, prompt_conclusao, prompt_proximo, prompt_resumo_contexto, system_role_play
from agent import AutomatedAgent

class Chat():
    def __init__(self, goal, diretorio_salvamento=None):
        self.mestre = None  # O mestre pode ser uma instância de AutomatedAgent ou HumanAgent
        self.conversa = []
        self.conversa_ativa = []
        self.participantes = []  # Lista de instâncias de Agent (AutomatedAgent ou HumanAgent)
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
        print(f"({role}) {content}")
        self.conversa.append({'role': role, 'content': content})

    def send(self, agente, content, system):
        response = agente.send(content, system)
        self.adicionar_mensagem(agente.name, response)
        return response

    def obter_estado_conversa(self):
        return self.conversa
    
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

    def role_play(self, agente):
        participantes_sem_agente = [p for p in self.participantes if p != agente]
        content = role_play_prompt(agente, self.goal, self.contexto, self.conversa, participantes_sem_agente)
        system = agente.system
        if isinstance(agente, AutomatedAgent):
            system = system_role_play(agente)
            self.send(agente, content, system)
            return
        self.send(agente, content, system)

    def mediar_conversa(self):
        prompt = prompt_conclusao(self.conversa_ativa, self.participantes, self.goal, self.contexto)
        result = self.mestre.send(prompt)
        if result == "True":
            self.stop()

    def escolher_proximo(self):
        prompt = prompt_proximo(self.conversa_ativa, self.participantes, self.goal, self.contexto)
        resposta_mestre = self.mestre.send(prompt)
        nome_proximo_agente = self.analisar_resposta_mestre(resposta_mestre)
        proximo_agente = next((agente for agente in self.participantes if agente.name == nome_proximo_agente), None)
        return proximo_agente

    def start(self):
        print("Chat iniciado. Objetivo atual:", self.goal)

    def stop(self):
        print("Parando o chat...")
        self.running = False  # Define a flag de execução como False para parar o loop
        print("Chat finalizado. Resumo da conversa:", self.contexto)

    def analisar_resposta_mestre(self, resposta):
        # Implementar lógica para extrair o nome do próximo agente da resposta do mestre
        # Esta é uma implementação simplificada. Você precisará ajustar com base no formato exato da resposta do mestre.
        # Exemplo: assumindo que o primeiro elemento da resposta é o nome do agente
        return resposta.split()[0]

    def execute_round(self):
        if self.round < self.max_rounds:
            atingiu_objetivo = self.mestre.mediar_conversa()  # Usa a implementação específica do mestre
            if atingiu_objetivo:
                self.stop()
                return
            proximo = self.mestre.escolher_proximo(self.participantes)  # Usa a implementação específica do mestre
            self.role_play(proximo)
            self.round += 1
            self.atualizar_csvs()
        else:
            self.stop()

    def run(self):
        self.start()
        while self.round < self.max_rounds and self.running:
            self.execute_round()
        self.stop()

    # Método carregar_conversa permanece o mesmo
