"""
Utilidades compartilhadas pelo baseline e pelo avaliador.

Sem dependências externas. Se você quiser usar pandas, polars ou o que for
na sua solução, fique à vontade — isto aqui é só o piso comum.
"""

import csv
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gerador"))
import parametros as P  # noqa: E402

DADOS_PADRAO = os.path.join("desafio", "dados", "v" + P.VERSAO)


# --------------------------------------------------------------- leitura

def ler_csv(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def escrever_csv(caminho, colunas, linhas):
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        # LF sempre: a resposta precisa ser byte a byte igual em qualquer sistema
        w = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore",
                           lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)


class Dados:
    """Carrega o pacote inteiro e indexa o que o baseline e o avaliador usam."""

    def __init__(self, pasta=DADOS_PADRAO):
        self.pasta = pasta
        self.skus = {r["sku"]: r for r in ler_csv(f"{pasta}/sku_master.csv")}
        self.clientes = {r["customer_id"]: r for r in ler_csv(f"{pasta}/customer_master.csv")}
        self.cds = {r["dc_id"]: r for r in ler_csv(f"{pasta}/dc_master.csv")}
        self.lanes = {(r["dc_id"], r["region"]): r for r in ler_csv(f"{pasta}/lanes.csv")}
        self.transfer = {(r["origin"], r["dest"]): r
                         for r in ler_csv(f"{pasta}/transfer_lanes.csv")}
        self.calendario = {(r["date"], r["region"]): r["is_business_day"] == "1"
                           for r in ler_csv(f"{pasta}/holidays_calendar.csv")}
        self.inbound = ler_csv(f"{pasta}/inbound_plan.csv")
        # estoque de abertura por janela avaliada — ponto de partida do seu ATP
        self.abertura = defaultdict(dict)
        for r in ler_csv(f"{pasta}/inventory_opening.csv"):
            self.abertura[r["window"]][(r["dc_id"], r["sku"])] = int(r["on_hand"])
        self.plano = ler_csv(f"{pasta}/demand_plan.csv")

        # estoque no fim do histórico
        corte = P.HIST_FIM.isoformat()
        self.estoque_inicial = {}
        self.reserva_ka = {}
        for r in ler_csv(f"{pasta}/inventory_snapshot.csv"):
            if r["date"] == corte:
                self.estoque_inicial[(r["dc_id"], r["sku"])] = int(r["on_hand"])
                self.reserva_ka[(r["dc_id"], r["sku"])] = int(r["reserved_ka"])

    def estoque_abertura(self, janela):
        """
        Posição de estoque no primeiro dia da janela avaliada.

        NÃO use o snapshot da data de corte para a janela privada: entre o corte
        e 14/09 os recebimentos chegam e os pedidos da janela pública já foram
        atendidos. Este arquivo é o ponto de partida correto do seu ATP.
        """
        return dict(self.abertura[janela])

    def pedidos(self, janela):
        arq = "orders_test_public.csv" if janela == "public" else "orders_test_private.csv"
        return ler_csv(f"{self.pasta}/{arq}")

    # ---------------------------------------------------------- calendário

    def dia_util(self, d, regiao):
        v = self.calendario.get((d.isoformat(), regiao))
        return v if v is not None else d.weekday() < 5

    def dia_util_cd(self, d, cd):
        limite = 6 if self.cds[cd]["saturday_operating"] == "1" else 5
        if d.weekday() >= limite:
            return False
        return self.dia_util(d, self.cds[cd]["region"]) or d.weekday() == 5

    def proximo_dia_util_cd(self, d, cd):
        for _ in range(20):
            if self.dia_util_cd(d, cd):
                return d
            d += timedelta(days=1)
        return d

    def somar_dias_uteis(self, d, n, regiao):
        atual, faltam = d, n
        while faltam > 0:
            atual += timedelta(days=1)
            if self.dia_util(atual, regiao):
                faltam -= 1
        return atual

    def subtrair_dias_uteis(self, d, n, regiao):
        atual, faltam = d, n
        while faltam > 0:
            atual -= timedelta(days=1)
            if self.dia_util(atual, regiao):
                faltam -= 1
        return atual

    # ---------------------------------------------------------- regras

    def liberacao(self, linha, cd):
        """Data em que o CD pode separar a linha, aplicando BR-101 e BR-102."""
        d = date.fromisoformat(linha["order_ts"][:10])
        if int(linha["order_ts"][11:13]) >= 18:
            d += timedelta(days=1)
        return self.proximo_dia_util_cd(d, cd)

    def transito(self, cd, regiao):
        return int(self.lanes[(cd, regiao)]["transit_days"])

    def data_minima_viavel(self, linha, cd):
        """Menor data prometível sem violar BR-406."""
        lib = self.liberacao(linha, cd)
        return self.somar_dias_uteis(lib, self.transito(cd, linha["ship_to_region"]),
                                     linha["ship_to_region"])

    def paletes(self, sku, qty):
        import math
        return math.ceil(qty / int(self.skus[sku]["units_per_pallet"]))

    def peso(self, sku, qty):
        return qty * float(self.skus[sku]["unit_weight_kg"])

    def volume(self, sku, qty):
        return qty * float(self.skus[sku]["unit_volume_m3"])

    def valor(self, sku, qty):
        return qty * float(self.skus[sku]["unit_value"])

    def segmento(self, linha):
        return self.clientes[linha["customer_id"]]["segment"]


# --------------------------------------------------------------- custos

def frete_distribuicao(dados, cd, itens, regiao):
    """
    Frete fracionado de um embarque (BR-602/603).
    `itens` = lista de (sku, qty). Frete mínimo é por embarque, não por linha.
    A tarifa por quilo vem da ROTA, não da região: atender de um CD distante
    custa mais por quilo do que atender do CD primário.
    """
    peso = sum(dados.peso(s, q) for s, q in itens)
    valor = sum(dados.valor(s, q) for s, q in itens)
    tarifa = float(dados.lanes[(cd, regiao)]["rate_per_kg"])
    base = max(P.FRETE_MINIMO, peso * tarifa)
    return base + valor * (P.AD_VALOREM + P.GRIS)


def frete_transferencia(dados, origem, destino, paletes):
    """Frete FTL de transferência (BR-601). Carga menor paga o veículo cheio."""
    import math
    lane = dados.transfer.get((origem, destino))
    if lane is None:
        return None
    veiculos = math.ceil(paletes / int(lane["pallets_per_truck"]))
    return veiculos * (float(lane["fixed_cost"]) +
                       float(lane["cost_per_km"]) * float(lane["distance_km"]))


def janela_datas(janela):
    return ((P.PUB_INICIO, P.PUB_FIM) if janela == "public"
            else (P.PRI_INICIO, P.PRI_FIM))


def horizonte_simulacao(janela):
    """A simulação corre do primeiro pedido da janela até 25 dias após o último."""
    ini, fim = janela_datas(janela)
    return ini, fim + timedelta(days=25)
