# Desafio Supply Chain — Promessa de Data e Rebalanceamento de Rede

> **Comece por aqui.** Em 30 minutos você tem os dados, roda o baseline, vê o seu
> primeiro score e sabe o que atacar. Se levar mais que isso, o problema é nosso —
> avise no canal do desafio.

---

## O problema em um parágrafo

Uma rede com **2 plantas, 4 centros de distribuição e 5 produtos** atende quatro tipos de
cliente com exigências diferentes. O plano de demanda já rodou e o estoque já está posicionado.
Chega um pedido: **de qual CD você atende, que data promete ao cliente e o que embarca junto?**
Atender rápido custa frete. Atender barato custa prazo. E o cliente que representa 41% da
receita tem multa contratual de 3% se o OTIF dele cair abaixo de 95%.

As regras completas estão em [`docs/desafio/01-business-scope.md`](../docs/desafio/01-business-scope.md)
— 40 regras de negócio numeradas, `BR-101` a `BR-509`.

> **Nunca trabalhou com supply chain?** Comece por
> [`docs/desafio/conceitos-supply-chain.md`](../docs/desafio/conceitos-supply-chain.md).
> Ele explica ATP, CTP, abastecimento, lead time e frete com exemplos numéricos deste
> pacote de dados, e termina com a receita de 5 passos do protótipo. Vinte minutos de
> leitura que economizam um dia de confusão.

---

## Primeiros 30 minutos

Você precisa de **Python 3.10+** e nada mais. Sem pandas, sem solver, sem instalar nada.

O pacote `.zip` traz os dados **e as ferramentas** — descompacte e os comandos abaixo funcionam
de dentro da pasta. Se você clonou o repositório, já está tudo no lugar.

```bash
# 1. Rode o baseline na janela pública (30 segundos)
python desafio/ferramentas/baseline_atual.py --janela public

# 2. Avalie o baseline e veja o placar de referência
python desafio/ferramentas/avaliar.py --resposta desafio/respostas/baseline/public

# 3. Rode o protótipo de exemplo e compare
python desafio/ferramentas/exemplo_prototipo.py --janela public
python desafio/ferramentas/avaliar.py --resposta desafio/respostas/exemplo/public

# 4. Copie um dos dois, mexa, e avalie de novo
cp -r desafio/respostas/exemplo/public minha_solucao/
python desafio/ferramentas/avaliar.py --resposta minha_solucao
```

O que a política vigente entrega hoje nas duas janelas:

| Métrica | Pública | Privada | Meta |
|---------|---------|---------|------|
| Promise Reliability | 94,8% | 94,7% | ≥ 96% |
| **OTIF** (contra a data que o cliente pediu) | **93,5%** | **91,2%** | ≥ 95% |
| **OTIF Key Account** | **86,7%** | **86,6%** | ≥ 98% |
| In Full | 100,0% | 100,0% | ≥ 97% |
| Fill Rate (valor) | 100,0% | 100,0% | ≥ 96% |
| Promise Tightness | 2,00 d | 2,00 d | ≤ 1,5 |
| Aderência ao CD primário | 90,2% | 86,0% | ≥ 85% |
| **Ocupação média do veículo** | **4,7%** | **4,6%** | ≥ 80% |
| Custo logístico / receita | 6,3% | 5,4% | ≤ 8,5% |
| **Custo total** | **R$ 491.736** | **R$ 463.201** | — |

E o protótipo de exemplo, que vem pronto no repositório:

| Métrica | Baseline (pública) | Protótipo (pública) |
|---------|--------------------|---------------------|
| Custo total | R$ 491.736 | **R$ 385.435** (−21,6%) |
| Ocupação do veículo | 4,7% | **16,9%** |
| OTIF | 93,5% | 92,3% |
| **Score automático** | 0 (é a referência) | **41,62 / 90** |

Duas linhas em negrito valem dinheiro imediato: o OTIF de Key Account em 86,7% aciona
**R$ 95.562 de multa** na janela pública, e a ocupação de 4,7% significa que a operação está
pagando frete mínimo em quase todo embarque. Comece por aí.

---

## O score local é uma estimativa — e isso é de propósito

O trânsito realizado das janelas de teste fica **lacrado com os organizadores**. Se estivesse
no repositório, bastaria abrir o arquivo para prometer datas perfeitas e o desafio acabaria ali.

Quando você roda o avaliador, ele entra em **modo TREINO**: sorteia o trânsito de cada rota a
partir da distribuição observada no histórico, com semente fixa. Consequências:

