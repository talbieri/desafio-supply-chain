"""
Avaliador oficial do Desafio Supply Chain.

Faz três coisas, nesta ordem:
  1. VALIDA a submissão contra os gates (formato, cobertura, BR-406, viabilidade
     física, capacidade de CD, MOQ de transferência, piso de fill rate).
  2. SIMULA o atendimento dia a dia com o trânsito e os recebimentos realizados
     (que ficam no gabarito e você não tem).
  3. PONTUA conforme a rubrica publicada.

Submissão reprovada em qualquer gate não é pontuada — igual ao leaderboard.

Uso:
    python desafio/ferramentas/avaliar.py --submissao desafio/submissoes/baseline/public
    python desafio/ferramentas/avaliar.py --submissao minha/pasta --janela private --json
"""

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import (Dados, ler_csv, frete_distribuicao, frete_transferencia,  # noqa: E402
                   janela_datas, horizonte_simulacao)
import parametros as P  # noqa: E402

# Console do Windows costuma abrir em cp1252 e quebra em acento e em "≥".
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


GABARITO_PADRAO = os.path.join("desafio", "privado")

# alvos usados na normalização enquanto não há leaderboard com outras submissões
ALVOS = dict(promise_reliability=0.99, otif=0.98, fill_rate=0.995, custo_ganho=0.25,
             pinball=0.35)


# ====================================================================
# Validação
# ====================================================================

class Resultado:
    def __init__(self):
        self.erros = []
        self.avisos = []

    def erro(self, codigo, msg):
        self.erros.append(f"[{codigo}] {msg}")

    def aviso(self, codigo, msg):
        self.avisos.append(f"[{codigo}] {msg}")

    @property
    def valida(self):
        return not self.erros


def validar_formato(dados, promessas, transferencias, linhas, res):
    cols_p = {"order_line_id", "dc_id", "promised_date", "qty_committed", "shipment_group"}
    if promessas and not cols_p.issubset(promessas[0].keys()):
        res.erro("FORMATO", f"submission_promise.csv precisa das colunas {sorted(cols_p)}")
        return
    idx = {ln["order_line_id"]: ln for ln in linhas}
    vistos = set()
    for p in promessas:
        oid = p["order_line_id"]
        if oid not in idx:
            res.erro("LINHA_DESCONHECIDA", f"{oid} não pertence à janela avaliada")
            continue
        if oid in vistos:
            res.erro("LINHA_DUPLICADA", f"{oid} aparece mais de uma vez")
        vistos.add(oid)
        ln = idx[oid]
        if p["dc_id"] not in dados.cds:
            res.erro("CD_INVALIDO", f"{oid}: CD {p['dc_id']} não existe")
            continue
        try:
            prom = date.fromisoformat(p["promised_date"])
            qty = int(p["qty_committed"])
        except (ValueError, TypeError):
            res.erro("TIPO_INVALIDO", f"{oid}: data ou quantidade em formato inválido")
            continue
        pedida = int(ln["qty"])
        if qty < 0 or qty > pedida:
            res.erro("QTD_INVALIDA", f"{oid}: comprometido {qty} fora de [0, {pedida}]")
        seg = dados.segmento(ln)
        # BR-501/502: KA e DIS não aceitam fração da linha
        if seg in ("KA", "DIS") and qty not in (0, pedida):
            res.erro("BR-501", f"{oid} ({seg}): linha parcial não é permitida — "
                               f"comprometa 0 ou {pedida}")
        # BR-406: promessa não pode ser anterior ao mínimo viável
        if qty > 0:
            minima = dados.data_minima_viavel(ln, p["dc_id"])
            if prom < minima:
                res.erro("BR-406", f"{oid}: prometido {prom} antes do mínimo viável {minima}")
        if not dados.dia_util(prom, ln["ship_to_region"]):
            res.erro("BR-102", f"{oid}: {prom} não é dia útil na região {ln['ship_to_region']}")

    faltantes = set(idx) - vistos
    if faltantes:
        res.erro("COBERTURA", f"{len(faltantes)} linhas da janela sem promessa "
                              f"(ex.: {sorted(faltantes)[:3]})")

    for t in transferencias:
        if t["origin"] == t["dest"]:
            res.erro("TRF_INVALIDA", f"{t['transfer_id']}: origem igual ao destino")
        if (t["origin"], t["dest"]) not in dados.transfer:
            res.erro("TRF_LANE", f"{t['transfer_id']}: lane {t['origin']}→{t['dest']} não existe")
        if t["sku"] not in dados.skus:
            res.erro("TRF_SKU", f"{t['transfer_id']}: SKU {t['sku']} não existe")
        if int(t["qty_pallets"]) < 1:
            res.erro("BR-703", f"{t['transfer_id']}: MOQ é 1 palete completo")


