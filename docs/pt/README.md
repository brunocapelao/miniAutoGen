# Documentação em Português

Esta seção reúne a documentação do MiniAutoGen em português.

## Referência principal de arquitetura

A documentação arquitetural atualizada está centralizada na trilha C4:

- [Arquitetura do MiniAutoGen](architecture/README.md)
- [C4 Nível 1: Contexto do sistema](architecture/01-contexto.md)
- [C4 Nível 2: Containers lógicos](architecture/02-containers.md)
- [C4 Nível 3: Componentes internos](architecture/03-componentes.md)
- [Fluxos de execução](architecture/04-fluxos.md)

## Arquitetura alvo e decisões tecnológicas

Para a visão de evolução do framework e a base de conhecimento técnica:

- [Arquitetura alvo do MiniAutoGen](target-architecture/README.md)
- [Princípios arquiteturais](target-architecture/01-principios.md)
- [Matriz tecnológica](target-architecture/02-matriz-tecnologica.md)
- [Arquitetura alvo](target-architecture/03-arquitetura-alvo.md)
- [Roadmap de adoção](target-architecture/04-roadmap-adocao.md)
- [Modelo de persistência](target-architecture/05-modelo-persistencia.md)
- [Invariantes e taxonomias](target-architecture/06-invariantes-e-taxonomias.md)
- [Plano de migração](target-architecture/07-plano-de-migracao.md)
- [Mapa físico de módulos](target-architecture/08-mapa-modulos.md)
- [Governança de compatibilidade](target-architecture/09-governanca-compatibilidade.md)
- [Base de conhecimento](target-architecture/10-base-de-conhecimento.md)

## Guias resumidos por módulo

Os documentos abaixo foram mantidos como guias rápidos e pontos de entrada:

- [Agent](agent.md)
- [Chat](chat.md)
- [ChatAdmin](chatadmin.md)
- [Pipelines](pipelines.md)
- [Componentes](components.md)

## Observação

Parte da documentação histórica descrevia uma arquitetura anterior baseada em persistência por arquivo e estruturas tabulares. A trilha C4 acima reflete o estado atual do código, com execução assíncrona, abstração de repositório e integração com LLMs por clientes assíncronos.