- Roda sempre igual — dá para comparar duas versões da sua solução com confiança.
- É uma amostra plausível do mundo, não o mundo. Espere alguns pontos de diferença.
- Os **gates são os mesmos** (BR-406, BR-501, BR-205 e companhia). Se reprovou no treino,
  reprova no oficial.

O avaliador diz em que modo rodou, na primeira linha:

```
RESPOSTA VÁLIDA — janela public · modo TREINO
```

Otimize a decisão, não o sorteio. Uma solução que só ganha no modo treino é uma solução que
não ganha.

---

## O que você entrega

### `resposta_promessa.csv` — obrigatório

Uma linha para **cada** `order_line_id` da janela. Faltou uma, a resposta é reprovada.

```csv
order_line_id,dc_id,promised_date,qty_committed,shipment_group
OL-0125001,CD-SP,2026-09-04,1400,SHP-00012
```

| Coluna | O que é |
|--------|---------|
| `dc_id` | De qual CD você vai atender |
| `promised_date` | A data que você promete ao cliente — é o seu compromisso |
| `qty_committed` | Quanto você se compromete a entregar (0 = não atende) |
| `shipment_group` | **Linhas com o mesmo grupo viajam juntas e dividem um frete** |

O `shipment_group` é a sua alavanca de composição de carga. Um grupo só embarca quando **todas**
as suas linhas têm estoque: consolidar corta frete e atrasa quem já estava pronto.

### `resposta_rebalanceamento.csv` — opcional, mas é onde está o jogo

```csv
transfer_id,origin,dest,sku,qty_pallets,ship_date
TRF-00001,CD-PE,CD-SP,P3,12,2026-09-01
```

### `resposta_previsao.csv` — opcional, vale 20 pontos

A trilha preditiva: seus quantis de lead time por rota e dia de embarque.

```csv
dc_id,region,ship_date,transit_q50,transit_q90
CD-SP,SE,2026-09-01,2,4
```

Sem este arquivo, a dimensão preditiva pontua zero. Os outros 70 pontos automáticos continuam
disponíveis.

---

## Como você é avaliado

Rubrica publicada, 100 pontos:

| Dimensão | Peso | Composição |
|----------|------|------------|
| Nível de serviço | 45 | Promise Reliability 25 · OTIF 12 · Fill Rate 8 |
| Eficiência de custo | 25 | Custo total contra o baseline |
| Qualidade preditiva | 20 | Pinball loss do lead time (q50 e q90) |
| Qualidade da entrega | 10 | **Júri humano** — código, reprodutibilidade, defesa da abordagem |

O avaliador calcula os 90 pontos automáticos. O baseline pontua ~0 por construção: **todo ponto
é ganho medido contra ele**.

### Promise Reliability e OTIF medem coisas diferentes

Esta é a distinção mais importante do desafio:

- **Promise Reliability** = entregou até a data que **você prometeu**. Mede a sua palavra.
- **OTIF** = entregou até a data que **o cliente pediu** (`requested_date`). Mede o que ele sente.

Empurrar todas as promessas para a frente melhora a primeira e **não salva a segunda**. Não
existe atalho: para subir o OTIF você precisa realmente colocar o produto no lugar certo, na
hora certa.

### Gates — reprovam a resposta inteira

| Gate | Regra |
|------|-------|
| Cobertura | Toda linha da janela precisa de uma promessa |
| `BR-406` | Data prometida não pode ser anterior ao lead time mínimo viável |
| `BR-102` | Data prometida precisa cair em dia útil da região |
| `BR-501/502` | KA e DIS não aceitam linha parcial: comprometa 0 ou a quantidade inteira |
| `BR-506` | Um embarque atende no máximo 8 pontos de entrega, em uma única região |
| `BR-704` | Transferência não pode tirar estoque que o CD de origem não tem |
| `BR-205` | Nenhum segmento pode ficar com fill rate abaixo de 85% |
| Fill global | Fill rate global mínimo de 70% |

O último par existe para impedir a saída fácil: **recusar os pedidos difíceis para inflar as
métricas dos fáceis**.

---

## Os dados

Tudo em `desafio/dados/v1.0.0/`. Dicionário completo, coluna por coluna, em
[`data_dictionary.md`](dados/v1.0.0/data_dictionary.md).