# ====================================================================
# Simulação
# ====================================================================

def simular(dados, promessas, transferencias, linhas, gabarito, janela, res):
    ini, fim_sim = horizonte_simulacao(janela)
    transito_real = {}
    for r in gabarito["transito"]:
        if r["window"] == janela:
            transito_real[(r["dc_id"], r["region"], r["ship_date"])] = int(r["transit_days_actual"])
    inbound_real = defaultdict(list)
    for r in gabarito["inbound"]:
        # o que chegou antes da abertura já está no estoque inicial
        if r["eta_planned"] >= ini.isoformat():
            inbound_real[r["eta_actual"]].append((r["dc_id"], r["sku"], int(r["qty"])))

    # Ponto de partida: o estoque de abertura PUBLICADO da janela
    # (inventory_opening.csv). A rede não fica parada entre o corte e o início
    # da janela — e essa posição é a mesma que os participantes recebem.
    estoque = dados.estoque_abertura(janela)
    idx = {ln["order_line_id"]: ln for ln in linhas}
    plano = {p["order_line_id"]: p for p in promessas}

    # Embarques: as linhas do mesmo shipment_group viajam juntas e dividem um
    # único frete. O grupo só sai quando TODAS as suas linhas têm estoque —
    # consolidar reduz custo e atrasa quem já estava pronto. É a decisão de
    # composição de carga (BR-505/506) nas mãos de quem submete.
    grupos = defaultdict(lambda: dict(oids=[], regiao=None, clientes=set(), pronto=None))
    for oid, p in plano.items():
        if int(p["qty_committed"]) <= 0:
            continue
        ln = idx[oid]
        chave = (p["dc_id"], p["shipment_group"] or f"__{oid}")
        g = grupos[chave]
        g["oids"].append(oid)
        g["regiao"] = ln["ship_to_region"]
        g["clientes"].add(ln["customer_id"])
        lib = dados.liberacao(ln, p["dc_id"])
        g["pronto"] = lib if g["pronto"] is None else max(g["pronto"], lib)

    for (cd, nome), g in grupos.items():
        regioes = {idx[o]["ship_to_region"] for o in g["oids"]}
        if len(regioes) > 1:
            res.erro("EMBARQUE_MISTO",
                     f"grupo {nome} mistura as regiões {sorted(regioes)} — um embarque "
                     f"atende uma região")
        if len(g["clientes"]) > P.MAX_PONTOS_ENTREGA:
            res.erro("BR-506", f"grupo {nome}: {len(g['clientes'])} pontos de entrega, "
                               f"máximo {P.MAX_PONTOS_ENTREGA}")
    if not res.valida:
        return {}, defaultdict(float), 0.0

    chegadas_transf = defaultdict(list)
    custo = defaultdict(float)
    resultados = {}
    embarcados = set()
    ocupacoes = []
    paletes_dia = defaultdict(int)
    estoque_dia_paletes = defaultdict(float)

    # --- transferências (BR-601, BR-703, BR-704)
    for t in sorted(transferencias, key=lambda x: x["ship_date"]):
        d = date.fromisoformat(t["ship_date"])
        if not (ini <= d <= fim_sim):
            res.aviso("TRF_FORA", f"{t['transfer_id']}: ship_date fora do horizonte, ignorada")
            continue
        sku = t["sku"]
        un_pal = int(dados.skus[sku]["units_per_pallet"])
        qty = int(t["qty_pallets"]) * un_pal
        if estoque.get((t["origin"], sku), 0) < qty:
            res.erro("BR-704", f"{t['transfer_id']}: {t['origin']} não tem {qty} un de {sku} "
                               f"em {d} (disponível {estoque.get((t['origin'], sku), 0)})")
            continue
        estoque[(t["origin"], sku)] -= qty
        lane = dados.transfer[(t["origin"], t["dest"])]
        chegada = d + timedelta(days=int(lane["transit_days"]))
        chegadas_transf[chegada].append((t["dest"], sku, qty))
        custo["frete_transferencia"] += frete_transferencia(
            dados, t["origin"], t["dest"], int(t["qty_pallets"]))
        custo["movimentacao"] += 2 * int(t["qty_pallets"]) * P.ARMAZ_MOVIMENTACAO

    # --- dia a dia
    d = ini
    while d <= fim_sim:
        iso = d.isoformat()
        for (cd, sku, qty) in inbound_real.get(iso, []):
            estoque[(cd, sku)] = estoque.get((cd, sku), 0) + qty
        for (cd, sku, qty) in chegadas_transf.pop(d, []):
            estoque[(cd, sku)] = estoque.get((cd, sku), 0) + qty

        # embarca o quanto antes: o grupo sai no primeiro dia em que todas as
        # suas linhas têm estoque e o CD tem capacidade de expedição
        for chave in [c for c in grupos if c not in embarcados]:
            cd, nome = chave
            g = grupos[chave]
            if d < g["pronto"] or not dados.dia_util_cd(d, cd):
                continue
            itens = [(idx[o]["sku"], int(plano[o]["qty_committed"])) for o in g["oids"]]
            precisa = defaultdict(int)
            for s, q in itens:
                precisa[s] += q
            if any(estoque.get((cd, s), 0) < q for s, q in precisa.items()):
                continue
            pal = sum(dados.paletes(s, q) for s, q in precisa.items())
            if paletes_dia[(cd, d)] + pal > int(dados.cds[cd]["daily_pallet_throughput"]):
                continue

            for s, q in precisa.items():
                estoque[(cd, s)] -= q
            paletes_dia[(cd, d)] += pal
            custo["movimentacao"] += pal * P.ARMAZ_MOVIMENTACAO

            regiao = g["regiao"]
            frete = frete_distribuicao(dados, cd, itens, regiao)
            custo["frete_distribuicao"] += frete
            if sum(dados.valor(s, q) for s, q in itens if s == "P3") > P.ESCOLTA_LIMIAR:
                custo["escolta"] += P.ESCOLTA_CUSTO           # BR-305
            transito = transito_real.get((cd, regiao, d.isoformat()),
                                         dados.transito(cd, regiao))
            entrega = dados.somar_dias_uteis(d, transito, regiao)
            ocupacao = max(sum(dados.peso(s, q) for s, q in itens) /
                           P.VEICULO_DISTRIBUICAO["peso_kg"],
                           sum(dados.volume(s, q) for s, q in itens) /
                           P.VEICULO_DISTRIBUICAO["volume_m3"])
            ocupacoes.append(min(1.0, ocupacao))

            for o in g["oids"]:
                prom = date.fromisoformat(plano[o]["promised_date"])
                pedida = date.fromisoformat(idx[o]["requested_date"])
                cliente = dados.clientes[idx[o]["customer_id"]]
                # BR-206: KA fora da janela agendada é recusado e reentregue
                if cliente["scheduled_window"] == "1" and entrega > prom:
                    custo["reentrega"] += frete * P.REENTREGA_PCT / len(g["oids"])
                resultados[o] = dict(entregue=True, delivery=entrega, promised=prom,
                                     requested=pedida, embarque=d,
                                     on_time=entrega <= prom,
                                     on_time_cliente=entrega <= pedida,
                                     qty=int(plano[o]["qty_committed"]))
            embarcados.add(chave)

        for cd in dados.cds:
            pal = sum(dados.paletes(s, max(0, estoque.get((cd, s), 0))) for s in dados.skus)
            estoque_dia_paletes[cd] += pal
            capacidade = int(dados.cds[cd]["pallet_capacity"])
            if pal > capacidade * P.OVERFLOW_LIMIAR:
                custo["overflow"] += (pal - capacidade * P.OVERFLOW_LIMIAR) * \
                    P.OVERFLOW_PALETE_MES / 30                # BR-608
        d += timedelta(days=1)

    dias = (fim_sim - ini).days + 1
    for cd, acumulado in estoque_dia_paletes.items():
        custo["armazenagem"] += (acumulado / dias) * P.ARMAZ_POSICAO_MES * (dias / 30)

    # linhas que nunca embarcaram
    for oid in plano:
        if oid not in resultados:
            resultados[oid] = dict(entregue=False, delivery=None, promised=None,
                                   requested=None, embarque=None, on_time=False,
                                   on_time_cliente=False, qty=0)
    custo["_ocupacao_media"] = 0.0
    return resultados, custo, (sum(ocupacoes) / len(ocupacoes) if ocupacoes else 0.0)


