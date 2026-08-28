# Supply Chain para quem nunca trabalhou com Supply Chain

> **Documento auxiliar do desafio.** Escrito para quem vem de dados, IA ou otimização e
> precisa entender o problema o suficiente para construir um protótipo — não para virar
> especialista em logística.
>
> Cada conceito aqui aparece com quatro coisas: **o que é**, **por que existe**, **onde está
> nos dados** e **a armadilha** que derruba o primeiro protótipo.

---

## Parte 1 — O mapa mental em cinco minutos

A cadeia tem três nós e dois fluxos.

```
   FÁBRICA                CENTRO DE DISTRIBUIÇÃO              CLIENTE
   ┌────────┐   abastecimento   ┌────────┐   atendimento   ┌────────┐
   │ PL-01  │ ────────────────▶ │ CD-SP  │ ──────────────▶ │ pedido │
   │ PL-02  │   (planejado)     │ CD-PR  │   (reativo)     │  real  │
   └────────┘                   │ CD-GO  │                 └────────┘
                                │ CD-PE  │
                                └────────┘
                                    ▲ │
                                    │ ▼
                              transferência entre CDs
```

**Fluxo 1 — Abastecimento (empurra).** A fábrica produz e manda para os CDs conforme um
*plano*, feito semanas antes. É lento, é em lote grande, e é decidido com base em **previsão**.

**Fluxo 2 — Atendimento (puxa).** O cliente faz um pedido hoje e quer receber depois de amanhã.
É rápido, fracionado e decidido com base em **realidade**.

**O desafio vive exatamente onde os dois fluxos se encontram.** O plano colocou estoque em
algum lugar semanas atrás; o pedido real chegou agora e não obedeceu ao plano. Sua tarefa é
tomar a melhor decisão possível com o estoque que já está onde está.

> Se você vem de machine learning: pense no plano como o *treino* e no pedido real como o
> *dado de produção* que veio de uma distribuição diferente. Só que aqui você não pode
> retreinar — você tem que atender.

---

## Parte 2 — Os conceitos, um a um

### 2.1 Abastecimento (*replenishment*)

**O que é.** O processo de repor estoque no CD antes que ele acabe. Neste cenário roda toda
segunda-feira: olha-se quanto tem, quanto vai ser vendido, e pede-se a diferença à fábrica.

**Por que existe.** Fábrica produz em campanha (lotes grandes, poucas vezes); cliente compra
em pingado (lotes pequenos, todo dia). O CD é o amortecedor entre os dois ritmos.

**Onde está nos dados.** `inbound_plan.csv` — cada linha é um lote a caminho de um CD.

**Armadilha.** O abastecimento **já aconteceu**. Você não decide o que a fábrica produz no
horizonte do desafio (a produção está congelada, `BR-706`). Você decide o que fazer com o
estoque que existe.

---

### 2.2 Recebimento confirmado e não confirmado

**O que é.** Um lote a caminho tem uma data prevista de chegada (ETA). Se o embarque já saiu
da fábrica com nota fiscal, ele é **confirmado**. Se ainda é só uma linha no plano de produção,
é **não confirmado**.

**Por que existe.** A diferença é jurídica e operacional: o confirmado tem placa de caminhão;
o não confirmado tem intenção.

**Onde está nos dados.** `inbound_plan.csv`, coluna `confirmed` (1 ou 0).

**Armadilha — esta derruba muita gente.** É tentador contar com os não confirmados: eles
inflam o estoque disponível e deixam você prometer datas melhores. Mas no gabarito deste
desafio os **não confirmados atrasam de 2 a 6 dias**. Prometer em cima deles é gastar salário
que ainda não caiu. A regra `BR-403` existe por isso.

São só **12 recebimentos não confirmados** no pacote inteiro, todos com ordem disparada a
partir de 21/09. Poucos — e exatamente por isso fáceis de ignorar até doer.

---

### 2.3 As quatro palavras para "estoque"

