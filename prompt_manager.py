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
    prompt = (f"""
### Objetivo Principal e Contexto:
Você é {agent.name}, um Agente GPT Customizado projetado para colaborar na resolução de problemas em um ambiente de conversação com outros agentes especializados. Sua função principal é analisar, compreender e contribuir para a discussão, utilizando seu conhecimento específico para auxiliar na solução de questões complexas. Você deve interagir de forma eficaz com os outros agentes, respeitando seus perfis e áreas de especialização.

### Perfil e Especialização:
Nome: {agent.name}
Área de Especialização: {agent.system}

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
    """)

    return prompt


def prompt_conclusao(conversa_ativa, participantes, goal, contexto):
    prompt = "Você é o Agente de Avaliação e Direcionamento. Sua função é analisar a eficácia da conversa atual, verificar se os objetivos estão sendo alcançados e orientar os participantes para manter o foco na meta estabelecida.\n\n"

    prompt += f"Objetivo Definido da Conversa: {goal}\n"
    prompt += f"Contexto e Dinâmica Atuais: {contexto}\n\n"
    prompt += "Perfis dos Participantes e Suas Funções:\n"
    for participante in participantes:
        prompt += f"- Nome: {participante.name}, Função: {participante.system}\n"

    prompt += "\nAnálise das Últimas Interações:\n"
    # Limitando a análise às últimas mensagens para focar nas contribuições mais relevantes
    for mensagem in conversa_ativa[-5:]:  # Reduzindo para 5 mensagens para maior relevância
        prompt += f"- {mensagem['role']} disse: '{mensagem['content']}'\n"

    prompt += "\nAvaliação do Progresso:\n"
    prompt += "Com base na dinâmica atual da conversa e no contexto, avalie se o objetivo está sendo alcançado. Responda com 'Verdadeiro' se o objetivo foi atingido ou 'Falso' se ainda não foi alcançado. Inclua breves recomendações para os próximos passos.\n"

    return prompt



def prompt_proximo(conversa_ativa, participantes, goal, contexto):
    prompt = "Você é o Agente Moderador. Sua missão é orientar a conversa de forma eficiente, assegurando que a discussão permaneça focada no objetivo estabelecido e que cada participante contribua de maneira construtiva. Analise as contribuições anteriores e direcione o próximo passo da conversa.\n\n"

    prompt += f"Objetivo Principal da Conversa: {goal}\n"
    prompt += f"Contexto Atual e Relevantes: {contexto}\n\n"
    prompt += "Lista de Participantes e Seus Perfis Específicos:\n"
    for participante in participantes:
        prompt += f"- Nome: {participante.name}, Perfil: {participante.system}\n"

    prompt += "\nÚltimas Interações da Conversa:\n"
    for mensagem in conversa_ativa[-5:]:  # Reduzindo para as últimas 5 mensagens para focar na relevância atual
        prompt += f"- {mensagem['role']} disse: '{mensagem['content']}'\n"

    prompt += "\nDecisão do Moderador:\n"
    prompt += "Com base na dinâmica atual da conversa e no progresso em direção ao objetivo, indique quem deve falar a seguir para contribuir efetivamente. Responda com o nome do participante selecionado.\n"

    return prompt



def prompt_resumo_contexto(conversa_ativa, participantes, goal, contexto):
    prompt = "Você é o Agente de Análise e Síntese. Sua função é avaliar a discussão até o momento, considerando o objetivo estabelecido, o contexto atual e as contribuições de cada participante. Com base nesta avaliação, elabore um resumo abrangente que destaque os pontos-chave, o progresso em relação ao objetivo e qualquer insight relevante.\n\n"

    prompt += f"Objetivo Central da Conversa: {goal}\n"
    prompt += f"Contexto Atual e Dinâmicas Relevantes: {contexto}\n\n"
    prompt += "Perfis dos Participantes e Suas Contribuições:\n"
    for participante in participantes:
        prompt += f"- Nome: {participante.name}, Função: {participante.system}\n"

    prompt += "\nRegistro Detalhado das Interações:\n"
    # Inclui apenas as últimas mensagens para focar na relevância atual e evitar sobrecarga de informações
    for mensagem in conversa_ativa[-10:]:
        prompt += f"- {mensagem['role']} disse: '{mensagem['content']}'\n"

    prompt += "\nResumo e Avaliação:\n"
    prompt += "Elabore um resumo conciso e direto da conversa, destacando as contribuições significativas, o progresso em direção ao objetivo e recomendações estratégicas para os próximos passos na discussão.\n"

    return prompt

