# Atividade individual 1: Serverless (Rota Vital)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)

**Português** | [English](README.en.md)

Infraestrutura de Software · ADS · CESAR School · 2026.2

Uma função HTTP que recebe uma requisição do Rota Vital e devolve a **guia de transporte**, rodando no computador com o **AWS SAM CLI** (Caminho A do enunciado, sem conta na AWS e sem publicar na nuvem).

- **Caminho escolhido:** A (AWS SAM CLI local, Python 3.12, Docker Desktop).
- **Ambiente:** Windows, comandos rodados no Git Bash. SAM CLI 1.174.0 instalado com `python -m pip install --user aws-sam-cli` (o `sam.exe` fica em `...\Python312\Scripts`, que precisa estar no `PATH`).
- **Evidências:** pasta [`evidencias/`](evidencias/), com a saída de cada comando.

## Como rodar

```bash
export SAM_CLI_TELEMETRY=0
# Docker Desktop precisa estar aberto

# testes unitários do handler (sem Docker)
python -m unittest tests.unit.test_handler -v

# Passo 3: evento + invocação
sam local generate-event apigateway aws-proxy --method POST --path guias \
  --body '{"requisicaoId":"R-001","hospital":"H-Recife","bolsas":["O-NEG-0142"]}' > events/pedido.json
sam build
sam local invoke -e events/pedido.json

# Passo 4: HTTP (outro terminal para o curl)
sam local start-api                         # e depois: sam local start-api --warm-containers LAZY
curl -X POST http://127.0.0.1:3000/guias -H "Content-Type: application/json" \
  -d '{"requisicaoId":"R-002","hospital":"H-Caruaru"}'

# Passo 5: limite de tempo (Timeout 3 no template, depois 10)
curl -X POST http://127.0.0.1:3000/guias -H "Content-Type: application/json" \
  -d '{"requisicaoId":"R-003","demorar":true}'
```

O projeto saiu do `sam init` (Hello World, Python 3.12, zip). No `template.yaml` troquei a rota de `/hello` (GET) para `/guias` (POST) e o `hello_world/app.py` é a função do enunciado. O `Timeout` do template está em **10** porque o Passo 5 termina com o ajuste.

## O que mudou em relação ao PDF

**1. Corpo do evento em base64.** O `sam local generate-event` da versão 1.174 gera o `body` em base64 com `"isBase64Encoded": true`. O handler do PDF lê o `body` direto e falhou com `JSONDecodeError` (as saídas da tentativa estão em `evidencias/02a-...` e `02b-...`). Acrescentei ao handler a decodificação quando `isBase64Encoded` é verdadeiro (3 linhas) e um teste unitário para esse caso. Pelo HTTP (`start-api`) o corpo chega em texto simples e não é afetado.

**2. `start-api` sem `--warm-containers` já reaproveita o ambiente.** O PDF espera que, sem a opção, o `invocacaoNesteAmbiente` volte a 1 a cada chamada. Nesta versão do SAM, o log mostra "Initializing the lambda functions containers" já na subida: o container é criado antes da primeira requisição e reaproveitado. O contador cresceu 1, 2, 3 nos dois modos. A diferença visível foi o tempo da primeira chamada (tabela abaixo). Já o `sam local invoke` cria um container novo a cada execução e o contador ficou em 1 nas duas.

## Resultados medidos

| Experimento | Resultado | Tempo | Evidência |
|---|---|---|---|
| `sam local invoke` (1ª, falhou por base64) | `JSONDecodeError`, Duration 96,38 ms | 28,06 s no relógio (incluiu montar a imagem Docker) | `02a-...` |
| `sam local invoke` (2ª, falhou por base64) | `JSONDecodeError`, Duration 115,78 ms | 6,52 s | `02b-...` |
| `sam local invoke` (1ª, corrigido) | 201, guia `G-R-001`, contador 1, Duration 93,95 ms, Init 0,08 ms | 5,38 s | `03-invoke-1.txt` |
| `sam local invoke` (2ª, corrigido) | 201, contador 1, Duration 104,30 ms, Init 0,13 ms | 5,59 s | `03-invoke-2.txt` |
| `start-api` sem opção, 3 chamadas | 201 nas três, contador 1, 2, 3 | 1,21 s, 1,08 s, 1,08 s | `04a-curl-sem-warm.txt` |
| `start-api --warm-containers LAZY`, 3 chamadas | 201 nas três, contador 1, 2, 3 | 3,93 s, 1,10 s, 1,12 s | `04b-curl-warm-lazy.txt` |
| `demorar: true`, Timeout 3 | HTTP 502 `{"message":"Internal server error"}`; log: `Function 'HelloWorldFunction' timed out after 3 seconds` | 4,18 s | `05a-curl-timeout3.txt` |
| `demorar: true`, Timeout 10 | 201, guia `G-R-003` | 6,21 s | `05b-curl-timeout10.txt` |

