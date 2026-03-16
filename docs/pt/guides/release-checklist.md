# Checklist de Release

Este checklist resume o mínimo necessário para publicar uma release do MiniAutoGen com a arquitetura nova e suporte a Gemini CLI via gateway.

## Pré-release

- Confirmar que a branch alvo está limpa.
- Confirmar a versão em `pyproject.toml`.
- Executar lint:
  - `ruff check gemini_cli_gateway miniautogen tests`
- Executar type-check do escopo suportado:
  - `python3 -m mypy gemini_cli_gateway miniautogen/adapters miniautogen/app`
- Executar a suíte crítica de integração:
  - `PYTHONPATH=. pytest tests/gemini_cli_gateway tests/adapters/test_openai_compatible_provider.py tests/app/test_provider_factory.py tests/app/test_settings.py tests/integration/test_miniautogen_with_gemini_gateway.py -q`
- Validar smoke real do Gemini CLI autenticado.
- Executar os notebooks oficiais:
  - `output/jupyter-notebook/miniautogen-nova-arquitetura-tutorial.ipynb`
  - `output/jupyter-notebook/miniautogen-mini-app-exemplo.ipynb`

## Release

- Criar tag anotada no formato `vX.Y.Z`.
- Registrar os destaques da release:
  - runtime oficial com `PipelineRunner`
  - gateway Gemini CLI compatível com OpenAI
  - `OpenAICompatibleProvider`
  - documentação consolidada e notebooks reais

## Pós-release

- Confirmar que a tag aponta para o commit aprovado.
- Publicar notas de release com instruções mínimas de uso do gateway.
- Se houver distribuição externa, validar build/publicação do pacote.

## Primeira release sugerida

- Tag: `v0.1.0`
- Escopo: primeira release pública coerente com a nova arquitetura e integração Gemini CLI.