# ====================================================================
# Métricas e score
# ====================================================================

def metricas(dados, linhas, promessas, resultados, custo, res, ocupacao=0.0):
    idx = {ln["order_line_id"]: ln for ln in linhas}
    plano = {p["order_line_id"]: p for p in promessas}

    n = len(idx)
    qtd_pedida = sum(int(ln["qty"]) for ln in linhas)
    valor_pedido = sum(dados.valor(ln["sku"], int(ln["qty"])) for ln in linhas)

    entregues = [o for o, r in resultados.items() if r["entregue"]]
    # Promise Reliability mede a palavra do fornecedor: entregou até a data que
    # prometeu. OTIF mede o que o cliente sente: chegou até a data que ele pediu.
    # Prometer folgado melhora a primeira e não salva a segunda — é o que impede
    # ganhar o desafio empurrando todas as datas para a frente.
    no_prazo = [o for o in entregues if resultados[o]["on_time"]]
    no_prazo_cliente = [o for o in entregues if resultados[o]["on_time_cliente"]]
    completos = [o for o in entregues
                 if resultados[o]["qty"] >= int(idx[o]["qty"])]
    otif = [o for o in entregues
            if resultados[o]["on_time_cliente"] and resultados[o]["qty"] >= int(idx[o]["qty"])]

    qtd_atendida = sum(resultados[o]["qty"] for o in entregues)
    valor_atendido = sum(dados.valor(idx[o]["sku"], resultados[o]["qty"]) for o in entregues)

    # folga da promessa contra o mínimo viável (BR-407)
    folgas = []
    for o, p in plano.items():
        if int(p["qty_committed"]) <= 0:
            continue
        minima = dados.data_minima_viavel(idx[o], p["dc_id"])
        prom = date.fromisoformat(p["promised_date"])
        folgas.append(max(0, sum(1 for i in range(1, (prom - minima).days + 1)
                                 if dados.dia_util(minima + timedelta(days=i),
                                                   idx[o]["ship_to_region"]))))
    tightness = sum(folgas) / len(folgas) if folgas else 0.0

    # fill rate por segmento (BR-205)
    seg = defaultdict(lambda: [0.0, 0.0])
    for ln in linhas:
        s = dados.segmento(ln)
        seg[s][1] += dados.valor(ln["sku"], int(ln["qty"]))
        r = resultados.get(ln["order_line_id"])
        if r and r["entregue"]:
            seg[s][0] += dados.valor(ln["sku"], r["qty"])
    fill_seg = {s: (a / b if b else 1.0) for s, (a, b) in seg.items()}

    # custo de falta e multa contratual
    custo["falta"] = (valor_pedido - valor_atendido) * P.MARGEM_PERDIDA
    ka_linhas = [ln for ln in linhas if dados.segmento(ln) == "KA"]
    ka_otif = (sum(1 for ln in ka_linhas
                   if ln["order_line_id"] in otif) / len(ka_linhas)) if ka_linhas else 1.0
    faturamento_ka = sum(dados.valor(ln["sku"],
                                     resultados[ln["order_line_id"]]["qty"])
                         for ln in ka_linhas if resultados[ln["order_line_id"]]["entregue"])
    if ka_otif < P.OTIF_GATILHO_MULTA:
        custo["multa_ka"] = faturamento_ka * P.MULTA_KA_PCT   # BR-606

    aderencia = sum(1 for o, p in plano.items()
                    if p["dc_id"] == P.CD_PRIMARIO[idx[o]["ship_to_region"]]) / n

    m = dict(
        linhas=n,
        promise_reliability=len(no_prazo) / n,
        on_time_cliente=len(no_prazo_cliente) / n,
        in_full=len(completos) / n,
        otif=len(otif) / n,
        otif_ka=ka_otif,
        fill_rate_qtd=qtd_atendida / qtd_pedida if qtd_pedida else 0.0,
        fill_rate_valor=valor_atendido / valor_pedido if valor_pedido else 0.0,
        fill_rate_por_segmento=fill_seg,
        promise_tightness=tightness,
        aderencia_cd_primario=aderencia,
        valor_pedido=valor_pedido,
        valor_atendido=valor_atendido,
        ocupacao_media_veiculo=ocupacao,
        custo_total=sum(v for k, v in custo.items() if not k.startswith("_")),
        custo_detalhado={k: round(v, 2) for k, v in sorted(custo.items())
                         if not k.startswith("_")},
        custo_logistico_pct=(sum(v for k, v in custo.items() if not k.startswith("_"))
                             / valor_atendido) if valor_atendido else 9.99,
    )

    # gates dependentes de resultado
    for s, v in fill_seg.items():
        if v < P.FILL_RATE_PISO_SEGMENTO:
            res.erro("BR-205", f"fill rate do segmento {s} = {v:.1%}, abaixo do piso de "
                               f"{P.FILL_RATE_PISO_SEGMENTO:.0%}")
    if m["fill_rate_valor"] < 0.70:
        res.erro("GATE_FILL", f"fill rate global {m['fill_rate_valor']:.1%} abaixo de 70%")
    return m


