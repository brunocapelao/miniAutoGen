# MiniAutoGen Versioning Best Practices

## Introdução

Este documento estabelece as melhores práticas de versionamento para o MiniAutoGen, visando manter a clareza, previsibilidade e compatibilidade. Seguindo estas diretrizes, garantimos que os usuários e contribuidores do MiniAutoGen tenham uma compreensão clara do significado de cada versão.

## Conformidade com PEP 440

- Todas as versões do MiniAutoGen devem estar em conformidade com a [PEP 440](https://www.python.org/dev/peps/pep-0440/).
- Esta conformidade assegura a compatibilidade com ferramentas comuns do ecossistema Python, como pip e setuptools.

## Esquema de Versionamento Semântico (SemVer)

- **Escolha Preferencial**: O MiniAutoGen adotará o [Versionamento Semântico](https://semver.org/).
- **Formato**: As versões seguirão o formato MAJOR.MINOR.PATCH.
  - **MAJOR**: Incrementado para mudanças incompatíveis na API.
  - **MINOR**: Incrementado para adições de funcionalidades compatíveis com versões anteriores.
  - **PATCH**: Incrementado para correções de bugs compatíveis com versões anteriores.

## Versionamento Baseado em Data

- Em casos especiais, como lançamentos significativos ou edições comemorativas, podemos adotar um esquema de versionamento baseado em data (ANO.MÊS).

## Versionamento Serial

- Esta abordagem será evitada devido à sua baixa informatividade sobre compatibilidade e mudanças de funcionalidades.

## Esquemas Híbridos

- Podemos considerar esquemas híbridos para situações específicas, combinando SemVer com elementos de versionamento baseado em data.

## Versionamento de Pré-lançamento

- **Desenvolvimento**: `.devN` para lançamentos em desenvolvimento.
- **Alfa**: `.aN` para lançamentos alfa.
- **Beta**: `.bN` para lançamentos beta.
- **Candidatos a Lançamento**: `.rcN` para release candidates.
- Os pré-lançamentos não serão instalados por padrão pelo pip e outros instaladores de pacotes.

## Processo de Decisão de Versão

- Detalhar como e quando as decisões de versionamento são tomadas.
- Incluir um fluxo de trabalho para incrementar versões, especialmente para lançamentos MAJOR e MINOR.

## Registros de Alterações (Changelog)

- Manter um arquivo `CHANGELOG.md` atualizado, detalhando as mudanças em cada lançamento.
- Cada entrada deve incluir o número da versão, data de lançamento e uma lista de mudanças.

## Conclusão

Este documento orienta a equipe do MiniAutoGen e a comunidade sobre como gerenciar e interpretar as versões do software. Seguir estas práticas garantirá que as versões sejam consistentes, previsíveis e informativas.




poetry install --with dev