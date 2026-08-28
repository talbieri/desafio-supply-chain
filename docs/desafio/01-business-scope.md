# Escopo de Negócio e Regras — Desafio Supply Chain

> **Documento:** `01-business-scope.md` · **Versão:** 1.0.0 · **Data:** 2026-08-28
> **Autor:** @scm-expert (Marta) · **Squad:** `desafio-supply-chain-squad`
> **Task:** `scm-define-business-scope.md` · **Status:** Draft para validação

---

## 1. Objetivo do Desafio

Simular a operação de **order promising e rebalanceamento** de uma cadeia com plantas produtoras e
centros de distribuição, para 5 produtos, e responder à pergunta que a operação enfrenta todo dia:

> Chegou um pedido. **De qual CD eu atendo, que data eu prometo e o que eu embarco agora** — sabendo
> que atender rápido custa frete, atender barato custa prazo, e que nem todo cliente pode esperar?

O plano de demanda e a política de estoque **já rodaram**: o estoque está posicionado na rede. O
desafio começa no momento em que o pedido real entra e diverge do que foi planejado.

### O que se exercita

| Dimensão | Pergunta que o participante precisa responder |
|----------|-----------------------------------------------|
| Sourcing | Qual CD atende cada linha do pedido? |
| Promessa de data | Que data prometer ao cliente, com que confiança? |
| Custo | Vale pagar frete de um CD distante para não quebrar o SLA? |
| Serviço diferenciado | Como proteger o Key Account sem sacrificar o resto da carteira? |
| Composição de carga | Embarca completo, parcial ou segura para consolidar? |
| Replanejamento | Quando o pedido real fura o plano, o que se transfere entre CDs? |

---

## 2. A Rede

### 2.1 Plantas produtoras

| Planta | Localização | Produtos | Capacidade | Frequência de produção |
|--------|-------------|----------|------------|------------------------|
| **PL-01** | Sumaré / SP | P1, P2, P3, P4 | 348.000 un/mês | Campanha semanal por SKU |
| **PL-02** | Feira de Santana / BA | P1, P2, P5 | 162.000 un/mês | Campanha quinzenal por SKU |

> P3 é produzido **exclusivamente** em PL-01; P5 **exclusivamente** em PL-02. Essa assimetria é
> deliberada: ela força decisões de transferência entre regiões.

### 2.2 Centros de distribuição

| CD | Localização | Região primária | Capacidade | Regiões secundárias |
|----|-------------|-----------------|------------|---------------------|
| **CD-SP** | Cajamar / SP | Sudeste | 12.000 pos. palete | Sul, Centro-Oeste |
| **CD-PR** | Curitiba / PR | Sul | 5.000 pos. palete | Sudeste |
| **CD-PE** | Recife / PE | Nordeste | 6.000 pos. palete | Norte |
| **CD-GO** | Goiânia / GO | Centro-Oeste | 4.000 pos. palete | Norte, Sudeste |

**Capacidade de expedição por dia útil** — o gargalo que aparece quando a demanda concentra:

| CD | CD-SP | CD-PR | CD-GO | CD-PE |
|----|-------|-------|-------|-------|
| Paletes expedidos / dia | 900 | 380 | 300 | 440 |

### 2.3 Lead time de suprimento (dias corridos)

**Planta → CD (transferência)**

| Origem | CD-SP | CD-PR | CD-GO | CD-PE |
|--------|-------|-------|-------|-------|
| PL-01 (SP) | 1 | 2 | 3 | 5 |
| PL-02 (BA) | 4 | 6 | 4 | 1 |

**CD → CD (rebalanceamento)**

| | CD-SP | CD-PR | CD-GO | CD-PE |
|--|-------|-------|-------|-------|
| **CD-SP** | — | 2 | 3 | 5 |
| **CD-PR** | 2 | — | 4 | 6 |
| **CD-GO** | 3 | 4 | — | 4 |
| **CD-PE** | 5 | 6 | 4 | — |

### 2.4 Lead time de distribuição, CD → região (dias úteis)

| CD | SE | S | CO | NE | N |
|----|----|---|----|----|---|
| **CD-SP** | 2 | 3 | 4 | 6 | 8 |
| **CD-PR** | 3 | 1 | 5 | 8 | 10 |
| **CD-PE** | 6 | 8 | 5 | 2 | 4 |
| **CD-GO** | 3 | 5 | 1 | 5 | 3 |

