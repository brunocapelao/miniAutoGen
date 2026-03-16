# MiniAutoGen

MiniAutoGen é uma biblioteca leve para orquestração de conversas, pipelines e execução multiagente com arquitetura assíncrona, adapters finos e contratos tipados.

O repositório hoje está organizado em torno de três eixos:
- arquitetura atual do framework
- arquitetura alvo e decisões tecnológicas
- integração operacional com Gemini CLI via gateway compatível com OpenAI

## Estado atual

O núcleo atual do projeto é baseado em:
- `PipelineRunner` como runtime oficial
- contratos tipados em `miniautogen/core/contracts`
- stores separados para mensagens, runs e checkpoints
- adapters de LLM desacoplados do core
- compatibilidade legada mantida apenas onde ainda necessário

## Gemini CLI

O caminho suportado para usar Gemini CLI como motor LLM é:
- `gemini_cli_gateway/` como gateway local compatível com `/v1/chat/completions`
- `OpenAICompatibleProvider` como adapter HTTP do MiniAutoGen

Guia rápido:
- [Gemini CLI Gateway](docs/pt/guides/gemini-cli-gateway.md)

## Documentação principal

- [Documentação em português](docs/pt/README.md)
- [Arquitetura atual (C4)](docs/pt/architecture/README.md)
- [Arquitetura alvo](docs/pt/target-architecture/README.md)
- [Referência rápida dos módulos](docs/pt/quick-reference.md)

## Exemplos executáveis

- [Tutorial da nova arquitetura](output/jupyter-notebook/miniautogen-nova-arquitetura-tutorial.ipynb)
- [Mini app com Gemini CLI](output/jupyter-notebook/miniautogen-mini-app-exemplo.ipynb)

## Observação

A documentação histórica antiga em inglês, os planos intermediários de execução e anotações superseded foram removidos para reduzir ruído. O repositório agora prioriza documentação viva e alinhada com o código atual.
