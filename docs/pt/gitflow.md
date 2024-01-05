# Gitflow Workflow Guide for MiniAutoGen Contributors

## Introduction

Este guia destina-se a contribuidores do projeto MiniAutoGen e oferece uma visão geral de como usamos o Gitflow Workflow para organizar o desenvolvimento do projeto.

## Overview of Gitflow

Gitflow é uma estratégia de branching que envolve várias branches para diferentes propósitos, garantindo organização e fluidez no desenvolvimento.

### Branches Principais

- **Main/Master**: Esta é a branch de código de produção. Ela contém uma versão do código que está em produção.
- **Develop**: Branch para desenvolvimento ativo. Todas as novas features são mescladas aqui antes de serem levadas para a branch principal.

### Branches de Suporte

- **Feature Branches**: Criadas a partir da branch `develop` para novas features.
- **Release Branches**: Criadas a partir da `develop` para preparar um lançamento.
- **Hotfix Branches**: Criadas a partir da `main/master` para correções urgentes.

## Gitflow Workflow Steps for MiniAutoGen

### 1. Developing New Features

1. **Create a Feature Branch**:
   ```bash
   git checkout develop
   git pull
   git checkout -b feature/[feature_name]
   ```
   *Substitua `[feature_name]` pelo nome da sua funcionalidade.*

2. **Develop Your Feature**:
   - Faça suas alterações no código.
   - Faça commits regulares para salvar seu progresso.

3. **Merge Back to Develop**:
   - Após completar a feature, faça merge de sua branch na `develop`.
   - Solicite um Pull Request (PR) para a branch `develop` para revisão.

### 2. Preparing a Release

1. **Create a Release Branch**:
   ```bash
   git checkout develop
   git checkout -b release/[version]
   ```
   *Substitua `[version]` pela versão do lançamento.*

2. **Finalize the Release**:
   - Conclua todos os ajustes para o lançamento.
   - Atualize o número da versão, se necessário.
   - Abra um PR para mesclar a branch de release na `main/master` e na `develop`.

### 3. Hotfixes

1. **Create a Hotfix Branch**:
   ```bash
   git checkout main
   git checkout -b hotfix/[hotfix_name]
   ```
   *Substitua `[hotfix_name]` pelo nome da correção.*

2. **Implement the Hotfix**:
   - Realize as correções necessárias.
   - Abra um PR para mesclar a branch de hotfix na `main/master` e na `develop`.

## Best Practices

- **PR Reviews**: Todos os PRs devem passar por revisões antes de serem mesclados.
- **Testing**: Teste suas alterações extensivamente antes de solicitar a mesclagem.
- **Documentation**: Atualize a documentação conforme necessário para refletir suas alterações.