---

## 3. Os 5 Produtos

| SKU | Descrição | Classe ABC | Demanda mês (un) | Peso un | Volume un | Valor un | Un/palete | Shelf life |
|-----|-----------|-----------|------------------|---------|-----------|----------|-----------|------------|
| **P1** | Linha básica, alto giro | A | 240.000 | 0,80 kg | 0,0025 m³ | R$ 12 | 700 | 365 d |
| **P2** | Linha padrão | A | 150.000 | 1,20 kg | 0,0040 m³ | R$ 28 | 450 | 365 d |
| **P3** | Linha premium | B | 40.000 | 0,50 kg | 0,0060 m³ | R$ 180 | 300 | 540 d |
| **P4** | Linha sazonal | B | 60.000 (pico 180.000 em nov–dez) | 1,50 kg | 0,0060 m³ | R$ 45 | 300 | 365 d |
| **P5** | Lançamento / promocional | C | 25.000 (alta incerteza) | 0,90 kg | 0,0035 m³ | R$ 60 | 500 | **90 d** |

> Todos os paletes fecham em torno de 1,8 m³ — a diferença de unidades por palete vem da
> densidade de cada produto, não de uma convenção arbitrária.

### Por que cada produto existe no desafio

| SKU | Tensão que ele introduz |
|-----|-------------------------|
| P1 | Volume domina o frete; erro de posicionamento é caro em cubagem, não em valor |
| P2 | O "caso médio" — referência de comparação |
| P3 | Alto valor → **ad valorem** pesa mais que o frete-peso; sourcing distante custa caro em seguro |
| P4 | Sazonalidade → o plano de estoque envelhece rápido; o pico quebra a capacidade do CD |
| P5 | Shelf life de 90 dias + demanda incerta → posicionar errado vira **perda**, não só custo |

### Distribuição regional da demanda

| Região | % da demanda | Observação |
|--------|--------------|------------|
| Sudeste | 45% | Concentra os Key Accounts |
| Sul | 20% | Alta densidade de varejo regional |
| Nordeste | 20% | Crescimento acima da média; atendido por PL-02/CD-PE |
| Centro-Oeste | 10% | Distribuidores de grande porte |
| Norte | 5% | Lead time longo, pedidos maiores e menos frequentes |

---

## 4. Tipos de Cliente e Nível de Serviço

| Tipo | Descrição | % receita | % pedidos | SLA de entrega | Pedido completo | Penalidade contratual |
|------|-----------|-----------|-----------|----------------|-----------------|-----------------------|
| **KA** — Key Account | Grandes redes nacionais | 40,6% | 10,8% | 48h SE/S · 72h CO/NE/N · **janela agendada** | **Obrigatório** (≥ 98% in-full) | 3% do valor do pedido se OTIF mensal < 95% |
| **DIS** — Distribuidor / Atacado | Compra volume, recebe palete fechado | 30,5% | 14,2% | 96h | Múltiplo de palete | Não |
| **VAR** — Varejo regional | Lojas médias, pedido misto | 20,3% | 35,4% | 72h | Parcial aceito se ≥ 80% do valor | Não |
| **ECM** — E-commerce / pequeno varejo | Pedido fracionado, alta frequência | 8,5% | 39,5% | 120h | Parcial livre | Não |

> Percentuais medidos sobre os 12 meses de histórico do pacote de dados v1.0.0, não estimados.

> **A assimetria é o ponto.** KA é 11% dos pedidos e 41% da receita, com a maior exigência e a única
> multa. Uma solução que trata todos os pedidos igual perde dinheiro; uma que só protege KA quebra
> o serviço da cauda longa e destrói o fill rate agregado.

### Janela de entrega agendada (KA)

Key Accounts operam com agendamento em CD próprio. Consequências:

- Entrega fora da janela é **recusada** — conta como falha de OTIF e gera custo de reentrega.
- A janela é confirmada no ato da promessa e não pode ser antecipada.
- Reentrega custa 60% do frete original.

---

## 5. Estado Inicial: Plano de Demanda e Política de Estoque

### 5.1 O plano já rodou

