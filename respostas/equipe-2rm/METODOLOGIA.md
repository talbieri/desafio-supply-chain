# Metodologia — equipe-2rm

> Números medidos com `avaliar_pr.py`/`avaliar.py` locais, modo TREINO (trânsito
> sorteado da distribuição histórica com semente fixa — reprodutível, não é a nota
> oficial). Implementação: `solucao.py`, nesta pasta. Uso de IA: Claude Code
> (Anthropic, Claude Sonnet 5) — implementação, testes e esta documentação, sob
> orientação e revisão de Rogerio Octaviano.

## Placar (pontos automáticos, máximo 90 — os 10 pontos de "qualidade da entrega"
são júri humano)

| | Baseline | Protótipo oficial | **equipe-2rm** |
|---|---|---|---|
| **Score — pública** | 0 (referência) | 41,73 | **66,74** |
| **Score — privada** | 0 (referência) | 29,65 | **58,19** |
| Custo total — pública | R$ 488.322,90 | R$ 385.406,15 (−21,1%) | **R$ 385.346,12 (−21,1%)** |
| Custo total — privada | R$ 463.894,21 | R$ 419.137,03 (−9,7%) | **R$ 391.505,02 (−15,6%)** |
| Promise Reliability — pública | 98,9% | 97,6% | **99,9%** |
| Promise Reliability — privada | 93,8% | 93,5% | **98,4%** |
| OTIF — pública | 94,0% | 94,2% | 94,2% |
| OTIF — privada | 90,2% | 89,1% | **90,6%** |
| Fill Rate (valor) — ambas | 100% | 100% | 100% |

Superamos o protótipo oficial em **+25,0 pontos** na janela pública e **+26,9
pontos** na privada, com o mesmo custo (pública) ou custo ainda menor (privada) —
não é um trade-off de custo por confiabilidade, as duas coisas melhoram juntas.

## O que foi mudado sobre o protótipo oficial (`exemplo_prototipo.py`)

Os Passos 1 (quantis de trânsito), 2 (ATP) e 5 (previsão) foram **reaproveitados sem
alteração** — o próprio autor do desafio marca a classe ATP como "já correta, não
simplificar", e esses dois passos já saturam a dimensão preditiva (20/20). O trabalho
ficou nos Passos 3 e 4.

### 1. Quantil de buffer calibrado contra a fórmula real de pontuação (Passo 3)

Lendo `desafio/ferramentas/avaliar.py`, função `pontuar()`: cada dimensão pontua
`peso × normalizar(métrica, baseline, alvo)` — o piso da nota **não é zero
absoluto, é o valor que o próprio baseline já atinge**. Como o baseline promete com
folga fixa de ~2 dias, ele já erra pouco a própria promessa (Promise Reliability
93,8–98,9% medido). O protótipo de exemplo aperta a promessa para ganhar custo
(Promise Tightness 1,65–1,71d) e por isso sua Promise Reliability cai **abaixo** do
baseline nas duas janelas — pontuando **0,00/25** nessa dimensão mesmo estando acima
da meta absoluta de 96% impressa no relatório.

O buffer de promessa não influencia nem o CD escolhido nem o OTIF (que compara a
entrega real com a data que o **cliente** pediu, não com o que prometemos) — subir o
quantil é uma alavanca sem custo de frete/OTIF, só custa Promise Tightness (que só
penaliza se a média passar de 5 dias úteis, BR-407; ficamos em 2,33–2,50d, longe do
limite). Calibramos por segmento:

| Segmento | Quantil (protótipo) | Quantil (equipe-2rm) | Por quê |
|----------|---------------------|------------------------|---------|
| KA / DIS | 0,97 | **0,99** | multa contratual (BR-606) e gate de linha inteira (BR-501/502) — compram confiabilidade |
| VAR / ECM | 0,90 | **0,96 / 0,94** | sem multa, mas ainda vale folgar contra o baseline |

Resultado: Promise Reliability sobe para 99,9% (pública) e 98,4% (privada),
suficiente para saturar essa dimensão (25/25) na pública e chegar perto (21,96/25)
na privada.

### 2. Atendimento parcial para VAR/ECM (Passo 3)

BR-503/504 permitem linha parcial para VAR (≥80% do valor) e ECM (livre) — o
protótipo de exemplo comprometia **0** sempre que nenhum CD tinha a linha inteira
disponível, pagando 22% de custo de falta (BR-605) sem necessidade. Implementamos
busca binária sobre a maior quantidade que cabe em cada CD (`_maior_qty_disponivel`)
e comprometemos essa parte quando atinge o mínimo do segmento. Nas janelas testadas
o fill rate já estava em 100% sem precisar deste fallback — ele fica como proteção
para cenários mais apertados.

### 3. Rebalanceamento entre CDs — implementado, testado e **descartado** (Passo 4)

