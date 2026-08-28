# Dicionário de Dados — Desafio Supply Chain v1.0.0

> Gerado em 2026-08-28 · seed `42` · origem: dados sintéticos

Toda coluna publicada está aqui. Coluna sem linha neste documento é bug de empacotamento — reporte no canal do desafio.

## Convenções

| Item | Convenção |
|------|-----------|
| Datas | `AAAA-MM-DD` |
| Timestamps | `AAAA-MM-DDTHH:MM:SS`, horário local do CD |
| Encoding | UTF-8, separador `,`, decimal `.` |
| Nulos | campo vazio (sem `NULL`, sem `NaN`) |
| Moeda | R$, valores relativos a uma operação de bens de consumo |
| Quantidades | unidades de venda, sempre inteiras |

## Janelas temporais

| Janela | Período | O que você recebe |
|--------|---------|-------------------|
| Histórico (treino) | 2025-09-01 a 2026-08-28 | Pedidos, entregas realizadas, estoque diário, plano vs. consumo |
| Public test | 2026-08-31 a 2026-09-11 | Só os pedidos. O trânsito realizado é gabarito |
| Private test | 2026-09-14 a 2026-09-25 | Só os pedidos. Define o ranking final |

O split é **temporal**. Não embaralhe. O estado inicial da simulação é a linha de `inventory_snapshot.csv` na data 2026-08-28.

## Tabelas

### `orders_history.csv`

Todo pedido recebido entre o início do histórico e a data de corte. É a base de treino: use para entender sazonalidade, mix e comportamento por segmento.

**Grão:** Linha de pedido histórica · **Chave:** `order_line_id` · **Linhas:** 25.079 · **Tamanho:** 2008.3 KB

`sha256 1a74cb44732c2c7015b379cb…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `order_id` | texto | — | Identificador do pedido |
| `order_line_id` | texto | — | Identificador da linha — é a chave da resposta |
| `customer_id` | texto | — | Cliente, liga em customer_master |
| `sku` | texto | — | Produto, liga em sku_master |
| `qty` | inteiro | unidades | Quantidade pedida na linha |
| `order_ts` | timestamp | ISO-8601 | Momento do pedido; a hora define o cutoff (BR-101) |
| `requested_date` | data | AAAA-MM-DD | Data que o cliente pediu — é contra ela que o OTIF é medido |
| `ship_to_region` | texto | — | Região de entrega: SE, S, CO, NE ou N |
| `channel` | texto | — | Canal de entrada: EDI, PORTAL ou TELEVENDAS |
| `segment` | texto | — | Segmento do cliente: KA, DIS, VAR ou ECM |

### `orders_test_public.csv`

Pedidos da janela pública. São estes que a sua resposta precisa promissar — todos eles, sem exceção.

**Grão:** Linha de pedido a promissar · **Chave:** `order_line_id` · **Linhas:** 919 · **Tamanho:** 73.8 KB

`sha256 9f316b3f169d65070fe75ad6…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `order_id` | texto | — | Identificador do pedido |
| `order_line_id` | texto | — | Identificador da linha — é a chave da resposta |
| `customer_id` | texto | — | Cliente, liga em customer_master |
| `sku` | texto | — | Produto, liga em sku_master |
| `qty` | inteiro | unidades | Quantidade pedida na linha |
| `order_ts` | timestamp | ISO-8601 | Momento do pedido; a hora define o cutoff (BR-101) |
| `requested_date` | data | AAAA-MM-DD | Data que o cliente pediu — é contra ela que o OTIF é medido |
| `ship_to_region` | texto | — | Região de entrega: SE, S, CO, NE ou N |
| `channel` | texto | — | Canal de entrada: EDI, PORTAL ou TELEVENDAS |
| `segment` | texto | — | Segmento do cliente: KA, DIS, VAR ou ECM |

### `orders_test_private.csv`

Pedidos da janela privada, usada no ranking final.

**Grão:** Linha de pedido a promissar · **Chave:** `order_line_id` · **Linhas:** 976 · **Tamanho:** 78.2 KB