O horizonte de 12 semanas foi planejado e o estoque **já está posicionado** nos CDs conforme a
política vigente. O participante **não replaneja do zero** — ele reage ao desvio entre o pedido
real e o plano.

### 5.2 Política de estoque vigente (baseline)

| Parâmetro | Regra |
|-----------|-------|
| Modelo | Revisão periódica semanal, ponto de ressuprimento por CD × SKU |
| Estoque de segurança | `ES = z × σ_D × √LT`, com `z` pelo nível de serviço da classe |
| Nível de serviço alvo | Classe A: 97,5% · Classe B: 95% · Classe C: 90% |
| Cobertura alvo | CD-SP: 21 dias · CD-PR e CD-GO: 28 dias · CD-PE: 35 dias |
| Alocação do plano | Proporcional à demanda prevista da região primária de cada CD |
| Congelamento | Produção congelada nas 2 primeiras semanas do horizonte |

### 5.3 Consumo de forecast

Pedido real **consome** a previsão da semana correspondente:

```
saldo_forecast[sku, região, semana] = max(0, forecast − pedidos_reais_acumulados)
```

| Situação | Interpretação | Consequência |
|----------|---------------|--------------|
| Consumo < 80% do forecast na semana | Demanda abaixo do plano | Estoque parado, risco de shelf life (P5) |
| Consumo entre 80% e 110% | Dentro da tolerância | Segue o plano |
| Consumo > 110% | Demanda acima do plano | **Dispara replanejamento** (BR-701) |

---

## 6. O Processo Ponta a Ponta

```
┌──────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────────┐   ┌─────────────┐
│ 1. Entrada   │──▶│ 2. Validação │──▶│ 3. Sourcing   │──▶│ 4. Promessa  │──▶│ 5. Carga    │
│    do pedido │   │  e priorização│   │  (qual CD?)   │   │  de data     │   │ (completo?) │
└──────────────┘   └──────────────┘   └───────────────┘   └──────────────┘   └─────────────┘
                                              │                                      │
                                              ▼                                      ▼
                                     ┌────────────────────┐              ┌────────────────────┐
                                     │ 6. Replanejamento  │◀─────────────│ 7. Execução e      │
                                     │ e rebalanceamento  │              │    medição (OTIF)  │
                                     └────────────────────┘              └────────────────────┘
```

| Etapa | O que acontece | Regras |
|-------|----------------|--------|
| 1. Entrada | Pedido chega por EDI, portal ou televendas, com `data_solicitada` | BR-1xx |
| 2. Validação | Crédito, cadastro, MOQ, priorização por segmento | BR-1xx, BR-2xx |
| 3. Sourcing | Determina o CD de atendimento por linha | BR-3xx |
| 4. Promessa | Calcula e comunica a data prometida | BR-4xx |
| 5. Composição de carga | Decide embarque completo, parcial ou consolidação | BR-5xx |
| 6. Replanejamento | Desvio de demanda dispara transferências | BR-7xx |
| 7. Medição | OTIF, custo e aderência entram no painel | Seção 9 |

---

## 7. Regras de Negócio

Cada regra tem ID rastreável. A formulação matemática (`02-formulation.md`) precisa transformar
**cada uma** em restrição, penalidade ou premissa explicitamente relaxada.

### BR-1xx — Entrada e validação do pedido

| ID | Regra |
|----|-------|
| **BR-101** | Pedido recebido após o cutoff do CD (**18h00 local**) conta como recebido no próximo dia útil. |
| **BR-102** | O calendário de operação é por região: sábado é dia útil apenas para CD-SP e CD-PR; domingos e feriados nacionais/estaduais não operam. |
| **BR-103** | Pedido sem crédito aprovado fica bloqueado e **não consome ATP** até a liberação. |
| **BR-104** | Pedido mínimo: KA e DIS ≥ 1 palete completo por linha; VAR ≥ R$ 1.500; ECM sem mínimo. |
| **BR-105** | A `data_solicitada` do cliente nunca pode ser anterior ao lead time mínimo viável — nesse caso a promessa usa o lead time mínimo e a divergência é registrada. |
| **BR-106** | Pedido com SKU descontinuado ou com shelf life remanescente < 2/3 do total é rejeitado automaticamente. |

### BR-2xx — Segmentação e nível de serviço