| Arquivo | O que tem |
|---------|-----------|
| `orders_history.csv` | 12 meses de pedidos reais — sua base de treino |
| `historical_deliveries.csv` | O que aconteceu com cada linha: lead time realizado, atrasos |
| `inventory_snapshot.csv` | Estoque diário por CD e SKU; a data de corte é o seu estado inicial |
| `inbound_plan.csv` | Recebimentos programados, confirmados e não confirmados |
| `demand_plan.csv` | O plano de demanda contra o consumo real |
| `orders_test_public.csv` | Os pedidos que você precisa promissar (leaderboard) |
| `orders_test_private.csv` | Os pedidos do ranking final |
| `sku_master` · `customer_master` · `dc_master` · `plant_master` | Cadastros |
| `lanes` · `transfer_lanes` · `vehicles` · `holidays_calendar` | Rede, custos e calendário |

Confira a integridade depois de baixar:

```bash
python desafio/ferramentas/conferir_dados.py
```

`sha256sum` não existe no PowerShell nem no cmd do Windows — por isso o verificador é em
Python, que você já precisa ter. Em macOS, Linux ou Git Bash, `sha256sum -c CHECKSUMS.txt`
dentro de `desafio/dados/v1.0.0/` faz o mesmo.

### Split temporal — não embaralhe

```
|<------ TREINO: 2025-09-01 a 2026-08-28 ------>|  PÚBLICO  |  PRIVADO  |
                                                  08-31→09-11  09-14→09-25
```

A **leakage list** está no dicionário de dados. Resumo: nada que só existe depois da entrega
pode virar feature. `actual_delivery_date`, `transit_days_actual` e `dc_id` do histórico
servem para **treinar**, nunca para prever o próprio futuro.

---

## Onde estão os pontos

Quatro frentes, em ordem de retorno sobre esforço:

**1. Matar a multa de KA (R$ 95.562).** O OTIF de Key Account está em 86,7% e a multa dispara
abaixo de 95%. São 11% dos pedidos e 41% da receita, com janela de entrega agendada. Priorizar
estoque e escolher o CD certo para eles muda o custo total em quase 20%.

**2. Consolidar carga (ocupação 4,7%).** O baseline manda um embarque por cliente por dia e paga
frete mínimo de R$ 180 em quase todos. O protótipo de exemplo agrupa só o que já está disponível
no mesmo dia e corta 17% do frete sem atrasar ninguém. Ir além disso começa a custar OTIF —
achar o ponto de equilíbrio é o exercício.

**3. Rebalancear a rede.** No corte, o **CD-SP está em ruptura nos 5 SKUs** (1 a 6 dias de
cobertura) enquanto CD-GO e CD-PE têm 12 a 18 dias. O Sudeste é 45% da demanda. O estoque está
no lugar errado e transferir leva de 3 a 5 dias — decidir cedo vale mais que decidir certo.

**4. Prever o lead time.** O trânsito real varia por rota: 9% de chance de atraso no Sudeste,
26% no Norte. Um buffer fixo de 2 dias é caro onde não precisa e insuficiente onde precisa.

---

## Regras de participação

| Item | Regra |
|------|-------|
| Equipes | Até 3 pessoas, com pelo menos dois perfis distintos (SCM, IA, otimização) |
| Respostas | Até 5 por dia; cada equipe escolhe 2 para o ranking final |
| Ranking final | 100% na janela privada. A pública serve só para feedback |
| Bibliotecas | Livre, desde que open source e declarado no README da sua solução |
| Uso de IA | Permitido e esperado. Declare o que foi gerado e por qual ferramenta |
| Dados externos | Não permitidos — o cenário é sintético, não há fonte externa válida |
| Erratas | Correção de dados gera nova versão e aviso no portal |

---

## Estrutura do repositório

```
desafio/
├── README.md                    você está aqui
├── dados/v1.0.0/                o pacote — 17 CSVs + dicionário + checksums
├── ferramentas/
│   ├── comum.py                 leitura dos dados, calendário, custos
│   ├── baseline_atual.py       o baseline de referência
│   ├── exemplo_prototipo.py     protótipo comentado — leia antes de escrever o seu
│   └── avaliar.py               o avaliador oficial
├── submissoes/baseline/         respostas do baseline, prontas
├── gerador/                     como os dados foram gerados (seed 42)
└── privado/                     gabarito — não distribuído
```

O gerador está publicado de propósito: você pode ler exatamente como o mundo foi construído.
O que você **não** tem é o gabarito — o trânsito realizado e o atraso dos recebimentos não
confirmados das janelas de teste.

---

## Dúvidas

Canal do desafio. SLA de resposta: 1 dia útil. Se encontrar inconsistência nos dados ou no
enunciado, reporte — erratas são publicadas com nova versão do pacote.