def avaliar_previsao(dados, caminho, gabarito, janela):
    """Dimensão preditiva (opcional): pinball loss do lead time por lane."""
    if not os.path.exists(caminho):
        return None
    prev = ler_csv(caminho)
    real = {(r["dc_id"], r["region"], r["ship_date"]): int(r["transit_days_actual"])
            for r in gabarito["transito"] if r["window"] == janela}
    perdas = []
    for r in prev:
        chave = (r["dc_id"], r["region"], r["ship_date"])
        if chave not in real:
            continue
        y = real[chave]
        for q, col in ((0.50, "transit_q50"), (0.90, "transit_q90")):
            try:
                yhat = float(r[col])
            except (KeyError, ValueError, TypeError):
                continue
            perdas.append(max(q * (y - yhat), (q - 1) * (y - yhat)))
    if not perdas:
        return None
    return sum(perdas) / len(perdas)


def normalizar(valor, pior, melhor):
    if melhor == pior:
        return 0.0
    return max(0.0, min(1.0, (valor - pior) / (melhor - pior)))


def pontuar(m, baseline, pinball):
    """Rubrica publicada: serviço 45 · custo 25 · preditiva 20 · entrega 10 (júri)."""
    s = {}
    s["promise_reliability"] = 25 * normalizar(
        m["promise_reliability"], baseline["promise_reliability"], ALVOS["promise_reliability"])
    s["otif"] = 12 * normalizar(m["otif"], baseline["otif"], ALVOS["otif"])
    s["fill_rate"] = 8 * normalizar(
        m["fill_rate_valor"], baseline["fill_rate_valor"], ALVOS["fill_rate"])
    ganho = (baseline["custo_total"] - m["custo_total"]) / baseline["custo_total"]
    s["custo"] = 25 * normalizar(ganho, 0.0, ALVOS["custo_ganho"])
    s["preditiva"] = 0.0 if pinball is None else 20 * normalizar(
        -pinball, -baseline.get("pinball", 1.20), -ALVOS["pinball"])

    total = sum(s.values())
    penal = {}
    if m["promise_tightness"] > 5:
        penal["tightness"] = 10.0                              # BR-407
    revisoes = 0.0
    penal_total = sum(penal.values()) + revisoes
    return dict(componentes={k: round(v, 2) for k, v in s.items()},
                penalidades=penal,
                bruto=round(total, 2),
                total=round(max(0.0, total - penal_total), 2),
                maximo_automatico=90.0,
                nota="Dimensão 4 (qualidade da entrega, 10 pts) é avaliada por júri humano.")