| ID | Regra |
|----|-------|
| **BR-201** | Prioridade de alocação em disputa por estoque: **KA > DIS > VAR > ECM**. |
| **BR-202** | Dentro do mesmo segmento, desempate por `data_solicitada` mais próxima; persistindo, por valor do pedido (maior primeiro). |
| **BR-203** | KA tem **estoque reservado** por SKU no CD primário, equivalente a 5 dias de demanda contratada. Esse estoque não é visível como ATP para os demais segmentos. |
| **BR-204** | A reserva de KA expira em 72h sem consumo e volta ao pool geral. |
| **BR-205** | Nenhum segmento pode ter fill rate mensal abaixo de **85%** — piso de serviço que impede sacrificar a cauda longa para proteger KA. |
| **BR-206** | Entrega de KA fora da janela agendada é recusada: conta como falha de OTIF e gera custo de reentrega (60% do frete original). |

### BR-3xx — Sourcing (determinação do CD)

| ID | Regra |
|----|-------|
| **BR-301** | A ordem de avaliação é: **(1)** CD primário da região do cliente → **(2)** CD secundário com ATP → **(3)** transferência entre CDs → **(4)** produção (CTP) → **(5)** backorder. |
| **BR-302** | O CD primário só é preterido se não houver ATP suficiente **ou** se atender por ele quebrar o SLA do cliente. |
| **BR-303** | Sourcing de CD secundário exige que o **custo incremental de frete não ultrapasse 8% do valor da linha** — acima disso, exige aprovação (marca a linha como exceção). |
| **BR-304** | Uma linha de pedido **não pode ser dividida entre CDs** para KA e DIS. Para VAR e ECM, split entre CDs é permitido no máximo em 2 origens. |
| **BR-305** | P3 (alto valor) tem restrição de rota: carga acima de **R$ 150.000** exige escolta, com custo adicional de R$ 1.850 por viagem. |
| **BR-306** | P5 só pode ser alocado se o shelf life remanescente na data de entrega for ≥ 60 dias. |
| **BR-307** | Transferência entre CDs para atender pedido específico (BR-301 passo 3) só é permitida se a data prometida resultante ainda respeitar o SLA do segmento. |

### BR-4xx — Promessa de data

| ID | Regra |
|----|-------|
| **BR-401** | `data_prometida = data_liberação + lead_time_transporte(CD, região) + buffer`, ajustada ao calendário da região (BR-102). |
| **BR-402** | O ATP considera: estoque disponível no CD + recebimentos confirmados de planta com ETA ≤ data de separação − 1 dia. |
| **BR-403** | Recebimento de planta **não confirmado** não entra no ATP; entra no CTP, usado somente a partir do passo 4 de BR-301. |
| **BR-404** | A data prometida é comunicada ao cliente **no ato** e passa a ser o compromisso medido pelo OTIF. |
| **BR-405** | Reprogramação da data prometida é permitida **uma única vez** por pedido e conta como falha de confiabilidade, mesmo que a nova data seja cumprida. |
| **BR-406** | Prometer data anterior ao lead time mínimo viável é proibido — o validador rejeita a submissão (viola viabilidade). |
| **BR-407** | O buffer de segurança é decisão do participante, mas a folga média é penalizada pela rubrica (Promise Tightness). |

### BR-5xx — Composição de carga

| ID | Regra |
|----|-------|
| **BR-501** | KA exige **pedido completo**: embarque parcial só com autorização registrada; sem ela, o pedido aguarda a completude ou vira falha de in-full. |
| **BR-502** | DIS aceita parcial, desde que cada embarque seja múltiplo de palete completo por SKU. |
| **BR-503** | VAR aceita parcial se o embarque cobrir **≥ 80% do valor** do pedido; abaixo disso, aguarda consolidação. |
| **BR-504** | ECM aceita parcial livremente, sem restrição de composição. |
| **BR-505** | Ocupação mínima do veículo de distribuição: **75% do peso ou do volume** (o que atingir primeiro). Abaixo disso, o embarque aguarda consolidação por até 24h — exceto se isso quebrar o SLA. |
| **BR-506** | Consolidação máxima: um veículo atende no máximo 8 pontos de entrega na mesma região. |
| **BR-507** | Carga mista com P3 acima de R$ 150.000 aciona BR-305 (escolta) para o veículo inteiro. |
| **BR-508** | Pedido em backorder tem prioridade de embarque sobre pedido novo do mesmo segmento quando o estoque chega. |
| **BR-509** | P3 (premium) não pode ter a linha fracionada entre embarques: sai inteira ou não sai. |