| Termo | O que significa | Coluna |
|-------|-----------------|--------|
| **On hand** | O que está fisicamente no CD, agora | `on_hand` |
| **Alocado** | Já tem dono: foi prometido a um pedido | — (você controla) |
| **Reservado** | Separado para um cliente específico antes de ele pedir | `reserved_ka` |
| **Em trânsito** | Saiu da fábrica, ainda não chegou | `in_transit` |

**Disponível ≠ on hand.** Se o CD tem 1.000 unidades e 800 já foram prometidas, você tem 200
para prometer, não 1.000. Essa distinção é o conceito seguinte.

---

### 2.4 ATP — *Available To Promise*

**O que é.** Quanto você ainda pode prometer, considerando o que tem e o que vai chegar
confirmado, descontado tudo que já prometeu a outros.

**Por que existe.** Sem ATP, dois vendedores prometem a mesma caixa para dois clientes.

**A ideia que importa: ATP é escalonado no tempo.** Não é um número, é uma linha do tempo.

Exemplo real deste desafio — **P3 no CD-SP**:

| Data | Evento | Saldo acumulado |
|------|--------|-----------------|
| 28/08 | Estoque no corte | **581** |
| 03/09 | Recebimento `RCP-001585`, confirmado (+11.100) | **11.681** |
| 17/09 | Recebimento `RCP-001624`, confirmado (+1.200) | **12.881** |

E o que **não** entra: `RCP-001645` chega em 28/09 ao CD-PE com 900 unidades de P3, mas a
ordem de reposição só é disparada em 21/09 — produção ainda não firme, `confirmed = 0`. Ele
existe no plano e não pode sustentar promessa alguma (`BR-403`).

Chegam estes pedidos no primeiro dia:

| Linha | Segmento | Qtd | Cabe? | Saldo depois |
|-------|----------|-----|-------|--------------|
| `OL-0125089` | KA | 300 | sim | 281 |
| `OL-0125120` | VAR | 150 | sim | 131 |
| `OL-0125147` | ECM | 30 | sim | 101 |
| `OL-0125160` | ECM | 66 | sim | 35 |
| `OL-0125174` | KA | 300 | **não** — faltam 265 | — |

O quinto pedido é de um Key Account e o cliente pediu para **03/09**. O que fazer:

| Opção | Embarque | Entrega | Atraso | Tarifa do frete |
|-------|----------|---------|--------|-----------------|
| Esperar o recebimento no CD-SP | 03/09 | **08/09** | 5 dias | R$ 0,68/kg |
| Atender do CD-GO (2.360 un em estoque) | 01/09 | **04/09** | 1 dia | R$ 0,80/kg (+18%) |
| Atender do CD-PR (2.195 un) | 01/09 | **04/09** | 1 dia | R$ 0,80/kg (+18%) |
| Atender do CD-PE (4.135 un) | 01/09 | **10/09** | 7 dias | R$ 1,17/kg (+72%) |

Repare em três coisas:

1. **08/09 e não 07/09** — 07 de setembro é feriado nacional. Calendário importa.
2. **Pagar 18% a mais de frete economiza 4 dias de atraso** em um cliente com multa de 3%.
3. **O CD-PE tem mais estoque e é a pior opção.** "Onde tem mais" não é "de onde atender".

Isso, em uma linha de pedido. Você tem 919 delas na janela pública.

**Onde está nos dados.** Você monta o ATP com `inventory_opening.csv` (a posição de abertura da
janela que está resolvendo) mais `inbound_plan.csv` filtrado por `confirmed = 1`.

> Atenção: **não** use `inventory_snapshot.csv` da data de corte para a janela privada. Entre o
> corte e 14/09 os recebimentos chegam e os pedidos da janela pública já foram atendidos.
> `inventory_opening.csv` traz a posição correta de cada janela.

**Duas armadilhas, e a segunda é pior.**

