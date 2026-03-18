Decomponha um plano técnico em tarefas executáveis.

## Instruções

1. Identifique a spec alvo:
   - Se $ARGUMENTS contém um número ou nome, use-o para localizar em `.specs/`
   - Caso contrário, liste os directórios em `.specs/` e peça ao utilizador para escolher

2. Leia os ficheiros:
   - `.specs/NNN-nome/spec.md` (para contexto e critérios de aceitação)
   - `.specs/NNN-nome/plan.md` (para a sequência de implementação)

3. Decomponha o plano em tarefas atómicas preenchendo `.specs/NNN-nome/tasks.md`:
   - Cada tarefa deve ser pequena o suficiente para um único commit
   - Numere sequencialmente: T001, T002, T003...
   - Para cada tarefa defina:
     - **Título** claro e conciso
     - **Status** inicial: TODO
     - **P (Paralelizável):** sim se pode ser feita em paralelo com outras
     - **Deps:** lista de tarefas das quais depende
     - **Descrição:** o que fazer concretamente
     - **Critério de conclusão:** checklist verificável

4. Regras de decomposição:
   - Primeira tarefa é SEMPRE escrever/atualizar testes (test-first)
   - Tarefas de teste vêm ANTES das tarefas de implementação
   - Agrupe tarefas paralelizáveis quando possível
   - Última tarefa é SEMPRE validação E2E / integração

5. Gere o grafo de dependências em texto ASCII.

6. Preencha o resumo (paralelizáveis / sequenciais / total).

7. Salve em `.specs/NNN-nome/tasks.md`.

8. Apresente um resumo ao utilizador com:
   - Total de tarefas
   - Caminho crítico (sequência mais longa de dependências)
   - Tarefas que podem ser executadas em paralelo
