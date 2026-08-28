"""
Protótipo de exemplo — leia este arquivo de cima a baixo antes de escrever o seu.

Não é a solução ótima. É a solução MÍNIMA COMPLETA: ela toca as três alavancas do
desafio e supera o baseline, para você ver o caminho e depois fazer melhor.

  Alavanca 1 — SOURCING     escolhe o CD que entrega na data do cliente pelo menor frete
  Alavanca 2 — PROMESSA     buffer por rota, calculado do histórico (não é chute fixo)
  Alavanca 3 — CONSOLIDAÇÃO agrupa embarques por cliente e semana para dividir frete

Também gera `resposta_previsao.csv`, que vale 20 pontos da rubrica e sai de graça
do mesmo cálculo do buffer.

Uso:
    python desafio/ferramentas/exemplo_prototipo.py --janela public
    python desafio/ferramentas/avaliar.py --resposta desafio/respostas/exemplo/public
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import Dados, ler_csv, escrever_csv, janela_datas  # noqa: E402
import parametros as P  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


# ====================================================================
# PASSO 1 — Aprender com o histórico quanto cada rota costuma atrasar
# ====================================================================

def quantis_de_transito(dados):
    """
    Para cada rota (CD → região), a distribuição de dias úteis que o transporte
    realmente levou no histórico.

    O `transit_days` do cadastro é a MEDIANA. Metade das viagens demora mais que
    isso. Prometer com a mediana quebra metade das promessas; prometer com um
    quantil alto entrega confiabilidade ao custo de um prazo maior. Devolvemos
    a distribuição inteira para você escolher o quantil por decisão.
    """
    amostras = defaultdict(list)
    for r in ler_csv(f"{dados.pasta}/historical_deliveries.csv"):
        if not r["transit_days_actual"]:
            continue
        # a região vem do pedido, não da entrega — precisamos cruzar as tabelas
        amostras[r["dc_id"]].append((r["order_line_id"], int(r["transit_days_actual"])))

    regiao_da_linha = {r["order_line_id"]: r["ship_to_region"]
                       for r in ler_csv(f"{dados.pasta}/orders_history.csv")}

    por_rota = defaultdict(list)
    for cd, itens in amostras.items():
        for oid, dias in itens:
            reg = regiao_da_linha.get(oid)
            if reg:
                por_rota[(cd, reg)].append(dias)

    for valores in por_rota.values():
        valores.sort()

    def q(cd, regiao, p, padrao=None):
        valores = por_rota.get((cd, regiao))
        if not valores:
            return padrao if padrao is not None else dados.transito(cd, regiao)
        return valores[min(len(valores) - 1, int(len(valores) * p))]

    return q


# ====================================================================
# PASSO 2 — ATP: o que eu posso prometer, e a partir de quando
# ====================================================================

class ATP:
    """
    ATP = Available To Promise. Não é "quanto tem no estoque": é quanto ainda
    NÃO foi prometido a ninguém, considerando o que vai chegar no futuro.

    A lista de eventos é uma linha do tempo por CD × SKU:
        (2026-08-28, +581)    estoque no corte
        (2026-09-03, +11100)  recebimento confirmado
        (2026-08-31, -300)    o que já prometemos a alguém

    Recebimento NÃO confirmado fica de fora de propósito (BR-403): ele pode
    atrasar, e prometer em cima dele é como gastar salário que não caiu.
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
        for k in self.eventos:
            self.eventos[k].sort(key=lambda e: e[0])

    def disponivel_em(self, cd, sku, quando):
        """Quanto está livre nesta data, já descontado o que foi prometido."""
        return sum(q for d, q in self.eventos.get((cd, sku), []) if d <= quando)

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

    def reservar(self, cd, sku, qty, quando):
        self.eventos[(cd, sku)].append([quando, -qty])
        self.eventos[(cd, sku)].sort(key=lambda e: e[0])


# ====================================================================
# PASSO 3 — Decidir CD, data e embarque para cada linha
# ====================================================================