A primeira: calcular ATP como número único ("tenho 581") em vez de linha do tempo ("tenho 581
hoje e 11.681 a partir de 03/09"). Quem faz isso rejeita pedidos que eram atendíveis dias
depois.

A segunda, mais sutil: aceitar um pedido só porque o **saldo corrente** cobre a quantidade. Não
basta. O saldo precisa continuar cobrindo em **todas as datas seguintes** — senão você promete
duas vezes o mesmo estoque, e a segunda promessa encontra o armazém vazio. A conta certa é:

```
disponível(t) = mínimo, para todo u >= t, do saldo acumulado em u
```

Quem pula esse mínimo à frente super-compromete e reprova por fill rate. Está implementado em
`exemplo_prototipo.py`, no método `primeira_data`.

---

### 2.5 CTP — *Capable To Promise*

**O que é.** O passo seguinte ao ATP: se não tenho o produto disponível, **consigo tê-lo** —
produzindo, transferindo de outro CD ou usando um recebimento ainda não confirmado?

**Por que existe.** ATP responde "tenho?". CTP responde "consigo ter a tempo?". A segunda
pergunta é mais cara de responder e mais cara de errar.

**Neste desafio.** ATP é passo 1 e 2 da cascata `BR-301`; CTP é passo 4. No meio há a
transferência entre CDs, que é a alavanca que você controla.

---

### 2.6 Lead time: a anatomia do prazo

Prazo não é um número, é uma soma de etapas:

```
pedido entra          cutoff              separação           trânsito         entrega
   14h32   ─────────▶  18h00  ─────────▶   dia útil  ─────▶  2 a 10 dias ────▶  cliente
                        │                  seguinte           úteis
                        │
              depois disso, conta como
              se tivesse chegado amanhã
```

| Etapa | Regra | Onde |
|-------|-------|------|
| **Cutoff** | Pedido depois das 18h vira pedido de amanhã | `BR-101` · `cutoff_local_time` |
| **Calendário** | Só dia útil da região; sábado só em CD-SP e CD-PR | `BR-102` · `holidays_calendar.csv` |
| **Trânsito** | Depende da rota CD→região | `lanes.csv`, `transit_days` |

**Armadilha número um do desafio:** somar dias corridos em vez de dias úteis. Um trânsito de
5 dias úteis saindo numa quinta-feira chega na quinta seguinte, não no domingo. E se pegar
feriado, mais um dia. Use as funções prontas em `desafio/ferramentas/comum.py`:
`somar_dias_uteis`, `liberacao`, `data_minima_viavel`.

---

### 2.7 Order promising: as três datas

Todo pedido tem três datas, e confundi-las é fatal:

| Data | Quem define | Coluna |
|------|-------------|--------|
| **Solicitada** | O cliente, quando pede | `requested_date` |
| **Prometida** | Você, ao aceitar o pedido | `promised_date` (sua resposta) |
| **Real** | A operação, quando entrega | conhecida só na avaliação |

E daí saem as duas métricas que o desafio mede — e **elas não são a mesma coisa**:

| Métrica | Compara | Mede |
|---------|---------|------|
| **Promise Reliability** | real ≤ **prometida** | Se você cumpre a sua palavra |
| **OTIF** | real ≤ **solicitada** | Se o cliente recebeu quando queria |

**Por que isso importa tanto.** Se OTIF fosse medido contra a data prometida, a estratégia
vencedora seria prometer tudo para daqui a três meses e cumprir 100%. Medindo contra a data
que o cliente pediu, esse atalho morre: prometer tarde melhora a Promise Reliability e não
salva o OTIF. Para subir o OTIF é preciso realmente colocar o produto no lugar certo.

---

### 2.8 Sourcing e CD primário

**O que é.** Decidir de qual CD sai cada linha do pedido.

**CD primário** é o CD "natural" da região do cliente — o mais próximo, o mais barato, o mais
rápido. Atender de outro CD é possível, mas custa mais frete por quilo e normalmente mais
prazo.

**Onde está nos dados.** `lanes.csv`: cada linha é uma rota CD→região, com `transit_days`,
`rate_per_kg` e a flag `is_primary`.

**Armadilha.** Achar que atender de outro CD é de graça. Neste desafio a tarifa por quilo sobe
**18% para cada dia útil de trânsito a mais** que a rota primária. CD-SP→Sudeste custa
R$ 0,68/kg; CD-PE→Sudeste custa R$ 1,17/kg pelo mesmo destino.

---

### 2.9 Transferência entre CDs (rebalanceamento)

**O que é.** Mover estoque de um CD que tem sobrando para um que está faltando.

**Diferença para abastecimento:** abastecimento vem da fábrica e cria produto novo na rede;
transferência só muda produto de lugar. O total da rede não aumenta.

**Por que importa aqui.** No corte, o **CD-SP está em ruptura nos cinco produtos** (1 a 6 dias
de cobertura) enquanto CD-GO e CD-PE têm 12 a 18 dias. O Sudeste é 45% da demanda e concentra
os Key Accounts. O estoque está no lugar errado.

**Onde está nos dados.** `transfer_lanes.csv` — distância, dias de trânsito, custo fixo e por
quilômetro, paletes por caminhão.

**Armadilhas.** Transferência leva de 2 a 6 dias (`BR-307`: só vale se a data resultante ainda
respeitar o SLA); tem lote mínimo de 1 palete completo (`BR-703`); e não pode deixar o CD de
origem abaixo de 10 dias de cobertura (`BR-704`).

---

### 2.10 Palete, camada e ocupação

**Palete** é a unidade física de movimentação: um estrado com produto empilhado. Aqui todos os
paletes fecham em torno de **1,8 m³**; o que muda é quantas unidades cabem, conforme a
densidade do produto — 700 unidades de P1, 300 de P3.

**Camada** é 1/4 de palete. Varejo regional compra em camada; Key Account e distribuidor
compram em palete fechado (`BR-104`).

**Ocupação** é o quanto do caminhão foi realmente usado, em peso **ou** em volume — o que
estourar primeiro. Um caminhão de distribuição leva 12 paletes, 8.000 kg ou 24 m³.

**Por que isso vale pontos.** O frete fracionado tem **mínimo de R$ 180 por embarque**
(`BR-602`). Mandar oito clientes num veículo paga um mínimo em vez de oito. O baseline opera
com **4,7% de ocupação** — ele manda praticamente um veículo por cliente por dia.

---

### 2.11 Os componentes do frete

| Componente | O que é | Fórmula |
|------------|---------|---------|
| **Frete-peso** | O transporte em si | `peso × tarifa da rota` |
| **Frete mínimo** | O piso que a transportadora cobra por embarque | R$ 180 |
| **Ad valorem** | Seguro sobre o valor transportado | 0,35% do valor |
| **GRIS** | Gerenciamento de risco (rastreamento, escolta) | 0,12% do valor |
| **FTL** | Carga fechada, usada em transferência: paga o caminhão inteiro | R$ 380 + R$ 4,20/km |

**Por que ad valorem importa.** Ele não olha o peso, olha o valor. P3 custa R$ 180 a unidade:
um palete de P3 vale R$ 54.000 e paga R$ 254 só de seguro, enquanto pesa 150 kg. Para P3, o
seguro pesa mais que o frete. É por isso que produto premium tem regra própria (`BR-305`,
escolta acima de R$ 150.000).

---

### 2.12 As métricas de serviço

| Métrica | Pergunta | Fórmula |
|---------|----------|---------|
| **On Time** | Chegou na data? | entregas no prazo / total |
| **In Full** | Chegou completo? | linhas completas / total |
| **OTIF** | Chegou na data **e** completo? | as duas coisas juntas |
| **Fill Rate** | Que fração do pedido foi atendida? | valor atendido / valor pedido |

**OTIF é o mais duro** porque é uma conjunção: 95% de On Time e 95% de In Full dão no máximo
95% de OTIF, e na prática menos.

**Armadilha.** Otimizar Fill Rate atendendo só os pedidos fáceis. Por isso existe o piso de
`BR-205`: **nenhum segmento pode ficar abaixo de 85% de fill rate**. Recusar a cauda longa
para proteger os grandes reprova a resposta inteira.

---

### 2.13 Backorder e ruptura

**Ruptura** (*stockout*) é o CD ficar sem produto. **Backorder** é o pedido que fica esperando
o produto chegar em vez de ser cancelado.

**Neste desafio.** Você pode comprometer `qty_committed = 0` para uma linha que não consegue
atender. É honesto — melhor que prometer uma data que não vai cumprir. Mas cuidado: fazer isso
demais derruba o fill rate e reprova pelo `BR-205`.

---

### 2.14 Forecast e consumo de forecast

**Forecast** é a previsão de quanto vai vender. **Consumo de forecast** é o mecanismo que
abate o pedido real da previsão da semana.

```
saldo = max(0, forecast − pedidos reais acumulados)
```

| Situação | Leitura |
|----------|---------|
| Consumo < 80% do forecast | Vendeu menos que o previsto — estoque vai sobrar |
| Consumo entre 80% e 110% | Dentro da tolerância |
| Consumo > 110% | Vendeu mais que o previsto — **replanejar** (`BR-701`) |

**Onde está nos dados.** `demand_plan.csv`, colunas `forecast_qty` e `consumed_qty`.

**Para quem vem de ML:** a diferença entre as duas colunas é o seu erro de previsão histórico,
já calculado. É de graça e a maioria das equipes esquece de olhar.

---

### 2.15 Segmentação de cliente

Nem todo cliente vale o mesmo, e o desafio deixa isso explícito:

| Segmento | Quem é | SLA | Particularidade |
|----------|--------|-----|-----------------|
| **KA** | Grandes redes | 48h no SE/S | Multa de 3% se OTIF mensal < 95%; janela agendada |
| **DIS** | Distribuidores | 96h | Compra em palete fechado |
| **VAR** | Varejo regional | 72h | Aceita parcial acima de 80% do valor |
| **ECM** | E-commerce | 120h | Aceita qualquer fração |

**Janela agendada (KA).** Grandes redes agendam a descarga. Chegar fora da janela é
**recusa na doca** — o caminhão volta e a reentrega custa 60% do frete original.

---

## Parte 3 — Do conceito ao código, em cinco passos

Esta é a receita mínima. Ela está implementada e comentada em
`desafio/ferramentas/exemplo_prototipo.py`.

### Passo 1 — Aprenda o trânsito real do histórico

O `transit_days` do cadastro é a **mediana**. Metade das viagens demora mais. Calcule os
quantis por rota a partir de `historical_deliveries.csv`.

### Passo 2 — Monte o ATP escalonado no tempo

Uma linha do tempo por CD × SKU: estoque no corte, mais recebimentos confirmados, menos o que
você já prometeu.

### Passo 3 — Para cada linha, gere as opções e escolha

Para cada CD com rota até a região do cliente: quando o produto fica disponível, quando
chegaria, quanto custa o frete. Entre as opções que chegam na data pedida, escolha a mais
barata.

### Passo 4 — Agrupe os embarques

Linhas do mesmo CD, mesma região e **mesmo dia** viajam juntas e dividem um frete. Até 8
pontos de entrega (`BR-506`). Como todas já estão disponíveis naquele dia, ninguém espera —
economia sem atraso.

### Passo 5 — Prometa a partir da data do embarque, não da linha

**Este é o erro que derruba o primeiro protótipo de quase todo mundo.** Se você consolida, o
grupo só parte quando a última linha dele fica pronta. Quem prometeu com base na própria linha
já quebrou a promessa antes de embarcar. Calcule a data de partida do grupo primeiro, prometa
depois.

### O que esse protótipo entrega

| Métrica | Baseline | Protótipo de exemplo |
|---------|----------|----------------------|
| Custo total | R$ 491.736 | **R$ 385.435** (−21,6%) |
| Frete de distribuição | R$ 305.083 | **R$ 252.767** |
| Ocupação do veículo | 4,7% | **16,9%** |
| Aderência ao CD primário | 90,2% | **97,5%** |
| Promise Reliability | 94,8% | 94,6% |
| OTIF | 93,5% | 92,3% |
| **Score automático** | 0 (é a referência) | **41,62 / 90** |

Ele ganha **21,6% de custo** e os 20 pontos da trilha preditiva, empatando em serviço com o
baseline. O que ele **não** faz: rebalancear a rede de verdade, diferenciar buffer por cliente
além do básico, nem recuperar o OTIF de Key Account — que segue em 80,7% e continua pagando a
multa de R$ 95.562. É exatamente aí que começa o seu trabalho.

---

## Parte 4 — As oito armadilhas

Em ordem de frequência com que aparecem:

| # | Armadilha | Consequência |
|---|-----------|--------------|
| 1 | Somar dias corridos em vez de dias úteis | Datas erradas; reprovação por `BR-102` |
| 2 | Esquecer o cutoff das 18h | Um dia a menos que você não tem |
| 3 | Contar recebimento não confirmado no ATP | Promessa quebrada quando ele atrasa |
| 4 | Tratar ATP como número em vez de linha do tempo | Rejeita pedidos que eram atendíveis |
| 5 | Prometer a partir da linha e consolidar depois | Promessa quebrada antes de embarcar |
| 6 | Fracionar linha de KA ou DIS | Reprovação por `BR-501` |
| 7 | Recusar pedidos difíceis para inflar métricas | Reprovação por `BR-205` |
| 8 | Usar coluna de resultado como feature | Modelo que não sobrevive à avaliação |

---

## Parte 5 — Glossário rápido

| Português | Inglês | Uma linha |
|-----------|--------|-----------|
| Abastecimento / Reposição | Replenishment | Repor estoque no CD |
| Disponível para promessa | ATP — Available to Promise | O que ainda posso prometer |
| Capaz de prometer | CTP — Capable to Promise | O que consigo ter a tempo |
| Centro de distribuição | DC — Distribution Center | Armazém que atende clientes |
| Cobertura | Days of Supply | Estoque dividido pela demanda diária |
| Data prometida | Promised / Commit date | O compromisso que você assume |
| Data solicitada | Requested date | O que o cliente pediu |
| Estoque de segurança | Safety stock | Colchão contra variação |
| Falta / Ruptura | Stockout | Acabou o produto |
| Frete fracionado | LTL — Less than Truckload | Carga compartilhada |
| Carga fechada | FTL — Full Truckload | Caminhão inteiro para um destino |
| Janela de entrega | Delivery window | Horário agendado de descarga |
| Lote mínimo | MOQ — Minimum Order Quantity | Menor quantidade comprável |
| Nível de serviço | Service level | Quanto se atende do que se pede |
| Pedido pendente | Backorder | Pedido esperando produto |
| Prazo de entrega | Lead time | Tempo do pedido à entrega |
| Previsão de demanda | Forecast | Quanto se espera vender |
| Rota | Lane | Par origem-destino |
| Transferência | Stock transfer | Mover estoque entre CDs |

---

## Onde continuar

| Documento | Para quê |
|-----------|----------|
| `desafio/README.md` | Rodar o baseline e enviar em 30 minutos |
| `docs/desafio/01-business-scope.md` | As 40 regras de negócio completas |
| `desafio/dados/v1.0.0/data_dictionary.md` | Toda coluna, tipo e unidade |
| `desafio/ferramentas/exemplo_prototipo.py` | A receita dos 5 passos, em código comentado |
| `desafio/ferramentas/comum.py` | Calendário, custos e ATP prontos para usar |

---

*Documento produzido pelo squad `desafio-supply-chain-squad` · @scm-expert (Marta).*
