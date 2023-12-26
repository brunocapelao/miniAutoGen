from agent import Agent

class GroupChatAdmin(Agent):
    def __init__(self, agent_id, name, role, pipeline, group_chat, goal):
        super().__init__(agent_id, name, role, pipeline)
        self.group_chat = group_chat
        self.goal = goal
        self.round = 0
        self.max_rounds = 9
        self.running = True

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        self.start()
        while self.round < self.max_rounds and self.running:
            self.execute_round()
        self.stop()

    def execute_round(self):
        if self.round < self.max_rounds and self.running:
            # Passando o group_chat como parte dos kwargs
            self.generate_reply(chatgroup=self.group_chat)
            self.group_chat.persist()
            self.round += 1
        else:
            self.stop()