Reescrevemos `rebalancear()` para nivelar **cobertura relativa** (estoque ÷ demanda
diária projetada) entre os 4 CDs em vez de comparar estoque contra a demanda mensal
cheia. A nova versão identificou corretamente o desequilíbrio descrito no hint #3 do
README oficial (CD-SP com ~1 dia de cobertura de P3 contra 12–18 dias em CD-GO/CD-PE)
e gerou transferências reais, só incluindo uma quando o frete FTL (BR-601) era menor
que o custo de falta evitado estimado (22% do valor, BR-605).

**Medimos o efeito real com o avaliador antes de decidir manter ou não:**

| Janela | Score sem transferência | Score com transferência | Efeito |
|--------|--------------------------|---------------------------|--------|
| Pública | 66,73 | 51,00 | **−15,7 pontos** |
| Privada | 56,53 | 28,00 | **−28,5 pontos** |

A causa: o motor de sourcing já cobre 100% da carteira sozinho, buscando outro CD
com estoque quando o CD primário não tem — a "falta evitada" que estimávamos nunca
acontecia de fato na simulação, então a transferência só somava
`frete_transferencia` ao custo sem ganhar nada em fill rate/OTIF. Na janela privada
o efeito foi pior ainda: tirar estoque de um CD doador reduziu a folga que a
simulação real precisava, criando falta nova. O próprio protótipo oficial mostra o
mesmo padrão na janela privada (transferências geradas → score cai para 29,65).

**Decisão**: `solucao.py` mantém `rebalancear_v2()` implementada e documentada (é
código real, testado, não uma tentativa abandonada), mas `main()` não a usa na
resposta final — `resposta_rebalanceamento.csv` sai vazio, como no baseline.

### 4. OTIF — duas hipóteses testadas, sem efeito nesta base (Passo 3)

**Hipótese A** — a escolha de CD usava a mediana cadastral do trânsito, não a
distribuição real (`_probabilidade_no_prazo()` corrige isso, calculando a
probabilidade histórica real por rota). **Hipótese B** — o baseline sempre escolhe
o CD mais rápido, nós escolhíamos o mais barato; testamos inverter o critério.

**Resultado medido: nenhuma das duas mudou um único CD escolhido nas 976 linhas da
janela privada** — nesta base, o CD mais barato já é o mais rápido e mais confiável
quase sempre (é o CD primário). Mantivemos a versão com probabilidade real (mais
correta, mesmo sem efeito medido) e voltamos ao critério "mais barato" (mais
simples, resultado idêntico).

### 5. CTP como passo 4 da cascata (BR-301) — a alavanca que funcionou

A alavanca 4 mostrou que a escolha de CD não era o problema — sobrava pouco espaço
porque quase toda linha já tinha estoque CONFIRMADO suficiente. O espaço real
estava nas ~30 linhas (3% da carteira privada) cuja melhor opção confirmada não
era confiável — exatamente o passo 4 da cascata oficial (produção/CTP), que nem
nosso motor nem o protótipo usavam.

Implementamos `_atp_com_ctp()`: os recebimentos NÃO confirmados de
`inbound_plan.csv` (BR-403) entram como oferta extra, com margem de segurança
sobre a ETA. A margem não foi chutada: `data_dictionary.md` documenta publicamente
que "os não confirmados atrasam de 2 a 6 dias — o atraso real está no gabarito" —
usamos o **pior caso documentado (6 dias)**, e testamos a sensibilidade de 2 a 6
dias: o resultado saiu **idêntico em toda a faixa**.

| | Antes (alavancas 1-3) | Com CTP (alavanca 5) |
|---|---|---|
| OTIF privada | 89,1% | **90,6%** (cruza o baseline, 90,2%) |
| Custo total privada | R$ 391.775,09 | R$ 391.505,02 (levemente menor) |
| Score privada | 56,53 | **58,19** (+1,66) |

Nenhuma dimensão piorou — o primeiro ganho desta solução sem nenhum trade-off
medido.

## Reproduzir (a partir da raiz do repositório)

```bash
python respostas/equipe-2rm/solucao.py --janela public  --saida respostas/equipe-2rm
python respostas/equipe-2rm/solucao.py --janela private --saida respostas/equipe-2rm
python desafio/ferramentas/avaliar_pr.py --equipe equipe-2rm
```

## Bibliotecas usadas

Nenhuma dependência externa — só a biblioteca padrão do Python (`argparse`, `csv`,
`os`, `sys`, `collections`, `datetime`, `math`), reaproveitando `desafio/ferramentas/
comum.py` e partes de `exemplo_prototipo.py` do próprio pacote oficial do desafio.

## Limitações conhecidas / próximos passos

- OTIF na privada passa o baseline (90,6% vs 90,2%) mas ainda está longe da meta
  absoluta de 95%. Continua o maior espaço de ganho automático (12 pontos) — o
  próximo passo provável é revisitar o rebalanceamento (alavanca 3) agora COM o
  CTP integrado ao ATP de sourcing, combinação que ainda não testamos.
- O atendimento parcial (VAR/ECM) nunca foi exercitado nas janelas testadas (fill
  rate já em 100% sem ele) — fica como proteção defensiva, não como alavanca
  comprovada.