### BR-6xx — Frete e custo

| ID | Regra |
|----|-------|
| **BR-601** | **Frete de transferência (FTL):** `R$ 380 fixo + R$ 4,20/km`, veículo de 30 paletes. Carga inferior paga o veículo cheio. |
| **BR-602** | **Frete de distribuição (fracionado):** `max(R$ 180 mínimo; peso × tarifa_região) + 0,35% ad valorem + 0,12% GRIS`. |
| **BR-603** | Tarifa por região (R$/kg): SE 0,68 · S 0,82 · CO 1,05 · NE 1,24 · N 1,68. |
| **BR-604** | **Armazenagem:** R$ 38 por posição-palete/mês + R$ 2,10 por palete movimentado. |
| **BR-605** | **Custo de falta:** margem perdida de 22% do valor da linha não atendida. |
| **BR-606** | **Multa contratual KA:** 3% do valor faturado no mês se o OTIF do cliente ficar abaixo de 95%. |
| **BR-607** | **Expedição extraordinária** (aéreo/expresso) reduz o lead time em 50%, ao custo de 4× o frete normal. Uso livre, mas contabilizado. |
| **BR-608** | Ocupação de CD acima de 95% da capacidade gera custo de overflow de R$ 95/palete/mês (armazém externo). |

### BR-7xx — Replanejamento e rebalanceamento

| ID | Regra |
|----|-------|
| **BR-701** | Consumo de forecast acima de **110%** em uma região dispara avaliação de replanejamento para o SKU afetado. |
| **BR-702** | Cobertura projetada de um CD abaixo de **7 dias** para SKU classe A dispara proposta de transferência. |
| **BR-703** | Transferência entre CDs respeita MOQ de **1 palete completo** por SKU e capacidade de 30 paletes por veículo. |
| **BR-704** | Rebalanceamento não pode reduzir a cobertura do CD de origem abaixo de **10 dias** para SKU classe A. |
| **BR-705** | O horizonte de decisão de rebalanceamento é de **28 dias**, com replanejamento semanal. |
| **BR-706** | Produção está congelada nas 2 primeiras semanas: nesse período, só há transferência, não há mudança de plano de produção. |
| **BR-707** | P5 (shelf life 90 dias) com cobertura projetada acima de 45 dias dispara transferência preventiva ou ação comercial. |

### BR-8xx — Exceções e escalonamento

| ID | Regra |
|----|-------|
| **BR-801** | Linha sem atendimento viável em nenhum CD vira **backorder** com data estimada de reposição, não desaparece do pedido. |
| **BR-802** | Backorder com mais de 5 dias úteis escala para decisão comercial (expedição extraordinária ou cancelamento negociado). |
| **BR-803** | Ruptura em SKU de KA escala imediatamente, independentemente do prazo. |
| **BR-804** | Toda exceção (BR-303, BR-501, BR-607) é registrada com motivo — a taxa de exceções é um KPI de qualidade da decisão. |

---

## 8. Parâmetros de Custo — Resumo

| Componente | Fórmula | Fonte |
|------------|---------|-------|
| Frete transferência | `380 + 4,20 × km` por veículo de 30 paletes | BR-601 |
| Frete distribuição | `max(180; peso × tarifa) + 0,35% valor + 0,12% valor` | BR-602, BR-603 |
| Armazenagem | `38 × posições + 2,10 × paletes movimentados` | BR-604 |
| Falta | `0,22 × valor não atendido` | BR-605 |
| Multa KA | `0,03 × faturamento_mês_KA` se OTIF < 95% | BR-606 |
| Escolta P3 | `1.850` por viagem acima de R$ 150.000 | BR-305 |
| Reentrega KA | `0,60 × frete original` | BR-206 |
| Expedição extraordinária | `4 × frete normal` | BR-607 |
| Overflow de CD | `95 × paletes acima de 95% da capacidade` | BR-608 |

### Distâncias entre nós (km)