O tempo "no relógio" inclui o custo do emulador (subir o container Docker, enviar o evento), por isso é muito maior que o `Duration` da função, que é o tempo do handler.

## Respostas

**1. Por que a primeira invocação demorou mais que a segunda? O que acontece na fase de Init?**
Na tentativa que falhou, a primeira invocação levou 28 s e a segunda 6,5 s. A diferença veio de a primeira ter de montar a imagem Docker do ambiente de execução; na segunda a imagem já existia. Depois de corrigido o evento, as duas levaram quase o mesmo tempo (5,4 s e 5,6 s), porque cada `sam local invoke` sobe um container novo, ou seja, toda invocação é uma partida a frio. Na fase de Init o serviço cria o ambiente, baixa o código, inicia o runtime e executa o que está fora do handler (imports e a variável global `contador`). Só depois chama o handler. No emulador, o `Init Duration` aparece com 0,06 a 0,13 ms: não mede a partida real, então o custo de um cold start na AWS só dá para ver nos logs do CloudWatch (caminho B).

**2. O que o `invocacaoNesteAmbiente` mostrou com e sem `--warm-containers`? O que isso diz sobre guardar estado numa variável global?**
Com `sam local invoke` ele ficou em 1 todas as vezes, porque cada execução usa um ambiente novo. No `start-api` ele cresceu 1, 2, 3 nos dois modos (nesta versão do SAM o container já é criado na subida; com LAZY só é criado na primeira requisição, e por isso a primeira chamada demorou 3,9 s). A conclusão é a mesma: a variável global só sobrevive enquanto o ambiente for reaproveitado, e quem decide isso é a plataforma, não o código. Não dá para contar com ela, porque uma nova instância começa do zero e duas instâncias em paralelo teriam contadores diferentes. Qualquer estado que importe (contagem, sessão, cache que não possa se perder) precisa ficar fora da função, por exemplo num banco.

**3. O que aconteceu com `demorar = true`? Qual é o tempo máximo de uma execução no Lambda, e o que fazer com um trabalho mais longo?**
A função dorme 5 s, mas o template limita a execução a 3 s. O SAM interrompeu a função (`timed out after 3 seconds`) e a chamada HTTP devolveu 502 com `Internal server error`. Com o Timeout em 10, a mesma chamada terminou com 201 em 6,2 s. No Lambda o tempo máximo de uma execução é de 15 minutos, conforme as cotas do serviço. Trabalho mais longo que isso se divide em etapas menores, se coloca numa fila para um processador que rode sem esse limite (um container, por exemplo), ou se orquestra por etapas com um serviço de fluxo.

**4. Quanto custa um milhão de execuções com 128 MB e 100 ms (preços de us-east-1 da aula)?**
- Requisições: 1.000.000 ÷ 1.000.000 × US$ 0,20 = **US$ 0,20**.
- Computação: 128 MB = 0,125 GB; 100 ms = 0,1 s; 0,125 × 0,1 = 0,0125 GB-s por execução. Para um milhão: 0,0125 × 1.000.000 = 12.500 GB-s. Custo: 12.500 × US$ 0,0000166667 = **US$ 0,2083**.
- Total: 0,20 + 0,2083 = **US$ 0,4083, cerca de US$ 0,41** por milhão de execuções.

Dentro da faixa sempre gratuita (1 milhão de requisições e 400 mil GB-s por mês, citada no enunciado), essa carga custaria zero.

**5. Em que parte do Rota Vital uma função assim faria sentido, e em qual não faria?**
Faz sentido para gerar a guia de transporte quando uma requisição é aprovada: é um trabalho curto, sem estado, que só roda quando o evento acontece e não precisa de servidor ligado no resto do tempo. Não faz sentido para a telemetria de temperatura: ela recebe leituras o tempo todo (até 500 por segundo no cenário alto da Seção E do trabalho em grupo), e o agregador guarda o estado em memória e precisa de uma única instância. Isso é o contrário do modelo serverless, em que várias instâncias nascem e morrem sem memória compartilhada.

## Uso de IA

- **Ferramenta:** Claude (Anthropic).
- **Finalidade:** instalar o SAM CLI e abrir o Docker, rodar os comandos dos passos 3 a 5 neste computador e gravar as saídas em `evidencias/`, corrigir o handler para o evento em base64, escrever os testes unitários e redigir o rascunho deste README.
- **Como validou:** todo resultado citado nas respostas e na tabela vem de um arquivo de `evidencias/`, gerado pelos próprios comandos; os 4 testes unitários passam; o autor revisou o texto antes da entrega (PO-CESAR-021, permitido com declaração).