# ====================================================================
# Principal
# ====================================================================

def gabarito_de_treino(dados, seed=7):
    """
    Oráculo de TREINO — para você se avaliar sem o gabarito oficial.

    Sorteia o trânsito de cada rota a partir da distribuição observada no
    histórico, com semente fixa: roda sempre igual, e é uma amostra plausível
    do mundo real. Recebimentos não confirmados atrasam 4 dias, o meio da faixa
    documentada.

    O que ele NÃO é: o gabarito. O trânsito realizado das janelas de teste está
    lacrado com os organizadores. Seu score local é uma estimativa honesta, não
    a nota — espere alguns pontos de diferença para cima ou para baixo.
    """
    import random as _random
    amostras = defaultdict(list)
    regiao_da_linha = {r["order_line_id"]: r["ship_to_region"]
                       for r in ler_csv(f"{dados.pasta}/orders_history.csv")}
    for r in ler_csv(f"{dados.pasta}/historical_deliveries.csv"):
        if not r["transit_days_actual"]:
            continue
        reg = regiao_da_linha.get(r["order_line_id"])
        if reg:
            amostras[(r["dc_id"], reg)].append(int(r["transit_days_actual"]))

    transito = []
    for janela in ("public", "private"):
        ini, fim = horizonte_simulacao(janela)
        d = ini
        while d <= fim:
            for (cd, reg) in dados.lanes:
                pool = amostras.get((cd, reg))
                rng = _random.Random(f"{seed}|{janela}|{cd}|{reg}|{d.isoformat()}")
                dias = (rng.choice(pool) if pool else dados.transito(cd, reg))
                transito.append(dict(window=janela, dc_id=cd, region=reg,
                                     ship_date=d.isoformat(),
                                     transit_days_actual=dias))
            d += timedelta(days=1)

    inbound = []
    for r in dados.inbound:
        if r["eta_date"] <= P.HIST_FIM.isoformat():
            continue
        eta = date.fromisoformat(r["eta_date"])
        real = eta if r["confirmed"] == "1" else eta + timedelta(days=4)
        inbound.append(dict(receipt_id=r["receipt_id"], dc_id=r["dc_id"], sku=r["sku"],
                            qty=r["qty"], eta_planned=r["eta_date"],
                            eta_actual=real.isoformat(), confirmed=r["confirmed"]))
    return dict(transito=transito, inbound=inbound, oficial=False)


