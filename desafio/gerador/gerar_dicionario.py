"""
Gera o dicionário de dados a partir dos CSVs realmente publicados.

Escrever o dicionário à mão garante que ele fique desatualizado. Este script
lê os arquivos, conta as linhas, calcula os checksums e só então escreve —
o que estiver aqui existe no pacote.

Uso:
    python desafio/gerador/gerar_dicionario.py
"""

import csv
import hashlib
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parametros as P  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

PASTA = os.path.join("desafio", "dados", "v" + P.VERSAO)

TABELAS = {
    "orders_history.csv": dict(
        grao="Linha de pedido histórica",
        desc="Todo pedido recebido entre o início do histórico e a data de corte. "
             "É a base de treino: use para entender sazonalidade, mix e comportamento "
             "por segmento.",
        chave="order_line_id",
    ),
    "orders_test_public.csv": dict(
        grao="Linha de pedido a promissar",
        desc="Pedidos da janela pública. São estes que a sua submissão precisa "
             "promissar — todos eles, sem exceção.",
        chave="order_line_id",
    ),
    "orders_test_private.csv": dict(
        grao="Linha de pedido a promissar",
        desc="Pedidos da janela privada, usada no ranking final.",
        chave="order_line_id",
    ),
    "historical_deliveries.csv": dict(
        grao="Linha entregue",
        desc="O que de fato aconteceu com cada linha histórica: de qual CD saiu, "
             "quando prometeu, quando embarcou, quando chegou. É aqui que está o "
             "histórico de lead time real para a trilha preditiva.",
        chave="order_line_id",
    ),
    "inventory_snapshot.csv": dict(
        grao="Dia × CD × SKU",
        desc="Posição de estoque no fim de cada dia do histórico. A linha da data "
             "de corte é o seu estado inicial.",
        chave="(date, dc_id, sku)",
    ),
    "inbound_plan.csv": dict(
        grao="Recebimento de planta",
        desc="Recebimentos programados. Só os confirmados entram no ATP (BR-402); "
             "os não confirmados são CTP e podem atrasar.",
        chave="receipt_id",
    ),
    "demand_plan.csv": dict(
        grao="Semana × SKU × região",
        desc="O plano de demanda vigente e o consumo real acumulado. Consumo acima "
             "de 110% do plano dispara replanejamento (BR-701).",
        chave="(week_start, sku, region)",
    ),
    "sku_master.csv": dict(grao="SKU", desc="Cadastro de produto.", chave="sku"),
    "customer_master.csv": dict(
        grao="Cliente",
        desc="Cadastro de cliente com segmento, SLA e regra de pedido completo.",
        chave="customer_id"),
    "dc_master.csv": dict(grao="Centro de distribuição",
                          desc="Capacidade, cutoff e calendário de cada CD.", chave="dc_id"),
    "plant_master.csv": dict(grao="Planta", desc="O que cada planta produz e sua capacidade.",
                             chave="plant_id"),
    "lanes.csv": dict(grao="CD → região",
                      desc="Lead time de distribuição e tarifa por quilo.",
                      chave="(dc_id, region)"),
    "transfer_lanes.csv": dict(grao="Nó → nó",
                               desc="Distâncias e lead times de suprimento e transferência.",
                               chave="(origin, dest)"),
    "vehicles.csv": dict(grao="Tipo de veículo",
                         desc="Capacidade de transferência e de distribuição.",
                         chave="vehicle_type"),
    "holidays_calendar.csv": dict(grao="Dia × região",
                                  desc="Calendário de dias úteis por região (BR-102).",
                                  chave="(date, region)"),
    "submission_example_promise.csv": dict(grao="Exemplo",
                                           desc="Formato aceito de submissão de promessa.",
                                           chave="—"),
    "submission_example_rebalance.csv": dict(grao="Exemplo",
                                             desc="Formato aceito de submissão de rebalanceamento.",
                                             chave="—"),
    "submission_example_forecast.csv": dict(
        grao="Exemplo",
        desc="Formato opcional da trilha preditiva: quantis de lead time por rota e dia.",
        chave="—"),
}