| | CD-SP | CD-PR | CD-GO | CD-PE |
|--|-------|-------|-------|-------|
| **PL-01 (Sumaré/SP)** | 90 | 480 | 930 | 2.660 |
| **PL-02 (Feira/BA)** | 1.960 | 2.380 | 1.600 | 800 |
| **CD-SP** | — | 410 | 930 | 2.660 |
| **CD-PR** | 410 | — | 1.340 | 3.070 |
| **CD-GO** | 930 | 1.340 | — | 1.900 |

---

## 9. KPIs

Nenhum KPI entra sem fórmula fechada e fonte de dados.

| KPI | Fórmula | Direção | Meta | Fonte |
|-----|---------|---------|------|-------|
| **OTIF** | linhas completas entregues até `requested_date` / total | ↑ | ≥ 95% geral · ≥ 98% KA | `orders` + `deliveries` |
| **On Time (cliente)** | entregas até `requested_date` / total | ↑ | ≥ 96% | `deliveries` |
| **In Full (IF)** | `pedidos com 100% da quantidade no 1º embarque / total` | ↑ | ≥ 97% | `shipments` |
| **Fill Rate (valor)** | `valor atendido / valor pedido` | ↑ | ≥ 96% · piso 85% por segmento | `orders` |
| **Promise Reliability** | entregas até `promised_date` / total de linhas | ↑ | ≥ 96% | `deliveries` |
| **Promise Tightness** | `média(data_prometida − data mínima viável)` em dias | ↓ | ≤ 1,5 d | Simulador |
| **Custo logístico** | `(frete + armazenagem + falta + multas) / receita` | ↓ | ≤ 8,5% | Custos |
| **Custo por pedido servido** | `custo logístico total / pedidos entregues` | ↓ | — | Custos |
| **Aderência ao sourcing primário** | `linhas atendidas pelo CD primário / total` | ↑ | ≥ 85% | Sourcing |
| **Ocupação média do veículo** | `média(max(peso, volume) / capacidade)` | ↑ | ≥ 80% | `shipments` |
| **Taxa de exceção** | `linhas com exceção registrada / total` | ↓ | ≤ 5% | BR-804 |
| **Aderência ao plano** | `1 − abs(pedidos reais − forecast) / forecast` | ↑ | — | Plano vs. real |

### Promise Reliability e OTIF medem coisas diferentes

Esta distinção é o coração da avaliação e fecha o principal vetor de gaming:

| Métrica | Medida contra | O que captura |
|---------|---------------|---------------|
| **Promise Reliability** | `promised_date` — a data que **o fornecedor** prometeu | A palavra dada |
| **OTIF** | `requested_date` — a data que **o cliente** pediu | O que o cliente sente |

Empurrar todas as promessas para a frente melhora a primeira e **não salva a segunda**. Não
existe atalho: para subir o OTIF é preciso colocar o produto no lugar certo, na hora certa —
com sourcing, rebalanceamento e composição de carga.

---

## 10. Função Objetivo e Trade-offs

O participante minimiza o custo total servido, sujeito às restrições de serviço:

```
min  Σ frete_transferência + Σ frete_distribuição + Σ armazenagem
   + Σ custo_falta + Σ multas_contratuais + Σ custos_extraordinários

sujeito a:
   OTIF_KA        ≥ 98%
   OTIF_geral     ≥ 95%
   Fill_Rate_seg  ≥ 85%   ∀ segmento          (BR-205)
   ATP, capacidade de CD, MOQ, calendário, shelf life
```

### Os quatro trade-offs centrais

| # | Trade-off | Lado A | Lado B |
|---|-----------|--------|--------|
| 1 | **Prazo vs. frete** | Atender do CD distante cumpre o SLA | Frete e ad valorem sobem; P3 sofre mais |
| 2 | **Promessa apertada vs. confiável** | Prazo curto ganha o cliente | Promessa quebrada custa OTIF e multa |
| 3 | **KA vs. cauda longa** | Proteger KA evita multa de 3% | O piso de 85% por segmento (BR-205) impede sacrificar VAR/ECM |
| 4 | **Embarcar agora vs. consolidar** | Embarque imediato cumpre o prazo | Veículo com baixa ocupação (BR-505) eleva o custo unitário |

> Uma solução que otimiza só um lado sempre existe — e sempre perde. É por isso que a rubrica
> (`04-scoring-rubric.md`) pontua serviço **e** custo simultaneamente.

