"""
Gerador do pacote de dados do Desafio Supply Chain.

Determinístico: mesma seed, mesmos arquivos, mesmos checksums.
Sem dependências externas — apenas biblioteca padrão do Python.

Uso:
    python desafio/gerador/gerar_dados.py
    python desafio/gerador/gerar_dados.py --seed 42 --saida desafio/dados/v1.0.0
"""

import argparse
import csv
import hashlib
import math
import os
import random
import sys
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parametros as P  # noqa: E402

# Console do Windows costuma abrir em cp1252 e quebra em acento e em "≥".
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass



# ====================================================================
# Calendário
# ====================================================================

def _feriados_por_regiao():
    mapa = defaultdict(set)
    for iso, _nome, escopo in P.FERIADOS:
        d = date.fromisoformat(iso)
        alvos = P.REGIOES if escopo == "ALL" else [escopo]
        for r in alvos:
            mapa[r].add(d)
    return mapa


FERIADOS_REGIAO = _feriados_por_regiao()


def dia_util_regiao(d, regiao):
    """Região opera de segunda a sexta, exceto feriados."""
    return d.weekday() < 5 and d not in FERIADOS_REGIAO[regiao]


def dia_util_cd(d, cd):
    """CD-SP e CD-PR operam também aos sábados (BR-102)."""
    limite = 6 if P.CDS[cd]["sabado_util"] else 5
    return d.weekday() < limite and d not in FERIADOS_REGIAO[P.CDS[cd]["regiao"]]


def proximo_dia_util_cd(d, cd):
    while not dia_util_cd(d, cd):
        d += timedelta(days=1)
    return d


def somar_dias_uteis(d, n, regiao):
    """Avança n dias úteis da região a partir de d."""
    atual = d
    restantes = n
    while restantes > 0:
        atual += timedelta(days=1)
        if dia_util_regiao(atual, regiao):
            restantes -= 1
    return atual


def intervalo(inicio, fim):
    d = inicio
    while d <= fim:
        yield d
        d += timedelta(days=1)


def inicio_semana(d):
    return d - timedelta(days=d.weekday())


# ====================================================================
# Demanda
# ====================================================================

def demanda_diaria_plano(d, sku, regiao):
    """Demanda esperada (plano) — sem ruído. É o forecast."""
    cfg = P.SKUS[sku]
    base_mes = cfg["demanda_mes"]
    saz = P.SAZONALIDADE[sku].get(d.month, 1.0)
    meses = (d.year - P.HIST_INICIO.year) * 12 + (d.month - P.HIST_INICIO.month)
    tend = (1.0 + P.CRESCIMENTO_MES[regiao]) ** meses
    dia = P.FATOR_DIA_SEMANA[d.weekday()]
    if not dia_util_regiao(d, regiao):
        return 0.0
    # 21,7 dias úteis médios por mês
    return base_mes * saz * tend * P.SHARE_REGIAO[regiao] * dia / 21.7


# Choques de demanda NÃO capturados pelo plano. É o que faz o consumo de
# forecast estourar 110% (BR-701) e o que gera a escassez do desafio.
CHOQUES = []


def gerar_choques(seed):
    """Eventos determinísticos de demanda fora do plano."""
    r = random.Random(seed + 991)
    eventos = []
    janelas = [
        (date(2025, 10, 6), 3), (date(2025, 11, 10), 2), (date(2026, 1, 19), 2),
        (date(2026, 3, 9), 2), (date(2026, 4, 20), 3), (date(2026, 6, 8), 2),
        (date(2026, 7, 13), 2), (date(2026, 8, 10), 2),
        # dois choques dentro das janelas de teste — é onde o desafio acontece
        (P.PUB_INICIO, 2), (P.PRI_INICIO + timedelta(days=3), 2),
    ]
    skus = list(P.SKUS)
    for inicio, semanas in janelas:
        sku = r.choice(skus)
        reg = r.choices(P.REGIOES, weights=[P.SHARE_REGIAO[x] for x in P.REGIOES], k=1)[0]
        eventos.append(dict(sku=sku, region=reg, inicio=inicio,
                            fim=inicio + timedelta(days=7 * semanas - 1),
                            fator=round(r.uniform(1.45, 2.30), 2)))
    return eventos


def fator_choque(d, sku, regiao):
    f = 1.0
    for e in CHOQUES:
        if e["sku"] == sku and e["region"] == regiao and e["inicio"] <= d <= e["fim"]:
            f *= e["fator"]
    return f


def demanda_diaria_real(rng, d, sku, regiao):
    """Demanda realizada — plano com ruído log-normal e choques fora do plano."""
    plano = demanda_diaria_plano(d, sku, regiao)
    if plano <= 0:
        return 0
    sigma = P.SIGMA_DEMANDA[sku]
    ruido = math.exp(rng.gauss(-0.5 * sigma * sigma, sigma))
    return max(0, int(round(plano * ruido * fator_choque(d, sku, regiao))))


# ====================================================================
# Cadastros
# ====================================================================