`sha256 e16c928bb63971649abdbdf7…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `order_id` | texto | — | Identificador do pedido |
| `order_line_id` | texto | — | Identificador da linha — é a chave da resposta |
| `customer_id` | texto | — | Cliente, liga em customer_master |
| `sku` | texto | — | Produto, liga em sku_master |
| `qty` | inteiro | unidades | Quantidade pedida na linha |
| `order_ts` | timestamp | ISO-8601 | Momento do pedido; a hora define o cutoff (BR-101) |
| `requested_date` | data | AAAA-MM-DD | Data que o cliente pediu — é contra ela que o OTIF é medido |
| `ship_to_region` | texto | — | Região de entrega: SE, S, CO, NE ou N |
| `channel` | texto | — | Canal de entrada: EDI, PORTAL ou TELEVENDAS |
| `segment` | texto | — | Segmento do cliente: KA, DIS, VAR ou ECM |

### `historical_deliveries.csv`

O que de fato aconteceu com cada linha histórica: de qual CD saiu, quando prometeu, quando embarcou, quando chegou. É aqui que está o histórico de lead time real para a trilha preditiva.

**Grão:** Linha entregue · **Chave:** `order_line_id` · **Linhas:** 25.077 · **Tamanho:** 2009.9 KB

`sha256 9a7c99389a9bcfd5e1c8d3cf…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `order_line_id` | texto | — | Identificador da linha — é a chave da resposta |
| `order_id` | texto | — | Identificador do pedido |
| `dc_id` | texto | — | Centro de distribuição |
| `sku` | texto | — | Produto, liga em sku_master |
| `qty_ordered` | inteiro | unidades | Quantidade pedida |
| `qty_shipped` | inteiro | unidades | Quantidade efetivamente embarcada |
| `ship_date` | data | AAAA-MM-DD | Data de embarque |
| `promised_date` | data | AAAA-MM-DD | Data prometida ao cliente |
| `actual_delivery_date` | data | AAAA-MM-DD | Data real de entrega |
| `transit_days_actual` | inteiro | dias úteis | Trânsito realizado da rota |
| `promise_revisions` | inteiro | — | Quantas vezes a data foi reprogramada (BR-405) |
| `backorder_days` | inteiro | dias | Dias que a linha ficou em backorder |
| `on_time` | 0/1 | — | Entregue até a data prometida |
| `in_full` | 0/1 | — | Entregue com a quantidade completa |

### `inventory_snapshot.csv`

Posição de estoque no fim de cada dia do histórico. A linha da data de corte é o seu estado inicial.

**Grão:** Dia × CD × SKU · **Chave:** `(date. dc_id. sku)` · **Linhas:** 7.240 · **Tamanho:** 317.3 KB

`sha256 898bbf8833718b631cf53c66…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `date` | data | AAAA-MM-DD | Dia de referência |
| `dc_id` | texto | — | Centro de distribuição |
| `sku` | texto | — | Produto, liga em sku_master |
| `on_hand` | inteiro | unidades | Estoque físico no fim do dia |
| `reserved_ka` | inteiro | unidades | Parcela reservada a Key Accounts (BR-203) |
| `in_transit` | inteiro | unidades | Quantidade a caminho do CD |
| `oldest_batch_date` | data | AAAA-MM-DD | Data do lote mais antigo — relevante para P5 |

### `inbound_plan.csv`

Recebimentos programados. Só os confirmados entram no ATP (BR-402); os não confirmados são CTP e podem atrasar.

**Grão:** Recebimento de planta · **Chave:** `receipt_id` · **Linhas:** 652 · **Tamanho:** 35.9 KB

`sha256 58e7352f8c7c9b98e4fa0ab0…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `receipt_id` | texto | — | Identificador do recebimento |
| `plant_id` | texto | — | Planta de origem |
| `dc_id` | texto | — | Centro de distribuição |
| `sku` | texto | — | Produto, liga em sku_master |
| `qty` | inteiro | unidades | Quantidade pedida na linha |
| `order_date` | data | AAAA-MM-DD | Data em que a reposição foi disparada |
| `eta_date` | data | AAAA-MM-DD | Data prevista de chegada ao CD |
| `confirmed` | 0/1 | — | 1 = entra no ATP (BR-402); 0 = CTP, pode atrasar (BR-403) |

### `demand_plan.csv`

O plano de demanda vigente e o consumo real acumulado. Consumo acima de 110% do plano dispara replanejamento (BR-701).

**Grão:** Semana × SKU × região · **Chave:** `(week_start. sku. region)` · **Linhas:** 1.400 · **Tamanho:** 37.2 KB

`sha256 f781d2f3657dfa91943b4eb6…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `week_start` | data | AAAA-MM-DD | Segunda-feira da semana |
| `sku` | texto | — | Produto, liga em sku_master |
| `region` | texto | — | Região |
| `forecast_qty` | inteiro | unidades | Demanda prevista pelo plano |
| `consumed_qty` | inteiro | unidades | Demanda real consumida; vazio nas semanas futuras |

### `sku_master.csv`

Cadastro de produto.

**Grão:** SKU · **Chave:** `sku` · **Linhas:** 5 · **Tamanho:** 0.4 KB

`sha256 e940d0d8b4f23c5a4e62c014…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `sku` | texto | — | Produto, liga em sku_master |
| `description` | texto | — | Descrição do produto |
| `abc_class` | texto | — | Classe ABC |
| `unit_weight_kg` | decimal | kg | Peso unitário |
| `unit_volume_m3` | decimal | m³ | Volume unitário |
| `unit_value` | decimal | R$ | Valor unitário |
| `units_per_pallet` | inteiro | unidades | Unidades por palete completo |
| `shelf_life_days` | inteiro | dias | Validade total |
| `allow_partial` | 0/1 | — | 0 = a linha não pode ser fracionada entre embarques (BR-509) |
| `monthly_demand_units` | inteiro | unidades | Demanda média mensal de referência |

