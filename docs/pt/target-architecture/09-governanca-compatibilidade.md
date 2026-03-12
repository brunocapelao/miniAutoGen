# Governança de Compatibilidade Pública

## Objetivo

Definir regras operacionais de compatibilidade para que o MiniAutoGen evolua como biblioteca corporativa sem ambiguidade.

## Classificação de estabilidade

### `stable`

- API pública suportada;
- sujeita a versionamento semântico;
- breaking change exige mudança de versão compatível com a política oficial.

### `experimental`

- API pública exposta para validação;
- pode mudar mais rapidamente;
- deve ser marcada explicitamente em documentação e changelog.

### `internal`

- não faz parte da compatibilidade pública;
- pode mudar sem compromisso externo.

## O que constitui breaking change

### Em APIs públicas

- remoção de classe, função ou método público;
- mudança incompatível de assinatura;
- alteração semântica relevante do contrato retornado;
- mudança de comportamento documentado sem marcação de depreciação.

### Em modelos persistidos

- remoção ou mudança incompatível de campos necessários;
- alteração de schema sem versionamento;
- mudança de significado de campos persistidos já publicados.

### Em eventos

- remoção de tipo de evento estável;
- alteração incompatível de payload de evento estável;
- mudança de semântica de correlação ou ordering documentado.

## Política sugerida de depreciação

1. marcar explicitamente o item como deprecated;
2. documentar substituto recomendado;
3. anunciar janela de remoção;
4. só remover após pelo menos um ciclo de transição relevante.

## Regras para facades legadas

- facades legadas devem ser documentadas como compatibilidade transitória;
- devem apontar para o substituto arquitetural;
- não devem receber expansão funcional nova, salvo correções necessárias;
- precisam de data ou condição explícita de corte.

## Governança de schemas e eventos

- todo schema persistido deve carregar versão;
- eventos estáveis devem ter taxonomia documentada;
- mudança em evento estável deve passar por revisão arquitetural;
- consumers externos devem ser considerados antes de alterar payload estável.