COLUNAS = {
    "order_id": ("texto", "—", "Identificador do pedido"),
    "order_line_id": ("texto", "—", "Identificador da linha — é a chave da submissão"),
    "customer_id": ("texto", "—", "Cliente, liga em customer_master"),
    "sku": ("texto", "—", "Produto, liga em sku_master"),
    "qty": ("inteiro", "unidades", "Quantidade pedida na linha"),
    "order_ts": ("timestamp", "ISO-8601", "Momento do pedido; a hora define o cutoff (BR-101)"),
    "requested_date": ("data", "AAAA-MM-DD", "Data que o cliente pediu — é contra ela que o OTIF é medido"),
    "ship_to_region": ("texto", "—", "Região de entrega: SE, S, CO, NE ou N"),
    "channel": ("texto", "—", "Canal de entrada: EDI, PORTAL ou TELEVENDAS"),
    "segment": ("texto", "—", "Segmento do cliente: KA, DIS, VAR ou ECM"),
    "dc_id": ("texto", "—", "Centro de distribuição"),
    "qty_ordered": ("inteiro", "unidades", "Quantidade pedida"),
    "qty_shipped": ("inteiro", "unidades", "Quantidade efetivamente embarcada"),
    "ship_date": ("data", "AAAA-MM-DD", "Data de embarque"),
    "promised_date": ("data", "AAAA-MM-DD", "Data prometida ao cliente"),
    "actual_delivery_date": ("data", "AAAA-MM-DD", "Data real de entrega"),
    "transit_days_actual": ("inteiro", "dias úteis", "Trânsito realizado da rota"),
    "promise_revisions": ("inteiro", "—", "Quantas vezes a data foi reprogramada (BR-405)"),
    "backorder_days": ("inteiro", "dias", "Dias que a linha ficou em backorder"),
    "on_time": ("0/1", "—", "Entregue até a data prometida"),
    "in_full": ("0/1", "—", "Entregue com a quantidade completa"),
    "date": ("data", "AAAA-MM-DD", "Dia de referência"),
    "on_hand": ("inteiro", "unidades", "Estoque físico no fim do dia"),
    "reserved_ka": ("inteiro", "unidades", "Parcela reservada a Key Accounts (BR-203)"),
    "in_transit": ("inteiro", "unidades", "Quantidade a caminho do CD"),
    "oldest_batch_date": ("data", "AAAA-MM-DD", "Data do lote mais antigo — relevante para P5"),
    "receipt_id": ("texto", "—", "Identificador do recebimento"),
    "plant_id": ("texto", "—", "Planta de origem"),
    "order_date": ("data", "AAAA-MM-DD", "Data em que a reposição foi disparada"),
    "eta_date": ("data", "AAAA-MM-DD", "Data prevista de chegada ao CD"),
    "confirmed": ("0/1", "—", "1 = entra no ATP (BR-402); 0 = CTP, pode atrasar (BR-403)"),
    "week_start": ("data", "AAAA-MM-DD", "Segunda-feira da semana"),
    "region": ("texto", "—", "Região"),
    "forecast_qty": ("inteiro", "unidades", "Demanda prevista pelo plano"),
    "consumed_qty": ("inteiro", "unidades", "Demanda real consumida; vazio nas semanas futuras"),
    "description": ("texto", "—", "Descrição do produto"),
    "abc_class": ("texto", "—", "Classe ABC"),
    "unit_weight_kg": ("decimal", "kg", "Peso unitário"),
    "unit_volume_m3": ("decimal", "m³", "Volume unitário"),
    "unit_value": ("decimal", "R$", "Valor unitário"),
    "units_per_pallet": ("inteiro", "unidades", "Unidades por palete completo"),
    "shelf_life_days": ("inteiro", "dias", "Validade total"),
    "allow_partial": ("0/1", "—", "0 = a linha não pode ser fracionada entre embarques (BR-509)"),
    "monthly_demand_units": ("inteiro", "unidades", "Demanda média mensal de referência"),
    "sla_hours": ("inteiro", "horas", "SLA contratado do cliente"),
    "full_order_required": ("0/1", "—", "1 = exige pedido completo (BR-501)"),
    "penalty_pct": ("decimal", "fração", "Multa contratual sobre o faturamento (BR-606)"),
    "priority_weight": ("inteiro", "—", "Prioridade de alocação: 1 é a maior (BR-201)"),
    "scheduled_window": ("0/1", "—", "1 = entrega em janela agendada (BR-206)"),
    "size_factor": ("decimal", "—", "Porte relativo do cliente"),
    "name": ("texto", "—", "Nome do nó"),
    "pallet_capacity": ("inteiro", "posições", "Capacidade de armazenagem do CD"),
    "daily_pallet_throughput": ("inteiro", "paletes/dia", "Capacidade de expedição por dia útil"),
    "cutoff_local_time": ("hora", "HH:MM", "Cutoff de recebimento de pedido (BR-101)"),
    "saturday_operating": ("0/1", "—", "1 = o CD opera aos sábados (BR-102)"),
    "target_coverage_days": ("inteiro", "dias", "Cobertura alvo da política de estoque"),
    "skus_produced": ("texto", "—", "SKUs produzidos, separados por |"),
    "monthly_capacity_units": ("inteiro", "unidades", "Capacidade mensal de produção"),
    "transit_days": ("inteiro", "dias", "Lead time da rota"),
    "rate_per_kg": ("decimal", "R$/kg", "Tarifa de frete fracionado (BR-603)"),
    "is_primary": ("0/1", "—", "1 = este CD é o primário da região (BR-301)"),
    "origin": ("texto", "—", "Nó de origem"),
    "dest": ("texto", "—", "Nó de destino"),
    "distance_km": ("inteiro", "km", "Distância rodoviária"),
    "pallets_per_truck": ("inteiro", "paletes", "Capacidade do veículo de transferência"),
    "fixed_cost": ("decimal", "R$", "Parcela fixa do frete FTL (BR-601)"),
    "cost_per_km": ("decimal", "R$/km", "Parcela variável do frete FTL (BR-601)"),
    "vehicle_type": ("texto", "—", "TRANSFERENCIA ou DISTRIBUICAO"),
    "pallets": ("inteiro", "paletes", "Capacidade em paletes"),
    "max_weight_kg": ("inteiro", "kg", "Capacidade de peso"),
    "max_volume_m3": ("decimal", "m³", "Capacidade cúbica"),
    "min_occupancy": ("decimal", "fração", "Ocupação mínima para expedir (BR-505)"),
    "is_business_day": ("0/1", "—", "1 = dia útil na região"),
    "holiday_name": ("texto", "—", "Nome do feriado, quando houver"),
    "qty_committed": ("inteiro", "unidades", "Quantidade que você se compromete a entregar"),
    "shipment_group": ("texto", "—", "Identificador do embarque: linhas do mesmo grupo viajam juntas"),
    "transfer_id": ("texto", "—", "Identificador da transferência"),
    "qty_pallets": ("inteiro", "paletes", "Quantidade transferida, em paletes completos"),
    "transit_q50": ("decimal", "dias", "Sua previsão de mediana do lead time"),
    "transit_q90": ("decimal", "dias", "Sua previsão de percentil 90 do lead time"),
}