### `customer_master.csv`

Cadastro de cliente com segmento, SLA e regra de pedido completo.

**Grão:** Cliente · **Chave:** `customer_id` · **Linhas:** 816 · **Tamanho:** 27.9 KB

`sha256 c7ee5e18700b5b50ae319bad…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `customer_id` | texto | — | Cliente, liga em customer_master |
| `segment` | texto | — | Segmento do cliente: KA, DIS, VAR ou ECM |
| `region` | texto | — | Região |
| `sla_hours` | inteiro | horas | SLA contratado do cliente |
| `full_order_required` | 0/1 | — | 1 = exige pedido completo (BR-501) |
| `penalty_pct` | decimal | fração | Multa contratual sobre o faturamento (BR-606) |
| `priority_weight` | inteiro | — | Prioridade de alocação: 1 é a maior (BR-201) |
| `scheduled_window` | 0/1 | — | 1 = entrega em janela agendada (BR-206) |
| `size_factor` | decimal | — | Porte relativo do cliente |

### `dc_master.csv`

Capacidade, cutoff e calendário de cada CD.

**Grão:** Centro de distribuição · **Chave:** `dc_id` · **Linhas:** 4 · **Tamanho:** 0.3 KB

`sha256 5ebd7c8aa40165e5542455e7…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `dc_id` | texto | — | Centro de distribuição |
| `name` | texto | — | Nome do nó |
| `region` | texto | — | Região |
| `pallet_capacity` | inteiro | posições | Capacidade de armazenagem do CD |
| `daily_pallet_throughput` | inteiro | paletes/dia | Capacidade de expedição por dia útil |
| `cutoff_local_time` | hora | HH:MM | Cutoff de recebimento de pedido (BR-101) |
| `saturday_operating` | 0/1 | — | 1 = o CD opera aos sábados (BR-102) |
| `target_coverage_days` | inteiro | dias | Cobertura alvo da política de estoque |

### `plant_master.csv`

O que cada planta produz e sua capacidade.

**Grão:** Planta · **Chave:** `plant_id` · **Linhas:** 2 · **Tamanho:** 0.1 KB

`sha256 e3bbeec8a815adfc108743ed…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `plant_id` | texto | — | Planta de origem |
| `name` | texto | — | Nome do nó |
| `region` | texto | — | Região |
| `skus_produced` | texto | — | SKUs produzidos, separados por | |
| `monthly_capacity_units` | inteiro | unidades | Capacidade mensal de produção |

### `lanes.csv`

Lead time de distribuição e tarifa por quilo.

**Grão:** CD → região · **Chave:** `(dc_id. region)` · **Linhas:** 20 · **Tamanho:** 0.4 KB

`sha256 eb54c97f592f2129c7da2e97…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `dc_id` | texto | — | Centro de distribuição |
| `region` | texto | — | Região |
| `transit_days` | inteiro | dias | Lead time da rota |
| `rate_per_kg` | decimal | R$/kg | Tarifa de frete fracionado (BR-603) |
| `is_primary` | 0/1 | — | 1 = este CD é o primário da região (BR-301) |

### `transfer_lanes.csv`

Distâncias e lead times de suprimento e transferência.

**Grão:** Nó → nó · **Chave:** `(origin. dest)` · **Linhas:** 20 · **Tamanho:** 0.7 KB

`sha256 fba5324828ce7e4305b6e764…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `origin` | texto | — | Nó de origem |
| `dest` | texto | — | Nó de destino |
| `distance_km` | inteiro | km | Distância rodoviária |
| `transit_days` | inteiro | dias | Lead time da rota |
| `pallets_per_truck` | inteiro | paletes | Capacidade do veículo de transferência |
| `fixed_cost` | decimal | R$ | Parcela fixa do frete FTL (BR-601) |
| `cost_per_km` | decimal | R$/km | Parcela variável do frete FTL (BR-601) |

### `vehicles.csv`

Capacidade de transferência e de distribuição.

**Grão:** Tipo de veículo · **Chave:** `vehicle_type` · **Linhas:** 2 · **Tamanho:** 0.1 KB

`sha256 d21a217108d4a62ae2472e5a…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `vehicle_type` | texto | — | TRANSFERENCIA ou DISTRIBUICAO |
| `pallets` | inteiro | paletes | Capacidade em paletes |
| `max_weight_kg` | inteiro | kg | Capacidade de peso |
| `max_volume_m3` | decimal | m³ | Capacidade cúbica |
| `min_occupancy` | decimal | fração | Ocupação mínima para expedir (BR-505) |

