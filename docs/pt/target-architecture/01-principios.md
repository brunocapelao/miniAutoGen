# Princípios Arquiteturais

## Objetivo

Definir os princípios que devem orientar a evolução do MiniAutoGen. Estes princípios servem como filtro para adoção de bibliotecas, desenho de APIs e decisões de modularização.

## 1. Elegância por redução, não por ausência de capacidade

O MiniAutoGen deve continuar pequeno na superfície pública, mas isso não significa ser frágil ou informal internamente. A elegância procurada aqui é a de uma base enxuta com peças fortes e contratos explícitos.

Implicações práticas:

- poucas abstrações centrais;
- APIs previsíveis;
- baixo número de conceitos fundamentais;
- extensibilidade por composição;
- pouca mágica implícita.

## 2. Microkernel antes de framework totalizante

O núcleo deve conhecer apenas:

- contratos de domínio;
- contratos de execução;
- contratos de persistência;
- contratos de integração.

Tudo o que for fornecedor, transporte, policy operacional ou tooling externo deve morar fora do núcleo.

Implicações práticas:

- o core não deve depender conceitualmente de um vendor de LLM;
- retry, tracing e logging não devem invadir o domínio;
- providers e stores devem entrar por adapters finos;
- o core deve continuar utilizável mesmo sem integrações opcionais.

## 3. Contracts-first

Tipos e contratos devem preceder implementação.

Isso significa:

- modelos públicos bem definidos;
- schemas geráveis e versionáveis;
- validação explícita;
- redução do uso de `dict[str, Any]` como formato principal de fronteira.

No desenho alvo, contratos têm prioridade sobre convenções implícitas.

## 4. Runtime disciplinado

Sistemas orientados a pipeline e concorrência assíncrona degradam rapidamente quando cancelamento, timeout e shutdown são tratados de forma ad hoc.

O runtime alvo do MiniAutoGen deve oferecer:

- timeouts consistentes;
- cancelamento estruturado;
- fan-out controlado;
- shutdown previsível;
- responsabilidade centralizada pela execução.

## 5. Adapters finos e substituíveis

Uma integração boa resolve uma responsabilidade muito bem e não contamina o restante da arquitetura.

Exemplos:

- HTTP deve entrar por uma camada de adapter;
- provedores de LLM devem entrar por uma interface comum;
- engines de template devem ficar atrás de contrato;
- stores devem ser intercambiáveis sem reescrever o domínio.

## 6. Observabilidade lateral

Observabilidade é necessária, mas não deve se tornar o vocabulário do domínio.

Portanto:

- o domínio emite eventos;
- a camada observável transforma esses eventos em traces, métricas e logs;
- o core não precisa saber qual vendor de observabilidade está ativo.

## 7. Persistência limpa

Persistência deve ser uma capacidade do sistema, não uma forma de organizar o domínio.

O desenho recomendado é:

- domínio fala com protocolos;
- infra implementa protocolos;
- queries e transações são preocupação da camada de store;
- o core não herda semântica ORM.

## 8. Unix-like

Ser unix-like aqui significa:

- cada peça faz poucas coisas e as faz bem;
- contratos são simples;
- composição vale mais que herança;
- bordas são explícitas;
- a solução coopera bem com tooling padrão de engenharia.

## 9. Corporativo sem inflar

O objetivo não é “enterprise framework”, e sim “biblioteca confiável em contexto corporativo”.

Isso exige:

- boa previsibilidade operacional;
- telemetria adequada;
- persistência séria;
- testes sólidos;
- typing e lint fortes;
- documentação que suporte validação por times de engenharia.

## 10. Adoção incremental

A arquitetura alvo deve poder ser construída em etapas, preservando o valor do código existente.

Consequências:

- primeiro estabilizar contratos;
- depois estabilizar runtime;
- depois fortalecer stores e observabilidade;
- só então expandir capacidades opcionais.

## Critério de aprovação de novas dependências

Uma dependência nova só deve entrar quando:

1. resolver uma responsabilidade claramente delimitada;
2. reduzir complexidade total do sistema;
3. melhorar previsibilidade, qualidade ou capacidade operacional;
4. respeitar o desenho de contracts-first e adapters finos;
5. não transformar o core em refém de fornecedor ou framework.