---

## 11. Modelo de Dados da Simulação

| Tabela | Grão | Colunas-chave |
|--------|------|---------------|
| `orders.csv` | Linha de pedido | `order_id`, `order_line_id`, `customer_id`, `sku`, `qty`, `order_ts`, `requested_date`, `ship_to_region`, `channel` |
| `customer_master.csv` | Cliente | `customer_id`, `segment` (KA/DIS/VAR/ECM), `region`, `sla_hours`, `full_order_required`, `penalty_pct` |
| `sku_master.csv` | SKU | `sku`, `abc_class`, `unit_weight_kg`, `unit_volume_m3`, `unit_value`, `units_per_pallet`, `shelf_life_days` |
| `dc_master.csv` | CD | `dc_id`, `region`, `pallet_capacity`, `cutoff_local_time`, `operating_days` |
| `plant_master.csv` | Planta | `plant_id`, `region`, `skus_produced`, `monthly_capacity` |
| `inventory_snapshot.csv` | Dia × CD × SKU | `date`, `dc_id`, `sku`, `on_hand`, `allocated`, `reserved_ka`, `in_transit`, `oldest_batch_date` |
| `inbound_plan.csv` | Recebimento | `receipt_id`, `plant_id`, `dc_id`, `sku`, `qty`, `eta_date`, `confirmed` |
| `demand_plan.csv` | Semana × SKU × região | `week`, `sku`, `region`, `forecast_qty`, `consumed_qty` |
| `lanes.csv` | CD → região | `dc_id`, `region`, `transit_days`, `rate_per_kg` |
| `transfer_lanes.csv` | Nó → nó | `origin`, `dest`, `distance_km`, `transit_days`, `pallets_per_truck` |
| `holidays_calendar.csv` | Dia × região | `date`, `region`, `is_business_day` |
| `historical_deliveries.csv` | Linha entregue | `order_line_id`, `dc_id`, `promised_date`, `ship_date`, `actual_delivery_date`, `promise_revisions` |

### Submissões esperadas

`submission_promise.csv`
```csv
order_line_id,dc_id,promised_date,qty_committed,shipment_group
OL-000001,CD-SP,2026-09-14,480,SHP-0001
```

`submission_rebalance.csv`
```csv
transfer_id,origin,dest,sku,qty_pallets,ship_date
TRF-0001,CD-SP,CD-GO,P4,12,2026-09-09
```

---

## 12. Cenários de Exercício

Cinco cenários que o time deve conseguir explicar e defender com números.

| # | Cenário | O que testa |
|---|---------|-------------|
| **C1** | Pedido KA de P1+P2+P3 no Sudeste, com ATP de P3 apenas em CD-GO | Sourcing multi-CD com BR-304 (split proibido para KA) vs. transferência |
| **C2** | Pico de P4 em novembro estoura a capacidade do CD-SP | Overflow (BR-608) vs. rebalanceamento antecipado (BR-702) |
| **C3** | Demanda de P5 no Nordeste 40% abaixo do plano | Shelf life (BR-707): transferir, promover ou perder |
| **C4** | Onda de pedidos VAR e ECM no Sul com veículos em baixa ocupação | Consolidação (BR-505) vs. SLA de 72h/120h |
| **C5** | Ruptura de P2 em CD-PE na semana congelada de produção | BR-706: só resta transferência; de onde, a que custo, sem furar BR-704 |

---

## 13. Baseline Operacional (como se faz hoje)

O baseline que os participantes precisam bater:

1. **Sourcing:** sempre o CD primário da região; se faltar, o CD com maior estoque disponível.
2. **Promessa:** `lead time da lane + 2 dias de folga fixa`, sem diferenciar cliente nem SKU.
3. **Composição:** embarca o que tem, exceto KA, que aguarda completude.
4. **Rebalanceamento:** transfere quando a cobertura cai abaixo de 7 dias, em lote fixo de 10 paletes.
5. **Sem antecipação:** nenhuma decisão usa previsão — tudo é reativo.

Esse baseline é regra fixa, sem otimização e sem previsão. É exatamente onde a maior parte das
operações reais está — e é por isso que ele é o piso justo de comparação.

### Desempenho medido do baseline

Rodado sobre o pacote de dados v1.0.0 pelo avaliador oficial:

| Métrica | Janela pública | Janela privada | Meta |
|---------|----------------|----------------|------|
| Promise Reliability | 94,8% | 94,7% | ≥ 96% |
| OTIF (vs. data do cliente) | 93,5% | 91,2% | ≥ 95% |
| OTIF Key Account | 86,7% | 86,6% | ≥ 98% |
| In Full | 100,0% | 100,0% | ≥ 97% |
| Fill Rate (valor) | 100,0% | 100,0% | ≥ 96% |
| Aderência ao CD primário | 90,2% | 86,0% | ≥ 85% |
| Ocupação média do veículo | 4,7% | 4,6% | ≥ 80% |
| Custo logístico / receita | 6,3% | 5,4% | ≤ 8,5% |
| **Custo total** | **R$ 491.736** | **R$ 463.201** | — |

Onde o dinheiro está parado: a multa de Key Account custa **R$ 95.562** na janela pública e
**R$ 105.966** na privada, e a ocupação de 4,7% significa frete mínimo pago em quase todo
embarque — R$ 305.083 de frete de distribuição que a consolidação ataca diretamente.

Reproduza:

```bash
python desafio/ferramentas/baseline_guloso.py --janela public
python desafio/ferramentas/avaliar.py --submissao desafio/submissoes/baseline/public
```

---

## 14. Premissas

Itens não fornecidos pelo negócio e assumidos para tornar o cenário simulável:

| ID | Premissa |
|----|----------|
| **[PREMISSA-01]** | Valores, distâncias, tarifas e capacidades são representativos de uma operação nacional de bens de consumo, não de uma empresa específica. |
| **[PREMISSA-02]** | Capacidade de transporte é ilimitada em número de veículos — a restrição é custo, não disponibilidade de frota. |
| **[PREMISSA-03]** | Não há restrição fiscal ou tributária entre estados (ICMS, substituição tributária) — simplificação deliberada. |
| **[PREMISSA-04]** | O lead time de transporte é determinístico na simulação base; a variabilidade entra apenas na trilha preditiva (`03-predictive-track.md`). |
| **[PREMISSA-05]** | Não há devolução, avaria ou recall no horizonte simulado. |
| **[PREMISSA-06]** | O cliente aceita a data prometida sem renegociação — não há perda de pedido por prazo longo, apenas penalização na rubrica. |

> **[PREMISSA-06] é a mais forte do documento.** No mundo real, prazo longo perde venda. Aqui, a
> perda comercial é representada só pela penalidade de Promise Tightness. Se o desafio evoluir,
> este é o primeiro item a revisar.

---

## 15. O Pacote de Dados

O cenário descrito acima está materializado em dados sintéticos determinísticos (seed 42):

| Item | Onde |
|------|------|
| Pacote de dados (19 arquivos) | `desafio/dados/v1.0.0/` |
| Dicionário de dados | `desafio/dados/v1.0.0/data_dictionary.md` |
| Guia do participante | `desafio/README.md` |
| Material auxiliar de conceitos | `docs/desafio/conceitos-supply-chain.md` |
| Protótipo de exemplo comentado | `desafio/ferramentas/exemplo_prototipo.py` |
| Baseline de referência | `desafio/ferramentas/baseline_guloso.py` |
| Avaliador oficial | `desafio/ferramentas/avaliar.py` |
| Gerador (auditável) | `desafio/gerador/` |
| Gabarito | `desafio/privado/` — **não distribuído** |

O histórico cobre 12 meses (25.079 linhas de pedido); a janela pública tem 919 linhas e a
privada 976. Tudo roda com Python 3.10+ e biblioteca padrão, sem instalar nada.

---

## 16. Handoff

| Item | Destino |
|------|---------|
| Regras BR-101 a BR-804 | `@optimization-scientist` → cada uma vira restrição, penalidade ou premissa relaxada |
| KPIs da seção 9 | `@optimization-scientist` → base da rubrica de pontuação |
| Modelo de dados da seção 11 | `@data-challenge-ops` → geração do pacote |
| Trilha preditiva | `@ai-ml-engineer` → lead time, demanda por região, risco de atraso |

**Próximo comando:**

```
@optimization-scientist *formulate
```

---

*Documento produzido pelo squad `desafio-supply-chain-squad`, task `scm-define-business-scope.md`.*