### `holidays_calendar.csv`

Calendário de dias úteis por região (BR-102).

**Grão:** Dia × região · **Chave:** `(date. region)` · **Linhas:** 2.100 · **Tamanho:** 37.2 KB

`sha256 36a95e9d2eed4acd5ff62019…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `date` | data | AAAA-MM-DD | Dia de referência |
| `region` | texto | — | Região |
| `is_business_day` | 0/1 | — | 1 = dia útil na região |
| `holiday_name` | texto | — | Nome do feriado, quando houver |

### `resposta_exemplo_promessa.csv`

Formato aceito de resposta de promessa.

**Grão:** Exemplo · **Chave:** `—` · **Linhas:** 20 · **Tamanho:** 0.9 KB

`sha256 b08c97abf3aeb87c5122388a…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `order_line_id` | texto | — | Identificador da linha — é a chave da resposta |
| `dc_id` | texto | — | Centro de distribuição |
| `promised_date` | data | AAAA-MM-DD | Data prometida ao cliente |
| `qty_committed` | inteiro | unidades | Quantidade que você se compromete a entregar |
| `shipment_group` | texto | — | Identificador do embarque: linhas do mesmo grupo viajam juntas |

### `resposta_exemplo_rebalanceamento.csv`

Formato aceito de resposta de rebalanceamento.

**Grão:** Exemplo · **Chave:** `—` · **Linhas:** 3 · **Tamanho:** 0.2 KB

`sha256 a5514d7a89081c2ac57f0b42…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `transfer_id` | texto | — | Identificador da transferência |
| `origin` | texto | — | Nó de origem |
| `dest` | texto | — | Nó de destino |
| `sku` | texto | — | Produto, liga em sku_master |
| `qty_pallets` | inteiro | paletes | Quantidade transferida, em paletes completos |
| `ship_date` | data | AAAA-MM-DD | Data de embarque |

### `resposta_exemplo_previsao.csv`

Formato opcional da trilha preditiva: quantis de lead time por rota e dia.

**Grão:** Exemplo · **Chave:** `—` · **Linhas:** 60 · **Tamanho:** 1.5 KB

`sha256 842e717a65a5bacaba40a713…`

| Coluna | Tipo | Unidade | Descrição |
|--------|------|---------|-----------|
| `dc_id` | texto | — | Centro de distribuição |
| `region` | texto | — | Região |
| `ship_date` | data | AAAA-MM-DD | Data de embarque |
| `transit_q50` | decimal | dias | Sua previsão de mediana do lead time |
| `transit_q90` | decimal | dias | Sua previsão de percentil 90 do lead time |

## Colunas proibidas como feature (leakage list)

Estas colunas existem no histórico mas **não existem no momento em que você decide**. Treinar com elas produz um modelo que não sobrevive à avaliação.

| Coluna | Tabela | Por que é vazamento |
|--------|--------|---------------------|
| `actual_delivery_date` | historical_deliveries | É o alvo — não existe no momento da decisão |
| `ship_date` | historical_deliveries | Posterior à promessa |
| `transit_days_actual` | historical_deliveries | Realizado; use apenas para treinar, nunca como feature do futuro |
| `on_time / in_full` | historical_deliveries | Derivados do resultado |
| `promise_revisions` | historical_deliveries | Posterior à decisão |
| `dc_id` | historical_deliveries | É a decisão que você deve tomar |
| `backorder_days` | historical_deliveries | Posterior à decisão |

**Cutoff de informação.** No momento em que o pedido é promissado (`order_ts`), você pode usar: cadastros, estoque e recebimentos com data ≤ `order_ts`, e histórico de entregas com `actual_delivery_date` < `order_ts`. Nada além disso.

## Simplificações declaradas

| # | Simplificação |
|---|---------------|
| 1 | Recebimentos **confirmados** chegam na ETA planejada. Os **não confirmados** atrasam de 2 a 6 dias — o atraso real está no gabarito. |
| 2 | Capacidade de transporte é ilimitada em número de veículos; a restrição é custo. |
| 3 | Não há tributação interestadual (ICMS, ST). |
| 4 | Não há devolução, avaria nem recall no horizonte. |
| 5 | O cliente aceita a data prometida sem renegociar. A perda comercial de um prazo longo aparece só via OTIF contra a data solicitada. |

## Verificação de integridade

```bash
cd dados/v1.0.0
sha256sum -c CHECKSUMS.txt
```

---

*Gerado por `desafio/gerador/gerar_dicionario.py`.*