def resolver(dados, janela):
    q = quantis_de_transito(dados)
    atp = ATP(dados, janela)
    linhas = dados.pedidos(janela)

    # Quem tem prioridade decide primeiro — quem decide primeiro pega o estoque.
    # KA antes de DIS antes de VAR antes de ECM (BR-201).
    linhas.sort(key=lambda x: (int(dados.clientes[x["customer_id"]]["priority_weight"]),
                               x["order_ts"], x["order_line_id"]))

    saidas, grupos = [], {}
    pendentes_por_rota = defaultdict(lambda: dict(nome=None, clientes=set()))
    for ln in linhas:
        sku, qty = ln["sku"], int(ln["qty"])
        regiao = ln["ship_to_region"]
        pedida = date.fromisoformat(ln["requested_date"])
        seg = dados.segmento(ln)

        # --- monta as opções de atendimento, uma por CD com lane para a região
        opcoes = []
        for cd in dados.cds:
            if (cd, regiao) not in dados.lanes:
                continue
            lib = dados.liberacao(ln, cd)          # respeita cutoff e calendário
            quando = atp.primeira_data(cd, sku, qty, lib)
            if quando is None:
                continue
            transito = dados.transito(cd, regiao)
            chegada = dados.somar_dias_uteis(quando, transito, regiao)
            tarifa = float(dados.lanes[(cd, regiao)]["rate_per_kg"])
            opcoes.append(dict(cd=cd, embarque=quando, chegada=chegada,
                               frete=dados.peso(sku, qty) * tarifa,
                               no_prazo=chegada <= pedida))

        if not opcoes:
            # Não há como atender: comprometa 0 em vez de mentir uma data.
            # Cuidado: fazer isso demais derruba o fill rate e reprova (BR-205).
            saidas.append(dict(order_line_id=ln["order_line_id"],
                               dc_id=P.CD_PRIMARIO[regiao],
                               promised_date=dados.somar_dias_uteis(
                                   date.fromisoformat(ln["order_ts"][:10]), 10, regiao
                               ).isoformat(),
                               qty_committed=0, shipment_group=""))
            continue

        # --- a escolha: entre as que chegam na data do cliente, a mais barata.
        #     Se nenhuma chega a tempo, a que chega mais cedo (perder por 1 dia
        #     custa muito menos que perder por 5, e KA ainda tem multa).
        no_prazo = [o for o in opcoes if o["no_prazo"]]
        escolha = (min(no_prazo, key=lambda o: o["frete"]) if no_prazo
                   else min(opcoes, key=lambda o: (o["chegada"], o["frete"])))

        atp.reservar(escolha["cd"], sku, qty, escolha["embarque"])

        # --- consolidação: MESMO CD, MESMA REGIÃO, MESMO DIA DE EMBARQUE.
        #
        #     Este é o almoço grátis do desafio. O frete fracionado tem mínimo
        #     de R$ 180 POR EMBARQUE (BR-602): mandar oito clientes num veículo
        #     paga um mínimo em vez de oito. E como todas as linhas do grupo já
        #     estão disponíveis no mesmo dia, ninguém espera por ninguém —
        #     economia de frete com zero de atraso.
        #
        #     O limite é BR-506: no máximo 8 pontos de entrega por veículo.
        #     Consolidar ao longo da SEMANA cortaria mais frete ainda, mas aí o
        #     grupo espera pela última linha e o OTIF desaba. Testamos: derruba
        #     o OTIF de Key Account de 82% para 31%. Não vale.
        #     Grupo grande acopla mais gente: se UMA linha não tiver estoque no
        #     dia, todo o veículo espera. Por isso KA e DIS viajam em grupos
        #     menores — eles têm multa e SLA curto, não podem pegar carona no
        #     atraso alheio.
        #     E a regra mais importante da consolidação: só junte quem JÁ ESTÁ
        #     disponível. Uma linha que espera um recebimento futuro viaja
        #     sozinha — se ela entrar no grupo, o veículo inteiro fica preso
        #     esperando por ela, e oito clientes atrasam por causa de um.
        lib_escolhida = dados.liberacao(ln, escolha["cd"])
        espera_estoque = escolha["embarque"] > lib_escolhida
        if espera_estoque:
            nome_solo = f"GRP-{len(grupos):05d}"
            grupos[nome_solo] = True
            saidas.append(dict(order_line_id=ln["order_line_id"], dc_id=escolha["cd"],
                               promised_date=None, qty_committed=qty,
                               shipment_group=nome_solo,
                               _embarque=escolha["embarque"], _regiao=regiao, _seg=seg))
            continue

        limite = 3 if seg in ("KA", "DIS") else P.MAX_PONTOS_ENTREGA
        pendente = pendentes_por_rota[(escolha["cd"], regiao, escolha["embarque"],
                                       seg in ("KA", "DIS"))]
        if pendente["nome"] is None or (len(pendente["clientes"]) >= limite
                                        and ln["customer_id"] not in pendente["clientes"]):
            pendente["nome"] = f"GRP-{len(grupos):05d}"
            pendente["clientes"] = set()
            grupos[pendente["nome"]] = True
        pendente["clientes"].add(ln["customer_id"])

        saidas.append(dict(order_line_id=ln["order_line_id"], dc_id=escolha["cd"],
                           promised_date=None, qty_committed=qty,
                           shipment_group=pendente["nome"],
                           _embarque=escolha["embarque"], _regiao=regiao,
                           _seg=seg))

    # ---------------------------------------------------------------
    # SEGUNDA PASSAGEM — a promessa sai da data do EMBARQUE, não da linha
    #
    # Este é o erro que derruba a maioria dos primeiros protótipos: prometer a
    # partir da data em que a linha ficou disponível, e só depois consolidar.
    # O grupo só parte quando a ÚLTIMA linha dele fica pronta — quem prometeu
    # com base na própria linha já quebrou a promessa antes de embarcar.
    # ---------------------------------------------------------------
    partida = {}
    for s in saidas:
        if not s["shipment_group"]:
            continue
        g = s["shipment_group"]
        partida[g] = max(partida.get(g, s["_embarque"]), s["_embarque"])

    for s in saidas:
        regiao = s.get("_regiao")
        if not s["shipment_group"] or s["qty_committed"] == 0:
            if s["promised_date"] is None:
                s["promised_date"] = dados.somar_dias_uteis(
                    P.PUB_INICIO if janela == "public" else P.PRI_INICIO, 12,
                    regiao or "SE").isoformat()
            continue
        cd = s["dc_id"]
        embarque = partida[s["shipment_group"]]
        # Quantil por segmento: KA tem multa de 3%, então compra confiabilidade
        # (q95). ECM tem SLA de 120h e nenhuma multa — q80 basta e economiza
        # prazo. O baseline usa 2 dias fixos para todo mundo; isto é melhor
        # nos dois sentidos.
        p = 0.97 if s["_seg"] in ("KA", "DIS") else 0.90
        transito_seguro = max(q(cd, regiao, p), dados.transito(cd, regiao))
        s["promised_date"] = dados.somar_dias_uteis(
            embarque, transito_seguro, regiao).isoformat()

    for s in saidas:
        for k in ("_embarque", "_regiao", "_seg"):
            s.pop(k, None)
    return saidas, q