def carregar_gabarito(pasta, dados):
    """Usa o gabarito oficial se ele estiver presente; senão, o oráculo de treino."""
    t = os.path.join(pasta, "realized_transit.csv")
    i = os.path.join(pasta, "realized_inbound.csv")
    if os.path.exists(t) and os.path.exists(i):
        return dict(transito=ler_csv(t), inbound=ler_csv(i), oficial=True)
    return gabarito_de_treino(dados)


def rodar(dados, pasta_sub, janela, gabarito, silencioso=False):
    res = Resultado()
    promessas = ler_csv(f"{pasta_sub}/submission_promise.csv")
    arq_reb = f"{pasta_sub}/submission_rebalance.csv"
    transferencias = ler_csv(arq_reb) if os.path.exists(arq_reb) else []
    linhas = dados.pedidos(janela)

    validar_formato(dados, promessas, transferencias, linhas, res)
    if not res.valida:
        return res, None, None
    resultados, custo, ocupacao = simular(dados, promessas, transferencias, linhas,
                                          gabarito, janela, res)
    if not res.valida:
        return res, None, None
    m = metricas(dados, linhas, promessas, resultados, custo, res, ocupacao)
    pinball = avaliar_previsao(dados, f"{pasta_sub}/submission_forecast.csv", gabarito, janela)
    m["pinball_lead_time"] = pinball
    return res, m, pinball


