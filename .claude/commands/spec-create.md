Crie uma nova spec para uma feature do MiniAutoGen.

## Instruções

1. Pergunte ao utilizador: "Descreva a feature que deseja implementar." (se não foi fornecida como argumento: $ARGUMENTS)

2. Execute o script de criação:
   ```
   bash scripts/specs/create-feature.sh <nome-slug-da-feature>
   ```
   Derive o slug a partir da descrição (lowercase, hifens, sem acentos, conciso).

3. Abra o ficheiro `spec.md` criado no directório `.specs/NNN-nome/`.

4. Preencha o template com base na descrição fornecida:
   - **Goal:** Sintetize o objetivo principal
   - **Constraint:** Identifique quais invariantes arquiteturais (CLAUDE.md §3) são relevantes
   - **Failure Condition:** Defina critérios objetivos de falha
   - **User Stories:** Extraia 2-3 user stories da descrição
   - **Critérios de Aceitação:** Liste critérios verificáveis
   - **Invariantes Afetadas:** Marque as checkboxes relevantes
   - **Dependências:** Liste dependências internas e externas

5. Valide a qualidade da spec com esta checklist:
   - [ ] Goal é específico e mensurável?
   - [ ] Constraint referencia invariantes reais do CLAUDE.md?
   - [ ] Failure Condition é objetiva (não subjetiva)?
   - [ ] Pelo menos 2 user stories?
   - [ ] Pelo menos 3 critérios de aceitação?
   - [ ] Invariantes relevantes estão marcadas?
   - [ ] Status está como "Rascunho"?

6. Apresente a spec preenchida ao utilizador e pergunte se deseja ajustes.

7. Informe os próximos passos:
   - Use `/spec-plan` para gerar o plano técnico
   - Use `/spec-tasks` para decompor em tarefas