def gerar_clientes(rng):
    clientes = []
    seq = 0
    for seg, cfg in P.SEGMENTOS.items():
        n = cfg["n_clientes"]
        # KA concentra no Sudeste; demais seguem a distribuição de demanda
        if seg == "KA":
            pesos = {"SE": 0.58, "S": 0.17, "CO": 0.08, "NE": 0.15, "N": 0.02}
        else:
            pesos = P.SHARE_REGIAO
        regioes = list(pesos.keys())
        probs = [pesos[r] for r in regioes]
        for _ in range(n):
            seq += 1
            reg = rng.choices(regioes, weights=probs, k=1)[0]
            sla = cfg["sla_horas_se_s"] if reg in ("SE", "S") else cfg["sla_horas_outras"]
            # fator de porte: distribuição de Pareto suave
            porte = round(rng.paretovariate(1.6), 3)
            clientes.append(dict(
                customer_id=f"C-{seq:05d}",
                segment=seg,
                region=reg,
                sla_hours=sla,
                full_order_required=cfg["pedido_completo"],
                penalty_pct=cfg["multa_pct"],
                priority_weight=cfg["prioridade"],
                scheduled_window=1 if seg == "KA" else 0,
                size_factor=min(porte, 12.0),
            ))
    return clientes


# ====================================================================
# Pedidos
# ====================================================================

