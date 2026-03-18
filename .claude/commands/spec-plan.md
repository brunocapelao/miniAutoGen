Gere um plano técnico a partir de uma spec existente.

## Instruções

1. Identifique a spec alvo:
   - Se $ARGUMENTS contém um número ou nome, use-o para localizar em `.specs/`
   - Caso contrário, liste os directórios em `.specs/` e peça ao utilizador para escolher

2. Leia o ficheiro `.specs/NNN-nome/spec.md` na íntegra.

3. Analise a spec e gere o plano técnico preenchendo `.specs/NNN-nome/plan.md`:
   - **Módulos Afetados:** Identifique quais módulos do projecto serão tocados consultando a estrutura real do repositório (`miniautogen/core/`, `miniautogen/adapters/`, etc.)
   - **Contratos e Interfaces:** Defina novos protocolos/interfaces necessários ou alterações a existentes, com assinaturas Python concretas
   - **Riscos e Mitigações:** Identifique pelo menos 2 riscos técnicos reais
   - **Estimativa de Complexidade:** Baseie-se no número de ficheiros e testes
   - **Sequência de Implementação:** Ordene os passos respeitando dependências

4. Valide o plano:
   - [ ] Todos os módulos afetados existem no repositório ou estão claramente marcados como "Novo"?
   - [ ] Contratos respeitam as invariantes da spec?
   - [ ] Riscos têm mitigações concretas (não genéricas)?
   - [ ] Sequência de implementação é test-first?

5. Salve o plano preenchido em `.specs/NNN-nome/plan.md`.

6. Apresente um resumo ao utilizador e informe:
   - Use `/spec-tasks` para decompor o plano em tarefas executáveis
