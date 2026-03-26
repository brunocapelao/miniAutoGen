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
- Verificar build Docker:
  - `docker compose build`
  - `docker compose up -d` e confirmar que o console responde em `http://localhost:8080`
  - `docker compose down`
- Verificar build do frontend do Console:
  - `cd console && npm ci && npm run build` (ou verificar que os assets estaticos existem em `console/out/`)
- Smoke test de todos os 16 comandos CLI:
  - `miniautogen init test-release --template quickstart`
  - `miniautogen check`
  - `miniautogen doctor`
  - `miniautogen status`
  - `miniautogen engine list`
  - `miniautogen engine discover`
  - `miniautogen engine create smoke-engine --provider openai --model gpt-4o-mini`
  - `miniautogen engine show smoke-engine`
  - `miniautogen engine update smoke-engine --temperature 0.5`
  - `miniautogen engine delete smoke-engine --confirm`
  - `miniautogen agent list`
  - `miniautogen agent create smoke-agent --role "Test" --goal "Test" --engine default_api`
  - `miniautogen agent show smoke-agent`
  - `miniautogen agent delete smoke-agent --confirm`
  - `miniautogen flow list`
  - `miniautogen flow create smoke-flow --mode workflow --participants researcher`
  - `miniautogen flow show smoke-flow`
  - `miniautogen flow delete smoke-flow --confirm`
  - `miniautogen run main --input "test" --timeout 30` (requer API key)
  - `miniautogen send "hello" --agent researcher` (requer API key)
  - `miniautogen daemon start && miniautogen daemon status && miniautogen daemon stop`
  - `miniautogen sessions list`
  - `miniautogen server start --daemon && miniautogen server status && miniautogen server stop`
  - `miniautogen completions bash`
  - `miniautogen dash` (verificar que abre sem erros)
  - `miniautogen console` (verificar que abre sem erros)
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
