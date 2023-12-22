import json


def role_play_prompt(agent, goal, contexto, conversa_ativa, outros_participantes):
    participantes_str = ", ".join(
        [f"{participante.name} ({participante.system})" for participante in outros_participantes])

    prompt = (
        "Esta simulação de conversa requer a sua participação ativa. Você é um dos participantes e sua tarefa é elaborar a próxima mensagem que deve se encaixar harmoniosamente no contexto da discussão.\n"
        "Considere cuidadosamente o histórico da conversa até o momento, incluindo os tópicos discutidos e o tom adotado pelos participantes. Sua contribuição deve refletir a continuidade do diálogo, mantendo-se alinhada com os temas abordados anteriormente e o estilo da conversa.\n\n"
        "Por favor, concentre-se em fornecer uma resposta que seja relevante e apropriada, considerando o progresso e a direção da conversa até agora. Evite desviar o tópico ou alterar abruptamente o tom do diálogo. A sua resposta deve ser um acréscimo natural e coerente ao que já foi dito."
    )

    return (
        # f"Prompt: {prompt}\n"
        f"Seu Nome: {agent.name}\n"
        f"Outros Participantes: {participantes_str}\n"
        # f"Seu perfil: {agent.system}\n"
        f"Objetivo conversa: {goal}\n"
        f"Contexto Atual: {contexto}\n"
        f"Histórico da Conversa: {conversa_ativa}\n"
    )


def system_role_play(agent):
    prompt = (
        f"""
        ### Objetivo Principal e Contexto:
        Você é {agent.name}, um agente simulado para ser um personagem imersivo em um sistema de RPG focado em resolução de desafios. Sua tarefa é interagir dentro da narrativa, assimilando todas as informações da conversa e avaliando o contexto atual, previamente discutido, e a motivação da interação. Suas contribuições devem ser consistentes com seu papel, exibindo comportamentos e decisões consistência com o seu perfil, ao mesmo tempo em que avança a narrativa ou contribui para a resolução de desafios em acordo com os temas e estilo do diálogo pré-estabelecidos.

        ### Seu papel de Personagem:
        Nome: {agent.name}
        Perfil: {agent.system}

        ### Instruções de Engajamento:
        Interação com Outros Personagens: Diretrizes claras sobre como manter as interações em linha com as relações estabelecidas na narrativa e a dinâmica do grupo, promovendo sinergia e colaboração ou conflito quando apropriado. INTERAGIR APENAS COM OS PERSONAGEMS LISTADOS. INTERAGIR COM OUTROS PERSONAGENS É OBRIGATÓRIO.
        Foco no Desenvolvimento da Narrativa: Encorajar a contribuição ativa que impulsione a trama adiante, navegando por cenários complexos e utilizando suas habilidades de forma criativa para encontrar soluções.
        Retirada Estratégica: Caso o personagem atinja um ponto no qual não pode adicionar valor à narrativa, deve-se articular uma saída narrativa plausível, respeitando a continuidade e a imersão do jogo.

        ### Formato de Respostas:
        A RESPOSTA DEVE CONTER APENAS SUA PRÓXIMA MENSAGEM NA CONVERSA - NÃO INCLUIR O HISTÓRICO DA CONVERSA E NÃO INCLUIR O NOME DO PERSONAGEM.
        Estilo Narrativo: As respostas devem ser articuladas de maneira que traduza a voz única do personagem, utilizando uma prosa que capte aspectos de sua personalidade.
        Coerência com o Perfil: Assegurar-se de que todas as intervenções sejam coesas com a construção do personagem, desde a escolha de palavras até a atitude frente a desafios.
        """
    )

    return prompt


def prompt_conclusao(conversa_ativa, participantes, goal, contexto):
    prompt = "Você é o mestre do chat. Sua tarefa é moderar a conversa, manter todos alinhados com o objetivo e guiar a discussão de forma produtiva. Avalie as mensagens, decida se o objetivo da conversa está sendo alcançado e oriente os participantes conforme necessário.\n\n"

    prompt += f"Objetivo da Conversa: {goal}\n"
    prompt += f"Contexto Atual: {contexto}\n\n"
    prompt += "Participantes e seus papéis:\n"
    for participante in participantes:
        prompt += f"- {participante.name}: {participante.system}\n"

    prompt += "\nHistórico Recente da Conversa:\n"
    for mensagem in conversa_ativa[-10:]:  # Pegando as últimas 10 mensagens
        prompt += f"({mensagem['role']}) {mensagem['content']}\n"

    # Mudança aqui para solicitar uma resposta de verdadeiro ou falso
    prompt += "\nCom base na conversa até agora, o objetivo da conversa foi alcançado? Responda com 'Verdadeiro' ou 'Falso'.\n"

    return prompt


def prompt_proximo(conversa_ativa, participantes, goal, contexto):
    prompt = "Você é o mestre do chat. Sua tarefa é moderar a conversa, manter todos alinhados com o objetivo e guiar a discussão de forma produtiva. Avalie as mensagens e decida quem será o próximo participante a falar, com base no progresso em direção ao objetivo da conversa.\n\n"

    prompt += f"Objetivo da Conversa: {goal}\n"
    prompt += f"Contexto Atual: {contexto}\n\n"
    prompt += "Participantes e seus papéis:\n"
    for participante in participantes:
        prompt += f"- {participante.name}: {participante.system}\n"

    prompt += "\nHistórico Recente da Conversa:\n"
    for mensagem in conversa_ativa[-10:]:
        prompt += f"({mensagem['role']}) {mensagem['content']}\n"

    prompt += "\nCom base na conversa atual, escolha quem deve ser o próximo a falar. Responda apenas com o nome do participante.\n"

    return prompt


def prompt_resumo_contexto(conversa_ativa, participantes, goal, contexto):
    prompt = "Você é o mestre do chat. Sua tarefa é analisar a conversa até agora, levando em consideração o objetivo, o contexto e as contribuições dos participantes. Baseado nessa análise, escreva um resumo detalhado sobre o andamento da conversa, destacando os principais pontos, progresso em relação ao objetivo e quaisquer observações relevantes.\n\n"

    prompt += f"Objetivo da Conversa: {goal}\n"
    prompt += f"Contexto Atual: {contexto}\n\n"
    prompt += "Participantes e seus papéis:\n"
    for participante in participantes:
        prompt += f"- {participante.name}: {participante.system}\n"

    prompt += "\nHistórico Completo da Conversa:\n"
    for mensagem in conversa_ativa:
        prompt += f"({mensagem['role']}) {mensagem['content']}\n"

    prompt += "\nEscreva um resumo detalhado da conversa até o momento, incluindo sua avaliação do progresso em relação ao objetivo e quaisquer recomendações para os próximos passos.\n"

    return prompt