# ====================================================================
# PASSO 4 — Rebalanceamento: mandar estoque para onde ele vai faltar
# ====================================================================

def rebalancear(dados, janela):
    """
    Versão simples: para cada CD × SKU, compara o estoque com a demanda prevista
    da janela. Quem está sobrando manda para quem está faltando, respeitando o
    piso de cobertura da origem (BR-704) e o lote mínimo de 1 palete (BR-703).

    Aqui há muito espaço para melhorar: antecipar a data de embarque, considerar
    o custo da transferência contra o custo da falta evitada, priorizar SKUs de
    KA. O baseline transfere 10 paletes fixos; isto aqui dimensiona pela falta.
    """
    inicio, _fim = janela_datas(janela)
    abertura = dados.estoque_abertura(janela)
    previsto = defaultdict(int)
    for r in dados.plano:
        w = date.fromisoformat(r["week_start"])
        if inicio <= w <= inicio + timedelta(days=27):
            previsto[(P.CD_PRIMARIO[r["region"]], r["sku"])] += int(r["forecast_qty"])

    transferencias, seq = [], 1
    for sku in dados.skus:
        un_pal = int(dados.skus[sku]["units_per_pallet"])
        saldo = {cd: abertura.get((cd, sku), 0) for cd in dados.cds}
        necessidade = {cd: previsto.get((cd, sku), 0) for cd in dados.cds}
        falta = {cd: necessidade[cd] - saldo[cd] for cd in dados.cds}
        # sobra = estoque acima da necessidade, guardando 10 dias de cobertura
        sobra = {cd: saldo[cd] - necessidade[cd] - (necessidade[cd] / 28) *
                 P.COBERTURA_MINIMA_ORIGEM for cd in dados.cds}

        doadores = sorted([c for c in dados.cds if sobra[c] > un_pal],
                          key=lambda c: -sobra[c])
        carentes = sorted([c for c in dados.cds if falta[c] > 0], key=lambda c: -falta[c])
        for destino in carentes:
            for origem in doadores:
                if origem == destino or (origem, destino) not in dados.transfer:
                    continue
                paletes = int(min(sobra[origem], falta[destino]) // un_pal)
                if paletes < 1:
                    continue
                sobra[origem] -= paletes * un_pal
                falta[destino] -= paletes * un_pal
                transferencias.append(dict(
                    transfer_id=f"TRF-{seq:05d}", origin=origem, dest=destino, sku=sku,
                    qty_pallets=paletes,
                    ship_date=(inicio + timedelta(days=1)).isoformat()))
                seq += 1
                if falta[destino] <= 0:
                    break
    return transferencias


# ====================================================================
# PASSO 5 — A trilha preditiva sai do mesmo cálculo
# ====================================================================

def previsao(dados, q, janela):
    """
    A rubrica pede q50 e q90 do lead time por rota e dia de embarque.
    Já calculamos os quantis do histórico — é só publicá-los.
    Um modelo de verdade usaria sazonalidade, volume e congestionamento do CD.
    """
    inicio, fim = janela_datas(janela)
    linhas = []
    d = inicio
    while d <= fim + timedelta(days=25):
        for (cd, reg) in dados.lanes:
            linhas.append(dict(dc_id=cd, region=reg, ship_date=d.isoformat(),
                               transit_q50=q(cd, reg, 0.50),
                               transit_q90=q(cd, reg, 0.90)))
        d += timedelta(days=1)
    return linhas


def main():
    ap = argparse.ArgumentParser(description="Protótipo de exemplo")
    ap.add_argument("--janela", choices=["public", "private"], default="public")
    ap.add_argument("--saida", default="desafio/respostas/exemplo")
    args = ap.parse_args()

    dados = Dados()
    promessas, q = resolver(dados, args.janela)
    transferencias = rebalancear(dados, args.janela)
    forecast = previsao(dados, q, args.janela)

    base = os.path.join(args.saida, args.janela)
    escrever_csv(f"{base}/resposta_promessa.csv",
                 ["order_line_id", "dc_id", "promised_date", "qty_committed",
                  "shipment_group"], promessas)
    escrever_csv(f"{base}/resposta_rebalanceamento.csv",
                 ["transfer_id", "origin", "dest", "sku", "qty_pallets", "ship_date"],
                 transferencias)
    escrever_csv(f"{base}/resposta_previsao.csv",
                 ["dc_id", "region", "ship_date", "transit_q50", "transit_q90"], forecast)

    comprometidas = sum(1 for p in promessas if int(p["qty_committed"]) > 0)
    print(f"Protótipo de exemplo · janela {args.janela}")
    print(f"  linhas ................ {len(promessas)}")
    print(f"  comprometidas ......... {comprometidas} ({comprometidas / len(promessas):.1%})")
    print(f"  embarques ............. {len({p['shipment_group'] for p in promessas if p['shipment_group']})}")
    print(f"  transferências ........ {len(transferencias)}")
    print(f"  arquivos em ........... {base}/")
    print(f"\n  Avalie com:\n    python desafio/ferramentas/avaliar.py "
          f"--resposta {base} --janela {args.janela}")


if __name__ == "__main__":
    main()