def lote_minimo(seg, sku):
    """Granularidade de compra do segmento para o SKU (BR-104)."""
    un_pal = P.SKUS[sku]["un_palete"]
    modo = P.SEGMENTOS[seg]["lote"]
    if modo == "palete":
        return un_pal
    if modo == "camada":
        return max(1, un_pal // 4)
    return 6


def tamanho_linha(rng, seg, sku):
    """Quantidade da linha, respeitando o lote do segmento (BR-104)."""
    un_pal = P.SKUS[sku]["un_palete"]
    cfg = P.SEGMENTOS[seg]
    lo, hi = cfg["paletes_linha"]
    if cfg["lote"] in ("palete", "camada"):
        lote = lote_minimo(seg, sku)
        n = rng.choices(range(lo, hi + 1),
                        weights=[2 ** (hi - k) for k in range(lo, hi + 1)], k=1)[0]
        return n * lote
    # ECM: fração livre do palete
    frac = rng.uniform(0.06, 0.28)
    return max(6, int(round(un_pal * frac / 6)) * 6)


def gerar_pedidos(rng, clientes, dt_inicio, dt_fim, seq_inicial=1):
    """Converte a demanda diária realizada em linhas de pedido agrupadas."""
    por_seg_regiao = defaultdict(list)
    for c in clientes:
        por_seg_regiao[(c["segment"], c["region"])].append(c)

    linhas_por_chave = defaultdict(list)   # (customer_id, data) -> [linha]
    # Resíduo acumulado por (sku, região, segmento): segmentos que compram em
    # palete não pedem todo dia — acumulam até fechar o lote. Sem isso, a
    # demanda de KA e DIS seria sistematicamente subalocada.
    residuo = defaultdict(float)
    for d in intervalo(dt_inicio, dt_fim):
        for sku in P.SKUS:
            for reg in P.REGIOES:
                total = demanda_diaria_real(rng, d, sku, reg)
                if total <= 0:
                    continue
                for seg, share in P.SHARE_SEGMENTO[sku].items():
                    pool = por_seg_regiao.get((seg, reg))
                    if not pool:
                        continue
                    chave = (sku, reg, seg)
                    residuo[chave] += total * share
                    lote = lote_minimo(seg, sku)
                    pesos = [c["size_factor"] for c in pool]
                    guarda = 0
                    while residuo[chave] >= lote and guarda < 400:
                        guarda += 1
                        q = tamanho_linha(rng, seg, sku)
                        if q > residuo[chave]:
                            q = int(residuo[chave] // lote) * lote
                        if q < lote:
                            break
                        cliente = rng.choices(pool, weights=pesos, k=1)[0]
                        linhas_por_chave[(cliente["customer_id"], d)].append((sku, q))
                        residuo[chave] -= q

    idx = {c["customer_id"]: c for c in clientes}
    pedidos, linhas = [], []
    seq_pedido = seq_inicial
    seq_linha = seq_inicial
    for (cid, d) in sorted(linhas_por_chave.keys(), key=lambda k: (k[1], k[0])):
        itens = linhas_por_chave[(cid, d)]
        # consolida linhas repetidas do mesmo SKU
        agreg = defaultdict(int)
        for sku, q in itens:
            agreg[sku] += q
        cliente = idx[cid]
        oid = f"ORD-{seq_pedido:06d}"
        seq_pedido += 1
        hora = rng.choices([9, 11, 13, 15, 17, 19], weights=[18, 22, 20, 18, 14, 8], k=1)[0]
        minuto = rng.randrange(0, 60)
        order_ts = f"{d.isoformat()}T{hora:02d}:{minuto:02d}:00"
        sla_dias = math.ceil(cliente["sla_hours"] / 24)
        requested = somar_dias_uteis(d, sla_dias, cliente["region"])
        pedidos.append(dict(order_id=oid, customer_id=cid, order_ts=order_ts,
                            order_date=d.isoformat(), requested_date=requested.isoformat(),
                            ship_to_region=cliente["region"],
                            channel=rng.choice(P.CANAIS[cliente["segment"]]),
                            segment=cliente["segment"]))
        for sku, q in sorted(agreg.items()):
            linhas.append(dict(
                order_id=oid, order_line_id=f"OL-{seq_linha:07d}",
                customer_id=cid, sku=sku, qty=q, order_ts=order_ts,
                order_date=d.isoformat(), requested_date=requested.isoformat(),
                ship_to_region=cliente["region"],
                channel=pedidos[-1]["channel"], segment=cliente["segment"],
                valor=round(q * P.SKUS[sku]["valor"], 2),
            ))
            seq_linha += 1
    return pedidos, linhas


# ====================================================================
# Suprimento e estoque
# ====================================================================

def planta_para(sku, cd):
    """Planta que produz o SKU com menor trânsito até o CD."""
    candidatas = [p for p, cfg in P.PLANTAS.items() if sku in cfg["skus"]]
    return min(candidatas, key=lambda p: P.TRANSITO_SUPRIMENTO[(p, cd)])


def demanda_media_diaria(cd, sku, ref, janela=28):
    """
    Demanda de plano prospectiva das regiões atendidas pelo CD.
    Olhar para a frente é o que permite a rede antecipar o pico sazonal —
    e o que faz a capacidade da planta virar restrição de verdade.
    """
    regioes = [r for r, c in P.CD_PRIMARIO.items() if c == cd]
    total = 0.0
    for i in range(janela):
        d = ref + timedelta(days=i)
        for r in regioes:
            total += demanda_diaria_plano(d, sku, r)
    return total / max(1, janela)


def simular_historico(rng, linhas_hist):
    """
    Roda a política de estoque vigente sobre o histórico:
    reposição semanal, sourcing baseline, expedição e entrega.
    Devolve snapshots diários, recebimentos e entregas realizadas.
    """
    estoque = defaultdict(int)          # (cd, sku) -> unidades
    em_transito = defaultdict(int)      # (cd, sku) -> unidades a caminho
    chegadas = defaultdict(list)        # data -> [(cd, sku, qty, receipt_id)]
    lote_mais_antigo = {}               # (cd, sku) -> data do lote mais antigo

    # estoque inicial: cobertura alvo do CD
    for cd, cfg in P.CDS.items():
        for sku in P.SKUS:
            dm = demanda_media_diaria(cd, sku, P.HIST_INICIO)
            estoque[(cd, sku)] = int(round(dm * cfg["cobertura_alvo"] * rng.uniform(0.85, 1.15)))
            lote_mais_antigo[(cd, sku)] = P.HIST_INICIO - timedelta(days=rng.randrange(5, 25))

    linhas_por_data = defaultdict(list)
    for ln in linhas_hist:
        linhas_por_data[date.fromisoformat(ln["order_date"])].append(ln)

    snapshots, recebimentos, entregas, transito_real = [], [], [], []
    seq_receipt = 1
    reservado_ka = defaultdict(int)
    producao_mes = defaultdict(int)     # (planta, ano, mês) -> unidades comprometidas
    pendentes = []                      # backorders em aberto
    MAX_DIAS_BACKORDER = 10

    def solicitar_producao(planta, sku, cd, qty, d):
        """Aplica a capacidade mensal da planta; devolve a quantidade liberada."""
        chave = (planta, d.year, d.month)
        livre = P.PLANTAS[planta]["capacidade_mes"] - producao_mes[chave]
        if livre <= 0:
            return 0
        un_pal = P.SKUS[sku]["un_palete"]
        liberado = min(qty, (livre // un_pal) * un_pal)
        producao_mes[chave] += liberado
        return liberado

    def registrar_recebimento(cd, sku, qty, planta, d):
        nonlocal seq_receipt
        eta = d + timedelta(days=2 + P.TRANSITO_SUPRIMENTO[(planta, cd)])
        qty_real = qty
        # ruptura de suprimento no histórico: atraso e corte de quantidade
        if rng.random() < 0.07:
            eta += timedelta(days=rng.randrange(2, 7))
        if rng.random() < 0.04:
            un_pal = P.SKUS[sku]["un_palete"]
            qty_real = max(un_pal, int(qty * rng.uniform(0.70, 0.88) / un_pal) * un_pal)
        rid = f"RCP-{seq_receipt:06d}"
        seq_receipt += 1
        chegadas[eta].append((cd, sku, qty_real, rid))
        em_transito[(cd, sku)] += qty_real
        recebimentos.append(dict(receipt_id=rid, plant_id=planta, dc_id=cd, sku=sku,
                                 qty=qty_real, order_date=d.isoformat(),
                                 eta_date=eta.isoformat(), confirmed=1))

    def escolher_cd(sku, qty, regiao):
        """Baseline: CD primário se tiver saldo; senão o CD com maior estoque."""
        primario = P.CD_PRIMARIO[regiao]
        if estoque[(primario, sku)] >= qty:
            return primario
        alternativo = max(P.CDS, key=lambda c: estoque[(c, sku)])
        return alternativo if estoque[(alternativo, sku)] >= qty else primario

    def fechar_linha(item, cd, enviado, d):
        regiao = item["ln"]["ship_to_region"]
        transito_p50 = P.TRANSITO_DISTRIBUICAO[cd][regiao]
        prob_atraso, atraso_max = P.VARIABILIDADE_LANE[regiao]
        atraso = rng.randrange(1, atraso_max + 1) if rng.random() < prob_atraso else 0
        transito_dias = transito_p50 + atraso
        entrega = somar_dias_uteis(d, transito_dias, regiao)
        # a promessa foi feita na liberação original, com o buffer do baseline
        prometida = somar_dias_uteis(
            item["liberacao"],
            P.TRANSITO_DISTRIBUICAO[item["cd_original"]][regiao] + P.BUFFER_BASELINE,
            regiao)
        qty = item["ln"]["qty"]
        entregas.append(dict(
            order_line_id=item["ln"]["order_line_id"], order_id=item["ln"]["order_id"],
            dc_id=cd, sku=item["ln"]["sku"], qty_ordered=qty, qty_shipped=enviado,
            ship_date=d.isoformat(), promised_date=prometida.isoformat(),
            actual_delivery_date=entrega.isoformat() if enviado > 0 else "",
            transit_days_actual=transito_dias if enviado > 0 else "",
            promise_revisions=1 if item["dias_espera"] > 0 else 0,
            backorder_days=item["dias_espera"],
            on_time=1 if (enviado > 0 and entrega <= prometida) else 0,
            in_full=1 if enviado >= qty else 0))
        if enviado > 0:
            transito_real.append(dict(dc_id=cd, region=regiao, ship_date=d.isoformat(),
                                      transit_days_actual=transito_dias))

    for d in intervalo(P.HIST_INICIO, P.HIST_FIM):
        # --- chegadas do dia
        for (cd, sku, qty, rid) in chegadas.pop(d, []):
            estoque[(cd, sku)] += qty
            em_transito[(cd, sku)] -= qty
            lote_mais_antigo[(cd, sku)] = d

        # --- reposição semanal (segunda-feira), limitada pela capacidade da planta
        if d.weekday() == 0:
            pedidos_reposicao = []
            for cd, cfg in P.CDS.items():
                for sku in P.SKUS:
                    dm = demanda_media_diaria(cd, sku, d)
                    alvo = dm * cfg["cobertura_alvo"]
                    posicao = estoque[(cd, sku)] + em_transito[(cd, sku)]
                    if posicao >= alvo * 0.92:
                        continue
                    un_pal = P.SKUS[sku]["un_palete"]
                    paletes = max(1, int(round((alvo - posicao) / un_pal)))
                    pedidos_reposicao.append((cd, sku, paletes * un_pal,
                                              posicao / max(1.0, dm)))
            # menor cobertura primeiro: a capacidade escassa vai para quem precisa
            for cd, sku, qty, _cob in sorted(pedidos_reposicao, key=lambda x: x[3]):
                planta = planta_para(sku, cd)
                liberado = solicitar_producao(planta, sku, cd, qty, d)
                if liberado > 0:
                    registrar_recebimento(cd, sku, liberado, planta, d)
                # capacidade esgotada na planta preferida: tenta a alternativa
                if liberado < qty:
                    for alt in [p for p, c in P.PLANTAS.items()
                                if sku in c["skus"] and p != planta]:
                        extra = solicitar_producao(alt, sku, cd, qty - liberado, d)
                        if extra > 0:
                            registrar_recebimento(cd, sku, extra, alt, d)
                            liberado += extra

        # --- fila do dia: backorders primeiro, depois pedidos novos
        novos = []
        for ln in linhas_por_data.get(d, []):
            hora = int(ln["order_ts"][11:13])
            liberacao = d + timedelta(days=1) if hora >= 18 else d       # BR-101
            cd0 = P.CD_PRIMARIO[ln["ship_to_region"]]
            liberacao = proximo_dia_util_cd(liberacao, cd0)
            novos.append(dict(ln=ln, liberacao=liberacao, cd_original=cd0,
                              dias_espera=0, entrada=liberacao))

        fila = pendentes + [n for n in novos if n["liberacao"] <= d]
        adiados = [n for n in novos if n["liberacao"] > d]
        fila.sort(key=lambda x: (P.SEGMENTOS[x["ln"]["segment"]]["prioridade"],
                                 -x["dias_espera"], x["ln"]["order_line_id"]))

        pendentes = list(adiados)
        for item in fila:
            ln = item["ln"]
            sku, qty, regiao = ln["sku"], ln["qty"], ln["ship_to_region"]
            cd = escolher_cd(sku, qty, regiao)
            if estoque[(cd, sku)] >= qty:
                estoque[(cd, sku)] -= qty
                fechar_linha(item, cd, qty, d)
                continue
            item["dias_espera"] += 1
            if item["dias_espera"] < MAX_DIAS_BACKORDER:
                pendentes.append(item)
                continue
            # esgotou o prazo de backorder: parcial quando o segmento permite
            aceita_parcial = ln["segment"] in ("VAR", "ECM") and \
                P.SKUS[sku]["allow_partial"] == 1
            enviado = min(qty, max(0, estoque[(cd, sku)])) if aceita_parcial else 0
            estoque[(cd, sku)] -= enviado
            fechar_linha(item, cd, enviado, d)

        # --- snapshot do fim do dia
        for cd in P.CDS:
            for sku in P.SKUS:
                dm = max(1.0, demanda_media_diaria(cd, sku, d))
                ka_share = P.SHARE_SEGMENTO[sku]["KA"]
                reservado_ka[(cd, sku)] = int(round(dm * ka_share * P.DIAS_RESERVA_KA))
                snapshots.append(dict(
                    date=d.isoformat(), dc_id=cd, sku=sku,
                    on_hand=max(0, estoque[(cd, sku)]),
                    reserved_ka=reservado_ka[(cd, sku)],
                    in_transit=max(0, em_transito[(cd, sku)]),
                    oldest_batch_date=lote_mais_antigo[(cd, sku)].isoformat()))

    util = defaultdict(float)
    for (planta, ano, mes), q in producao_mes.items():
        util[(ano, mes)] += q
    cap = sum(c['capacidade_mes'] for c in P.PLANTAS.values())
    piores = sorted(util.items(), key=lambda kv: -kv[1])[:4]
    print('      utilizacao de planta (top meses): ' +
          ', '.join(f'{a}-{m:02d} {q/cap:.0%}' for (a, m), q in piores))
    return snapshots, recebimentos, entregas, transito_real, estoque, em_transito, chegadas


def planejar_recebimentos_futuros(estoque, em_transito, chegadas, seq_inicial):
    """
    Estende o plano de reposição para o horizonte de teste.
    Recebimentos até 14 dias após o corte são confirmados (BR-402);
    além disso, entram como não confirmados (BR-403).
    """
    futuros = []
    seq = seq_inicial
    est = dict(estoque)
    trans = dict(em_transito)
    # Um recebimento é confirmado quando a ordem de reposição já foi colocada e a
    # produção está firme. Ordens disparadas até 3 semanas após o corte entram
    # como firmes; o que for planejado depois disso ainda é intenção (BR-403).
    limite_pedido_firme = P.HIST_FIM + timedelta(days=21)
    fim = P.PRI_FIM + timedelta(days=7)

    # recebimentos já em trânsito que chegam depois do corte
    for eta, itens in sorted(chegadas.items()):
        if eta > P.HIST_FIM:
            for (cd, sku, qty, rid) in itens:
                futuros.append(dict(receipt_id=rid, plant_id=planta_para(sku, cd),
                                    dc_id=cd, sku=sku, qty=qty,
                                    order_date=(eta - timedelta(days=6)).isoformat(),
                                    eta_date=eta.isoformat(),
                                    confirmed=1))   # já estava em trânsito no corte

    d = P.HIST_FIM + timedelta(days=1)
    while d <= fim:
        if d.weekday() == 0:
            for cd, cfg in P.CDS.items():
                for sku in P.SKUS:
                    dm = demanda_media_diaria(cd, sku, d)
                    alvo = dm * cfg["cobertura_alvo"]
                    posicao = est.get((cd, sku), 0) + trans.get((cd, sku), 0)
                    if posicao >= alvo * 0.92:
                        continue
                    un_pal = P.SKUS[sku]["un_palete"]
                    paletes = max(1, int(round((alvo - posicao) / un_pal)))
                    qty = paletes * un_pal
                    planta = planta_para(sku, cd)
                    eta = d + timedelta(days=2 + P.TRANSITO_SUPRIMENTO[(planta, cd)])
                    seq += 1
                    trans[(cd, sku)] = trans.get((cd, sku), 0) + qty
                    futuros.append(dict(
                        receipt_id=f"RCP-{seq:06d}", plant_id=planta, dc_id=cd, sku=sku,
                        qty=qty, order_date=d.isoformat(), eta_date=eta.isoformat(),
                        confirmed=1 if d <= limite_pedido_firme else 0))
            # consumo aproximado da semana, para não inflar o plano
            for cd in P.CDS:
                for sku in P.SKUS:
                    dm = demanda_media_diaria(cd, sku, d)
                    est[(cd, sku)] = max(0, est.get((cd, sku), 0) - int(dm * 5))
        d += timedelta(days=1)
    return futuros


# ====================================================================
# Escrita
# ====================================================================

def escrever_csv(caminho, colunas, linhas):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        # LF em qualquer sistema. Sem isto o Windows grava CRLF, o git
        # normaliza para LF ao versionar, e a conferência de checksum falha
        # para quem baixa em macOS ou Linux — foi o que o CI acusou.
        w = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore",
                           lineterminator="\n")
        w.writeheader()
        for ln in linhas:
            w.writerow(ln)
    return len(linhas)


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


# ====================================================================
# Principal
# ====================================================================

def main():
    ap = argparse.ArgumentParser(description="Gera o pacote de dados do desafio")
    ap.add_argument("--seed", type=int, default=P.SEED)
    ap.add_argument("--saida", default="desafio/dados/v" + P.VERSAO)
    ap.add_argument("--privado", default="desafio/privado")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    globals()["CHOQUES"] = gerar_choques(args.seed)
    print(f"      choques de demanda fora do plano: {len(CHOQUES)}")
    out, priv = args.saida, args.privado
    os.makedirs(out, exist_ok=True)
    os.makedirs(priv, exist_ok=True)
    stats = {}

    print(f"[1/8] Cadastros (seed={args.seed})")
    clientes = gerar_clientes(rng)
    stats["customer_master.csv"] = escrever_csv(
        f"{out}/customer_master.csv",
        ["customer_id", "segment", "region", "sla_hours", "full_order_required",
         "penalty_pct", "priority_weight", "scheduled_window", "size_factor"], clientes)

    skus = [dict(sku=k, description=v["descricao"], abc_class=v["classe"],
                 unit_weight_kg=v["peso"], unit_volume_m3=v["volume"],
                 unit_value=v["valor"], units_per_pallet=v["un_palete"],
                 shelf_life_days=v["shelf_life"], allow_partial=v["allow_partial"],
                 monthly_demand_units=v["demanda_mes"])
            for k, v in P.SKUS.items()]
    stats["sku_master.csv"] = escrever_csv(
        f"{out}/sku_master.csv",
        ["sku", "description", "abc_class", "unit_weight_kg", "unit_volume_m3",
         "unit_value", "units_per_pallet", "shelf_life_days", "allow_partial",
         "monthly_demand_units"], skus)

    cds = [dict(dc_id=k, name=v["nome"], region=v["regiao"],
                pallet_capacity=v["capacidade_paletes"],
                daily_pallet_throughput=P.CAPACIDADE_DIARIA_PALETES[k],
                cutoff_local_time=v["cutoff"], saturday_operating=v["sabado_util"],
                target_coverage_days=v["cobertura_alvo"])
           for k, v in P.CDS.items()]
    stats["dc_master.csv"] = escrever_csv(
        f"{out}/dc_master.csv",
        ["dc_id", "name", "region", "pallet_capacity", "daily_pallet_throughput",
         "cutoff_local_time", "saturday_operating", "target_coverage_days"], cds)

    plantas = [dict(plant_id=k, name=v["nome"], region=v["regiao"],
                    skus_produced="|".join(v["skus"]), monthly_capacity_units=v["capacidade_mes"])
               for k, v in P.PLANTAS.items()]
    stats["plant_master.csv"] = escrever_csv(
        f"{out}/plant_master.csv",
        ["plant_id", "name", "region", "skus_produced", "monthly_capacity_units"], plantas)

    lanes = []
    for cd, mapa in P.TRANSITO_DISTRIBUICAO.items():
        for r, t in mapa.items():
            base = P.TRANSITO_DISTRIBUICAO[P.CD_PRIMARIO[r]][r]
            tarifa = P.TARIFA_KG[r] * (1 + P.ACRESCIMO_POR_DIA_EXTRA * max(0, t - base))
            lanes.append(dict(dc_id=cd, region=r, transit_days=t,
                              rate_per_kg=round(tarifa, 4),
                              is_primary=1 if P.CD_PRIMARIO[r] == cd else 0))
    stats["lanes.csv"] = escrever_csv(
        f"{out}/lanes.csv", ["dc_id", "region", "transit_days", "rate_per_kg", "is_primary"], lanes)

    transf = []
    for (a, b), km in P.DISTANCIA_KM.items():
        t = P.TRANSITO_SUPRIMENTO[(a, b)]
        transf.append(dict(origin=a, dest=b, distance_km=km, transit_days=t,
                           pallets_per_truck=P.VEICULO_TRANSFERENCIA["paletes"],
                           fixed_cost=P.FRETE_TRANSF_FIXO,
                           cost_per_km=P.FRETE_TRANSF_KM))
        if a.startswith("CD"):
            transf.append(dict(origin=b, dest=a, distance_km=km, transit_days=t,
                               pallets_per_truck=P.VEICULO_TRANSFERENCIA["paletes"],
                               fixed_cost=P.FRETE_TRANSF_FIXO,
                               cost_per_km=P.FRETE_TRANSF_KM))
    stats["transfer_lanes.csv"] = escrever_csv(
        f"{out}/transfer_lanes.csv",
        ["origin", "dest", "distance_km", "transit_days", "pallets_per_truck",
         "fixed_cost", "cost_per_km"], transf)

    veiculos = [
        dict(vehicle_type="TRANSFERENCIA", pallets=P.VEICULO_TRANSFERENCIA["paletes"],
             max_weight_kg=P.VEICULO_TRANSFERENCIA["peso_kg"],
             max_volume_m3=P.VEICULO_TRANSFERENCIA["volume_m3"], min_occupancy=1.0),
        dict(vehicle_type="DISTRIBUICAO", pallets=P.VEICULO_DISTRIBUICAO["paletes"],
             max_weight_kg=P.VEICULO_DISTRIBUICAO["peso_kg"],
             max_volume_m3=P.VEICULO_DISTRIBUICAO["volume_m3"],
             min_occupancy=P.OCUPACAO_MINIMA_VEICULO),
    ]
    stats["vehicles.csv"] = escrever_csv(
        f"{out}/vehicles.csv",
        ["vehicle_type", "pallets", "max_weight_kg", "max_volume_m3", "min_occupancy"], veiculos)

    feriados = []
    for d in intervalo(P.HIST_INICIO, P.PRI_FIM + timedelta(days=30)):
        for r in P.REGIOES:
            nome = ""
            for iso, n, escopo in P.FERIADOS:
                if date.fromisoformat(iso) == d and (escopo == "ALL" or escopo == r):
                    nome = n
            feriados.append(dict(date=d.isoformat(), region=r,
                                 is_business_day=1 if dia_util_regiao(d, r) else 0,
                                 holiday_name=nome))
    stats["holidays_calendar.csv"] = escrever_csv(
        f"{out}/holidays_calendar.csv", ["date", "region", "is_business_day", "holiday_name"], feriados)

    print("[2/8] Pedidos históricos")
    ped_hist, lin_hist = gerar_pedidos(rng, clientes, P.HIST_INICIO, P.HIST_FIM, 1)
    cols_ordem = ["order_id", "order_line_id", "customer_id", "sku", "qty", "order_ts",
                  "requested_date", "ship_to_region", "channel", "segment"]
    stats["orders_history.csv"] = escrever_csv(f"{out}/orders_history.csv", cols_ordem, lin_hist)

    print("[3/8] Simulação do histórico (política vigente)")
    (snapshots, recebimentos, entregas, transito_real,
     estoque_final, transito_final, chegadas_pendentes) = simular_historico(rng, lin_hist)

    stats["inventory_snapshot.csv"] = escrever_csv(
        f"{out}/inventory_snapshot.csv",
        ["date", "dc_id", "sku", "on_hand", "reserved_ka", "in_transit", "oldest_batch_date"],
        snapshots)
    stats["historical_deliveries.csv"] = escrever_csv(
        f"{out}/historical_deliveries.csv",
        ["order_line_id", "order_id", "dc_id", "sku", "qty_ordered", "qty_shipped",
         "ship_date", "promised_date", "actual_delivery_date", "transit_days_actual",
         "promise_revisions", "backorder_days", "on_time", "in_full"], entregas)

    print("[4/8] Plano de recebimentos")
    futuros = planejar_recebimentos_futuros(estoque_final, transito_final,
                                            chegadas_pendentes, len(recebimentos) + 1000)
    todos_receb = [r for r in recebimentos if r["eta_date"] <= P.HIST_FIM.isoformat()] + futuros
    stats["inbound_plan.csv"] = escrever_csv(
        f"{out}/inbound_plan.csv",
        ["receipt_id", "plant_id", "dc_id", "sku", "qty", "order_date", "eta_date", "confirmed"],
        todos_receb)

    print("[5/8] Plano de demanda e consumo de forecast")
    consumo = defaultdict(int)
    for ln in lin_hist:
        w = inicio_semana(date.fromisoformat(ln["order_date"]))
        consumo[(w, ln["sku"], ln["ship_to_region"])] += ln["qty"]
    plano = []
    w = inicio_semana(P.HIST_INICIO)
    while w <= P.PRI_FIM:
        for sku in P.SKUS:
            for r in P.REGIOES:
                prev = sum(demanda_diaria_plano(w + timedelta(days=i), sku, r) for i in range(7))
                if prev <= 0:
                    continue
                plano.append(dict(week_start=w.isoformat(), sku=sku, region=r,
                                  forecast_qty=int(round(prev)),
                                  consumed_qty=consumo.get((w, sku, r), 0) if w <= P.HIST_FIM else ""))
        w += timedelta(days=7)
    stats["demand_plan.csv"] = escrever_csv(
        f"{out}/demand_plan.csv", ["week_start", "sku", "region", "forecast_qty", "consumed_qty"], plano)

    print("[6/8] Janelas de teste")
    seq = len(lin_hist) + 100000
    _, lin_pub = gerar_pedidos(rng, clientes, P.PUB_INICIO, P.PUB_FIM, seq)
    _, lin_pri = gerar_pedidos(rng, clientes, P.PRI_INICIO, P.PRI_FIM, seq + 50000)
    stats["orders_test_public.csv"] = escrever_csv(f"{out}/orders_test_public.csv", cols_ordem, lin_pub)
    stats["orders_test_private.csv"] = escrever_csv(f"{out}/orders_test_private.csv", cols_ordem, lin_pri)

    # trânsito realizado das janelas de teste — GABARITO, não distribuído
    realizado = []
    for janela, ini, fim in (("public", P.PUB_INICIO, P.PUB_FIM),
                             ("private", P.PRI_INICIO, P.PRI_FIM)):
        for d in intervalo(ini, fim + timedelta(days=20)):
            for cd in P.CDS:
                for r in P.REGIOES:
                    p50 = P.TRANSITO_DISTRIBUICAO[cd][r]
                    prob, amax = P.VARIABILIDADE_LANE[r]
                    atraso = rng.randrange(1, amax + 1) if rng.random() < prob else 0
                    realizado.append(dict(window=janela, dc_id=cd, region=r,
                                          ship_date=d.isoformat(),
                                          transit_days_actual=p50 + atraso))
    escrever_csv(f"{priv}/realized_transit.csv",
                 ["window", "dc_id", "region", "ship_date", "transit_days_actual"], realizado)

    # chegada real dos recebimentos: os confirmados chegam na ETA; os NÃO
    # confirmados atrasam de 2 a 6 dias. É o que dá dente ao BR-403 — quem
    # montou o ATP contando com recebimento não confirmado paga o atraso.
    reais = []
    for r in futuros:
        eta = date.fromisoformat(r["eta_date"])
        if r["confirmed"] == 1:
            real = eta
        else:
            real = eta + timedelta(days=rng.randrange(2, 7))
        reais.append(dict(receipt_id=r["receipt_id"], dc_id=r["dc_id"], sku=r["sku"],
                          qty=r["qty"], eta_planned=r["eta_date"],
                          eta_actual=real.isoformat(), confirmed=r["confirmed"]))
    escrever_csv(f"{priv}/realized_inbound.csv",
                 ["receipt_id", "dc_id", "sku", "qty", "eta_planned", "eta_actual",
                  "confirmed"], reais)

    # --- estoque de abertura de cada janela avaliada
    # A janela privada não começa no estado do corte: entre 29/08 e 13/09 os
    # recebimentos planejados chegam e os pedidos da janela pública já foram
    # atendidos pela política vigente. Publicar isso é questão de justiça —
    # sem esse arquivo, ninguém conseguiria montar o ATP da janela privada.
    print("[7/8] Estoque de abertura das janelas")
    aberturas = []
    for janela, ini in (("public", P.PUB_INICIO), ("private", P.PRI_INICIO)):
        est = {k: v for k, v in estoque_final.items()}
        chegando = defaultdict(list)
        for r in todos_receb:
            eta = date.fromisoformat(r["eta_date"])
            if P.HIST_FIM < eta < ini:
                chegando[eta].append((r["dc_id"], r["sku"], int(r["qty"])))
        consumo = defaultdict(list)
        if janela == "private":
            for ln in lin_pub:
                if date.fromisoformat(ln["order_ts"][:10]) < ini:
                    cd0 = P.CD_PRIMARIO[ln["ship_to_region"]]
                    consumo[proximo_dia_util_cd(
                        date.fromisoformat(ln["order_ts"][:10]), cd0)].append(ln)
        d = P.HIST_FIM + timedelta(days=1)
        while d < ini:
            for (cd, sku, qty) in chegando.get(d, []):
                est[(cd, sku)] = est.get((cd, sku), 0) + qty
            for ln in sorted(consumo.get(d, []),
                             key=lambda x: (P.SEGMENTOS[x["segment"]]["prioridade"],
                                            x["order_line_id"])):
                sku, qty = ln["sku"], ln["qty"]
                cd = P.CD_PRIMARIO[ln["ship_to_region"]]
                if est.get((cd, sku), 0) < qty:
                    alt = max(P.CDS, key=lambda c: est.get((c, sku), 0))
                    if est.get((alt, sku), 0) >= qty:
                        cd = alt
                est[(cd, sku)] = max(0, est.get((cd, sku), 0) - qty)
            d += timedelta(days=1)
        for cd in P.CDS:
            for sku in P.SKUS:
                aberturas.append(dict(window=janela, opening_date=ini.isoformat(),
                                      dc_id=cd, sku=sku,
                                      on_hand=max(0, est.get((cd, sku), 0))))
    stats["inventory_opening.csv"] = escrever_csv(
        f"{out}/inventory_opening.csv",
        ["window", "opening_date", "dc_id", "sku", "on_hand"], aberturas)

    print("[8/8] Exemplos de resposta")
    exemplo_p, exemplo_r = [], []
    for i, ln in enumerate(lin_pub[:20]):
        cd = P.CD_PRIMARIO[ln["ship_to_region"]]
        d0 = date.fromisoformat(ln["order_date"])
        prom = somar_dias_uteis(proximo_dia_util_cd(d0, cd),
                                P.TRANSITO_DISTRIBUICAO[cd][ln["ship_to_region"]] + 2,
                                ln["ship_to_region"])
        exemplo_p.append(dict(order_line_id=ln["order_line_id"], dc_id=cd,
                              promised_date=prom.isoformat(), qty_committed=ln["qty"],
                              shipment_group=f"SHP-{i // 3:04d}"))
    for i, (o, dst, sku) in enumerate([("CD-SP", "CD-GO", "P4"), ("CD-SP", "CD-PR", "P1"),
                                       ("CD-PE", "CD-GO", "P5")]):
        exemplo_r.append(dict(transfer_id=f"TRF-{i + 1:04d}", origin=o, dest=dst, sku=sku,
                              qty_pallets=8 + i * 4,
                              ship_date=(P.PUB_INICIO + timedelta(days=2 + i)).isoformat()))
    escrever_csv(f"{out}/resposta_exemplo_promessa.csv",
                 ["order_line_id", "dc_id", "promised_date", "qty_committed", "shipment_group"],
                 exemplo_p)
    escrever_csv(f"{out}/resposta_exemplo_rebalanceamento.csv",
                 ["transfer_id", "origin", "dest", "sku", "qty_pallets", "ship_date"], exemplo_r)

    # exemplo da trilha preditiva: quantis de lead time por rota e dia de embarque
    exemplo_f = []
    d = P.PUB_INICIO
    while d <= P.PUB_INICIO + timedelta(days=2) and len(exemplo_f) < 60:
        for cd, mapa in P.TRANSITO_DISTRIBUICAO.items():
            for reg, t in mapa.items():
                exemplo_f.append(dict(dc_id=cd, region=reg, ship_date=d.isoformat(),
                                      transit_q50=t, transit_q90=t + 2))
        d += timedelta(days=1)
    escrever_csv(f"{out}/resposta_exemplo_previsao.csv",
                 ["dc_id", "region", "ship_date", "transit_q50", "transit_q90"],
                 exemplo_f[:60])

    print("[9/9] Checksums")
    arquivos = sorted(f for f in os.listdir(out) if f.endswith(".csv"))
    linhas_ck = [f"# Desafio Supply Chain — pacote de dados v{P.VERSAO}",
                 f"# seed={args.seed}", "# verificacao (qualquer sistema): python desafio/ferramentas/conferir_dados.py",
                 "# verificacao (macOS/Linux/Git Bash): sha256sum -c CHECKSUMS.txt", ""]
    for nome in arquivos:
        linhas_ck.append(f"{sha256(os.path.join(out, nome))}  {nome}")
    with open(f"{out}/CHECKSUMS.txt", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(linhas_ck) + "\n")

    print("\nArquivos gerados:")
    total_bytes = 0
    for nome in arquivos:
        tam = os.path.getsize(os.path.join(out, nome))
        total_bytes += tam
        print(f"  {nome:34s} {stats.get(nome, '-'):>9} linhas  {tam / 1024:8.1f} KB")
    print(f"\n  total: {total_bytes / 1024 / 1024:.2f} MB")

    # resumo para o dicionário de dados
    receita = defaultdict(float)
    pedidos_seg = defaultdict(set)
    for ln in lin_hist:
        receita[ln["segment"]] += ln["valor"]
        pedidos_seg[ln["segment"]].add(ln["order_id"])
    tot_rec = sum(receita.values())
    tot_ped = sum(len(v) for v in pedidos_seg.values())
    print("\nMix realizado (histórico):")
    for seg in ("KA", "DIS", "VAR", "ECM"):
        print(f"  {seg:4s} receita {receita[seg] / tot_rec:6.1%}   "
              f"pedidos {len(pedidos_seg[seg]) / tot_ped:6.1%}")
    print(f"\n  pedidos históricos: {tot_ped}   linhas: {len(lin_hist)}")
    print(f"  linhas public test: {len(lin_pub)}   private test: {len(lin_pri)}")


if __name__ == "__main__":
    main()