VAZAMENTO = [
    ("actual_delivery_date", "historical_deliveries", "É o alvo — não existe no momento da decisão"),
    ("ship_date", "historical_deliveries", "Posterior à promessa"),
    ("transit_days_actual", "historical_deliveries", "Realizado; use apenas para treinar, nunca como feature do futuro"),
    ("on_time / in_full", "historical_deliveries", "Derivados do resultado"),
    ("promise_revisions", "historical_deliveries", "Posterior à decisão"),
    ("dc_id", "historical_deliveries", "É a decisão que você deve tomar"),
    ("backorder_days", "historical_deliveries", "Posterior à decisão"),
]


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def main():
    linhas = []
    A = linhas.append
    A(f"# Dicionário de Dados — Desafio Supply Chain v{P.VERSAO}\n")
    A(f"> Gerado em {date.today().isoformat()} · seed `{P.SEED}` · origem: dados sintéticos\n")
    A("Toda coluna publicada está aqui. Coluna sem linha neste documento é bug de "
      "empacotamento — reporte no canal do desafio.\n")

    A("## Convenções\n")
    A("| Item | Convenção |")
    A("|------|-----------|")
    A("| Datas | `AAAA-MM-DD` |")
    A("| Timestamps | `AAAA-MM-DDTHH:MM:SS`, horário local do CD |")
    A("| Encoding | UTF-8, separador `,`, decimal `.` |")
    A("| Nulos | campo vazio (sem `NULL`, sem `NaN`) |")
    A("| Moeda | R$, valores relativos a uma operação de bens de consumo |")
    A("| Quantidades | unidades de venda, sempre inteiras |\n")

    A("## Janelas temporais\n")
    A("| Janela | Período | O que você recebe |")
    A("|--------|---------|-------------------|")
    A(f"| Histórico (treino) | {P.HIST_INICIO} a {P.HIST_FIM} | Pedidos, entregas realizadas, "
      "estoque diário, plano vs. consumo |")
    A(f"| Public test | {P.PUB_INICIO} a {P.PUB_FIM} | Só os pedidos. O trânsito realizado é gabarito |")
    A(f"| Private test | {P.PRI_INICIO} a {P.PRI_FIM} | Só os pedidos. Define o ranking final |")
    A("\nO split é **temporal**. Não embaralhe. O estado inicial da simulação é a linha de "
      f"`inventory_snapshot.csv` na data {P.HIST_FIM}.\n")

    A("## Tabelas\n")
    for nome, meta in TABELAS.items():
        caminho = os.path.join(PASTA, nome)
        if not os.path.exists(caminho):
            continue
        with open(caminho, newline="", encoding="utf-8") as f:
            leitor = csv.reader(f)
            cabecalho = next(leitor)
            n = sum(1 for _ in leitor)
        tamanho = os.path.getsize(caminho) / 1024
        A(f"### `{nome}`\n")
        A(f"{meta['desc']}\n")
        A(f"**Grão:** {meta['grao']} · **Chave:** `{meta['chave']}` · "
          f"**Linhas:** {n:,} · **Tamanho:** {tamanho:.1f} KB".replace(",", "."))
        A(f"\n`sha256 {sha256(caminho)[:24]}…`\n")
        A("| Coluna | Tipo | Unidade | Descrição |")
        A("|--------|------|---------|-----------|")
        for col in cabecalho:
            tipo, unidade, desc = COLUNAS.get(col, ("texto", "—", "—"))
            A(f"| `{col}` | {tipo} | {unidade} | {desc} |")
        A("")

    A("## Colunas proibidas como feature (leakage list)\n")
    A("Estas colunas existem no histórico mas **não existem no momento em que você decide**. "
      "Treinar com elas produz um modelo que não sobrevive à avaliação.\n")
    A("| Coluna | Tabela | Por que é vazamento |")
    A("|--------|--------|---------------------|")
    for col, tab, motivo in VAZAMENTO:
        A(f"| `{col}` | {tab} | {motivo} |")
    A("")
    A("**Cutoff de informação.** No momento em que o pedido é promissado (`order_ts`), "
      "você pode usar: cadastros, estoque e recebimentos com data ≤ `order_ts`, e histórico "
      "de entregas com `actual_delivery_date` < `order_ts`. Nada além disso.\n")

    A("## Simplificações declaradas\n")
    A("| # | Simplificação |")
    A("|---|---------------|")
    A("| 1 | Recebimentos **confirmados** chegam na ETA planejada. Os **não confirmados** "
      "atrasam de 2 a 6 dias — o atraso real está no gabarito. |")
    A("| 2 | Capacidade de transporte é ilimitada em número de veículos; a restrição é custo. |")
    A("| 3 | Não há tributação interestadual (ICMS, ST). |")
    A("| 4 | Não há devolução, avaria nem recall no horizonte. |")
    A("| 5 | O cliente aceita a data prometida sem renegociar. A perda comercial de um prazo "
      "longo aparece só via OTIF contra a data solicitada. |")
    A("")
    A("## Verificação de integridade\n")
    A("```bash\ncd dados/v" + P.VERSAO + "\nsha256sum -c CHECKSUMS.txt\n```\n")
    A("---\n")
    A("*Gerado por `desafio/gerador/gerar_dicionario.py`.*")

    destino = os.path.join(PASTA, "data_dictionary.md")
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    print(f"dicionário escrito em {destino} ({len(linhas)} linhas)")


if __name__ == "__main__":
    main()