def main():
    ap = argparse.ArgumentParser(description="Avaliador oficial do desafio")
    ap.add_argument("--submissao", required=True, help="pasta com submission_promise.csv")
    ap.add_argument("--janela", choices=["public", "private"], default="public")
    ap.add_argument("--dados", default=None)
    ap.add_argument("--gabarito", default=GABARITO_PADRAO)
    ap.add_argument("--baseline", default="desafio/submissoes/baseline")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    dados = Dados(args.dados) if args.dados else Dados()
    gabarito = carregar_gabarito(args.gabarito, dados)

    arq = os.path.join(args.submissao, "submission_promise.csv")
    if not os.path.exists(arq):
        print(f"Não encontrei {arq}")
        print()
        print("  --submissao aponta para a PASTA que contém submission_promise.csv.")
        print("  Exemplo:")
        print("    python desafio/ferramentas/avaliar.py \\")
        print("      --submissao desafio/submissoes/baseline/public --janela public")
        print()
        print("  Não tem uma submissão ainda? Gere a do baseline:")
        print("    python desafio/ferramentas/baseline_guloso.py --janela public")
        sys.exit(2)

    res, m, pinball = rodar(dados, args.submissao, args.janela, gabarito)
    if not res.valida:
        print("SUBMISSÃO REPROVADA\n")
        for e in res.erros[:25]:
            print("  " + e)
        if len(res.erros) > 25:
            print(f"  ... e mais {len(res.erros) - 25} erros")
        sys.exit(1)

    ref = None
    caminho_base = os.path.join(args.baseline, args.janela)
    if os.path.exists(f"{caminho_base}/submission_promise.csv") and \
            os.path.abspath(caminho_base) != os.path.abspath(args.submissao):
        _r, ref, _p = rodar(dados, caminho_base, args.janela, gabarito, silencioso=True)

    saida = dict(janela=args.janela, valida=True,
                 modo="oficial" if gabarito.get("oficial") else "treino",
                 metricas=m, avisos=res.avisos)
    if ref:
        saida["baseline"] = {k: ref[k] for k in
                             ("promise_reliability", "otif", "fill_rate_valor", "custo_total")}
        saida["score"] = pontuar(m, ref, pinball)

    if args.json:
        print(json.dumps(saida, indent=2, ensure_ascii=False, default=str))
        return

    modo = "OFICIAL" if gabarito.get("oficial") else "TREINO"
    print(f"SUBMISSÃO VÁLIDA — janela {args.janela} · modo {modo}")
    print()
    if modo == "TREINO":
        print("  Gabarito oficial ausente: o trânsito realizado foi sorteado da")
        print("  distribuição histórica com semente fixa. Roda sempre igual e é uma")
        print("  amostra plausível — mas NÃO é a nota. Espere alguns pontos de")
        print("  diferença, para cima ou para baixo.")
        print()
    print(f"  linhas avaliadas ........... {m['linhas']}")
    print(f"  Promise Reliability ........ {m['promise_reliability']:6.1%}   meta ≥ 96%")
    print(f"  OTIF (vs. data do cliente) . {m['otif']:6.1%}   meta ≥ 95%")
    print(f"  OTIF Key Account ........... {m['otif_ka']:6.1%}   meta ≥ 98%")
    print(f"  In Full .................... {m['in_full']:6.1%}   meta ≥ 97%")
    print(f"  Fill Rate (valor) .......... {m['fill_rate_valor']:6.1%}   meta ≥ 96%")
    print(f"  Promise Tightness .......... {m['promise_tightness']:6.2f} d  meta ≤ 1,5")
    print(f"  Aderência ao CD primário ... {m['aderencia_cd_primario']:6.1%}   meta ≥ 85%")
    print(f"  Ocupação média do veículo .. {m['ocupacao_media_veiculo']:6.1%}   meta ≥ 80%")
    print(f"  Custo logístico / receita .. {m['custo_logistico_pct']:6.1%}   meta ≤ 8,5%")
    print(f"\n  Fill rate por segmento (piso {P.FILL_RATE_PISO_SEGMENTO:.0%}):")
    for s, v in sorted(m["fill_rate_por_segmento"].items()):
        print(f"    {s:4s} {v:6.1%}")
    print(f"\n  Custo total: R$ {m['custo_total']:,.2f}")
    for k, v in m["custo_detalhado"].items():
        print(f"    {k:24s} R$ {v:>14,.2f}")
    if pinball is not None:
        print(f"\n  Pinball loss lead time: {pinball:.3f}")
    if "score" in saida:
        sc = saida["score"]
        print(f"\n  SCORE: {sc['total']:.2f} / {sc['maximo_automatico']:.0f} pontos automáticos")
        for k, v in sc["componentes"].items():
            print(f"    {k:22s} {v:6.2f}")
        if sc["penalidades"]:
            print(f"    penalidades          {sc['penalidades']}")
        print(f"  {sc['nota']}")
    for a in res.avisos[:10]:
        print("  aviso " + a)


if __name__ == "__main__":
    main()
