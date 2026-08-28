"""
Baseline de referência — é assim que a operação decide hoje.

Regra fixa, sem previsão e sem otimização:
  1. Sourcing: CD primário da região; faltando saldo, o CD com maior estoque.
  2. Promessa: lead time da rota + 2 dias de folga, igual para todo cliente.
  3. Composição: compromete a linha inteira; KA aguarda a completude.
  4. Rebalanceamento: transfere quando a cobertura projetada cai de 7 dias,
     em lote fixo de 10 paletes, do CD com maior cobertura.

Este é o piso a ser batido. Se a sua solução não supera isto, ela não está
resolvendo o problema — está reproduzindo o problema.

Uso:
    python desafio/ferramentas/baseline_guloso.py --janela public
    python desafio/ferramentas/baseline_guloso.py --janela private --saida minha_pasta/
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import Dados, escrever_csv, janela_datas  # noqa: E402
import parametros as P  # noqa: E402

# Console do Windows costuma abrir em cp1252 e quebra em acento e em "≥".
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


LOTE_TRANSFERENCIA_PALETES = 10
GATILHO_COBERTURA = P.COBERTURA_GATILHO


def demanda_diaria_prevista(dados, cd, sku, inicio, fim):
    """Demanda semanal prevista das regiões atendidas pelo CD, por dia."""
    regioes = [r for r, c in P.CD_PRIMARIO.items() if c == cd]
    total = 0
    semanas = 0
    for r in dados.plano:
        if r["sku"] != sku or r["region"] not in regioes:
            continue
        w = date.fromisoformat(r["week_start"])
        if inicio - timedelta(days=7) <= w <= fim:
            total += int(r["forecast_qty"])
            semanas += 1
    if semanas == 0:
        return 0.0
    return total / (semanas / len(regioes)) / 7 if semanas else 0.0


class ATP:
    """
    Disponibilidade no tempo por CD × SKU (BR-402).
    Estoque atual mais recebimentos CONFIRMADOS — não confirmados ficam de
    fora, conforme BR-403. Devolve a primeira data em que a quantidade cabe.
    """

    def __init__(self, dados, janela):
        abertura = janela_datas(janela)[0]
        self.eventos = defaultdict(list)
        for (cd, sku), qty in dados.estoque_abertura(janela).items():
            self.eventos[(cd, sku)].append([abertura, qty])
        for r in dados.inbound:
            # só o que chega A PARTIR da abertura: o resto já está no estoque
            if r["confirmed"] == "1" and r["eta_date"] >= abertura.isoformat():
                self.eventos[(r["dc_id"], r["sku"])].append(
                    [date.fromisoformat(r["eta_date"]), int(r["qty"])])
        for chave in self.eventos:
            self.eventos[chave].sort(key=lambda e: e[0])

    def primeira_data(self, cd, sku, qty, nao_antes):
        """
        A partir de que dia esta quantidade cabe? None se nunca couber.

        ATENÇÃO — é aqui que quase todo protótipo erra. Não basta o saldo
        CORRENTE cobrir a quantidade: é preciso que ele continue cobrindo em
        TODAS as datas seguintes. Senão você promete duas vezes o mesmo estoque:
        a primeira promessa embarca antes, a segunda descobre o armazém vazio.

        A conta certa é o "ATP cumulativo mínimo à frente":

            disponível(t) = mínimo, para todo u >= t, do saldo acumulado em u

        Quem devolve simplesmente o primeiro dia em que o saldo corrente cobre
        a quantidade super-compromete o estoque e reprova por fill rate.
        """
        eventos = self.eventos.get((cd, sku))
        if not eventos:
            return None
        datas = sorted({d for d, _ in eventos} | {nao_antes})
        acumulado, saldo = 0, {}
        i = 0
        ordenados = sorted(eventos, key=lambda e: e[0])
        for d in datas:
            while i < len(ordenados) and ordenados[i][0] <= d:
                acumulado += ordenados[i][1]
                i += 1
            saldo[d] = acumulado
        minimo_futuro, corrente = {}, None
        for d in reversed(datas):
            corrente = saldo[d] if corrente is None else min(corrente, saldo[d])
            minimo_futuro[d] = corrente
        for d in datas:
            if d >= nao_antes and minimo_futuro[d] >= qty:
                return d
        return None

    def alocar(self, cd, sku, qty, quando):
        self.eventos[(cd, sku)].append([quando, -qty])
        self.eventos[(cd, sku)].sort(key=lambda e: e[0])

    def saldo_em(self, cd, sku, quando):
        return sum(d for q, d in self.eventos.get((cd, sku), []) if q <= quando)


def gerar_promessas(dados, janela):
    linhas = dados.pedidos(janela)
    atp = ATP(dados, janela)

    # prioridade de segmento e depois data do pedido (BR-201/202)
    linhas.sort(key=lambda x: (int(dados.clientes[x["customer_id"]]["priority_weight"]),
                               x["order_ts"], x["order_line_id"]))

    saidas = []
    grupo = {}
    for ln in linhas:
        sku, qty = ln["sku"], int(ln["qty"])
        regiao = ln["ship_to_region"]
        primario = P.CD_PRIMARIO[regiao]
        lib = dados.liberacao(ln, primario)

        # Baseline: CD primário. Se ele não puder embarcar na liberação, tenta o
        # CD com maior saldo. Se nenhum puder hoje, a operação NÃO recusa o
        # pedido — ela promete uma data mais tarde, quando o estoque chega.
        cd = primario
        quando = atp.primeira_data(primario, sku, qty, lib)
        if quando is None or quando > lib:
            candidatos = []
            for c in dados.cds:
                if (c, regiao) not in dados.lanes:
                    continue
                lib_c = dados.liberacao(ln, c)
                q_c = atp.primeira_data(c, sku, qty, lib_c)
                if q_c is not None:
                    candidatos.append((q_c, dados.transito(c, regiao), c, lib_c))
            if candidatos:
                candidatos.sort()
                quando, _t, cd, lib = candidatos[0]

        if quando is None:
            comprometido, embarque = 0, lib
        else:
            comprometido, embarque = qty, quando
            atp.alocar(cd, sku, qty, embarque)

        prometida = dados.somar_dias_uteis(
            embarque, dados.transito(cd, regiao) + P.BUFFER_BASELINE, regiao)
        chave = (cd, ln["customer_id"], embarque.isoformat())
        if chave not in grupo:
            grupo[chave] = f"SHP-{len(grupo):05d}"
        saidas.append(dict(order_line_id=ln["order_line_id"], dc_id=cd,
                           promised_date=prometida.isoformat(),
                           qty_committed=comprometido,
                           shipment_group=grupo[chave]))
    return saidas


def gerar_rebalanceamento(dados, janela):
    inicio, fim = janela_datas(janela)
    abertura = dados.estoque_abertura(janela)
    transferencias = []
    seq = 1
    for sku in dados.skus:
        cobertura = {}
        for cd in dados.cds:
            dm = demanda_diaria_prevista(dados, cd, sku, inicio, fim)
            saldo = abertura.get((cd, sku), 0)
            cobertura[cd] = saldo / dm if dm > 0 else 999.0
        deficit = [cd for cd, c in cobertura.items() if c < GATILHO_COBERTURA]
        if not deficit:
            continue
        doador = max(cobertura, key=lambda c: cobertura[c])
        if cobertura[doador] < P.COBERTURA_MINIMA_ORIGEM:
            continue
        un_pal = int(dados.skus[sku]["units_per_pallet"])
        # BR-704: o doador não pode cair abaixo de 10 dias de cobertura
        dm_doador = demanda_diaria_prevista(dados, doador, sku, inicio, fim)
        folga_un = abertura.get((doador, sku), 0) - \
            dm_doador * P.COBERTURA_MINIMA_ORIGEM
        disponivel_paletes = max(0, int(folga_un // un_pal))
        for cd in sorted(deficit, key=lambda c: cobertura[c]):
            if cd == doador or (doador, cd) not in dados.transfer:
                continue
            paletes = min(LOTE_TRANSFERENCIA_PALETES, disponivel_paletes)
            if paletes < 1:                                    # BR-703: MOQ 1 palete
                continue
            disponivel_paletes -= paletes
            transferencias.append(dict(
                transfer_id=f"TRF-{seq:05d}", origin=doador, dest=cd, sku=sku,
                qty_pallets=paletes,
                ship_date=(inicio + timedelta(days=1)).isoformat()))
            seq += 1
    return transferencias


def main():
    ap = argparse.ArgumentParser(description="Baseline guloso de referência")
    ap.add_argument("--janela", choices=["public", "private"], default="public")
    ap.add_argument("--dados", default=None)
    ap.add_argument("--saida", default="desafio/submissoes/baseline")
    args = ap.parse_args()

    dados = Dados(args.dados) if args.dados else Dados()
    promessas = gerar_promessas(dados, args.janela)
    transferencias = gerar_rebalanceamento(dados, args.janela)

    base = os.path.join(args.saida, args.janela)
    escrever_csv(f"{base}/submission_promise.csv",
                 ["order_line_id", "dc_id", "promised_date", "qty_committed",
                  "shipment_group"], promessas)
    escrever_csv(f"{base}/submission_rebalance.csv",
                 ["transfer_id", "origin", "dest", "sku", "qty_pallets", "ship_date"],
                 transferencias)

    comprometidas = sum(1 for p in promessas if int(p["qty_committed"]) > 0)
    print(f"Baseline · janela {args.janela}")
    print(f"  linhas promissadas .... {len(promessas)}")
    print(f"  linhas comprometidas .. {comprometidas} ({comprometidas / len(promessas):.1%})")
    print(f"  transferências ........ {len(transferencias)}")
    print(f"  arquivos em ........... {base}/")


if __name__ == "__main__":
    main()
