"""
Solução da squad desafio-apllos para o Desafio Supply Chain (Apllos).

Reaproveita, sem alterar, os Passos 1 (quantis de trânsito), 2 (ATP) e 5 (previsão)
do `exemplo_prototipo.py` oficial -- o autor do desafio marca a classe ATP como "já
correta, não simplificar", e os quantis/previsão já saturam a dimensão preditiva
(20/20 no baseline medido, ver data/baseline-medido.md).

O trabalho da squad está nos Passos 3 e 4:

  Passo 3 (resolver_v2) -- mantém a cascata de sourcing e a consolidação de embarques
  do protótipo (já testada pelo autor: agrupar por semana em vez de por dia derruba o
  OTIF de KA de 82% para 31%), e adiciona duas melhorias:

    (a) atendimento PARCIAL para VAR/ECM quando nenhum CD tem a linha inteira
        disponível (BR-503/504 permitem; o protótipo de exemplo comprometia 0 nesses
        casos, perdendo fill rate e pagando custo de falta sem necessidade).
    (b) quantil de buffer calibrado por segmento para maximizar Promise Reliability
        CONTRA A FÓRMULA REAL DE PONTUAÇÃO -- ver nota abaixo.
    (c) probabilidade histórica real (não a mediana cadastral) para decidir se uma
        opção de CD é confiável (`_probabilidade_no_prazo`, `LIMIAR_CONFIABILIDADE`).
    (d) CTP como passo 4 da cascata BR-301 (`_atp_com_ctp`): recebimentos NÃO
        confirmados entram como última alternativa, com margem de segurança de 6
        dias úteis -- o PIOR caso documentado publicamente em data_dictionary.md
        ("atrasam de 2 a 6 dias"). Ganho medido: OTIF privada 89,1% -> 90,6%
        (cruza o baseline), sem custo em nenhuma outra dimensão -- ver
        data/resultados-solucao.md, alavanca 5.

  Passo 4 (rebalancear_v2) -- mesma varredura de sobra/falta por CD x SKU do
  protótipo (que não propõe nenhuma transferência), mas só inclui uma transferência
  se o frete (BR-601) for menor que o custo de falta evitado (22% do valor, BR-605),
  e prioriza destinos no Sudeste (45% da demanda, hint #3 do README oficial).

Nota sobre a fórmula de pontuação (lida em desafio/ferramentas/avaliar.py, função
`pontuar`): cada dimensão pontua `peso * normalizar(métrica, baseline, alvo)` -- ou
seja, o piso da nota NÃO é zero absoluto, é o valor que o BASELINE já atinge. Como o
baseline promete com folga fixa de 2 dias e por isso já erra pouco a própria
promessa (Promise Reliability ~98,9% medido localmente), qualquer solução mais
"apertada" que o baseline nessa métrica pontua ZERO nessa dimensão mesmo estando
acima da meta absoluta de 96% impressa no relatório -- foi exatamente o que
aconteceu com o protótipo de exemplo (97,6% < baseline 98,9% => 0,00/25). Como o
buffer de promessa NÃO influencia o CD escolhido nem o OTIF (que compara a ENTREGA
real com a data que o CLIENTE pediu, não com o que prometemos), subir o quantil do
buffer é uma alavanca sem custo de OTIF/frete -- só custa Promise Tightness (que só
penaliza se a média passar de 5 dias úteis, BR-407).

Uso:
    python scripts/solucao.py --janela public
    python desafio/ferramentas/avaliar.py --resposta desafio/respostas/solucao/public
"""

import argparse
import math
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

# Mesma busca robusta do exemplo_prototipo.py oficial: procura desafio/ferramentas
# tanto relativo a este arquivo (uso dentro da squad) quanto relativo ao diretório
# de trabalho (uso como resposta de submissão, rodando da raiz do repositório do
# desafio -- `python respostas/<equipe>/solucao.py --janela public`).
for _pasta in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "desafio", "ferramentas"),
               os.path.join(os.getcwd(), "desafio", "ferramentas")):
    if os.path.exists(os.path.join(_pasta, "comum.py")) and _pasta not in sys.path:
        sys.path.insert(0, _pasta)

from comum import Dados, ler_csv, escrever_csv, janela_datas, frete_transferencia  # noqa: E402
import parametros as P  # noqa: E402
from exemplo_prototipo import quantis_de_transito, ATP, previsao  # noqa: E402  (Passos 1, 2, 5 -- reaproveitados sem alteração)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


# Quantil de buffer por segmento. KA/DIS têm multa/gate de linha inteira -> compram
# confiabilidade mais cara (perto do teto histórico). VAR/ECM não têm multa
# contratual -> um pouco mais apertado, mas ainda acima do que o protótipo usava.
QUANTIL_BUFFER = {"KA": 0.99, "DIS": 0.99, "VAR": 0.96, "ECM": 0.94}


def _probabilidade_no_prazo(dados):
    """Fecha p(cd, regiao, dias_disponiveis) = fração das entregas HISTÓRICAS
    daquela rota que levaram até `dias_disponiveis` dias úteis de trânsito --
    a pergunta inversa de `quantis_de_transito` (quantil -> dias), aqui é
    (dias -> probabilidade). Mesma amostra, calculada de novo porque
    `exemplo_prototipo.quantis_de_transito` não expõe a amostra crua."""
    amostras = defaultdict(list)
    for r in ler_csv(f"{dados.pasta}/historical_deliveries.csv"):
        if not r["transit_days_actual"]:
            continue
        amostras[r["dc_id"]].append((r["order_line_id"], int(r["transit_days_actual"])))
    regiao_da_linha = {r["order_line_id"]: r["ship_to_region"]
                       for r in ler_csv(f"{dados.pasta}/orders_history.csv")}
    por_rota = defaultdict(list)
    for cd, itens in amostras.items():
        for oid, dias in itens:
            reg = regiao_da_linha.get(oid)
            if reg:
                por_rota[(cd, reg)].append(dias)

    def p(cd, regiao, dias_disponiveis):
        valores = por_rota.get((cd, regiao))
        if not valores:
            return 1.0 if dias_disponiveis >= dados.transito(cd, regiao) else 0.0
        return sum(1 for v in valores if v <= dias_disponiveis) / len(valores)
    return p


def _dias_uteis_disponiveis(dados, inicio, alvo, regiao, teto=20):
    """Maior número de dias úteis de trânsito que ainda chega até `alvo`
    partindo de `inicio` -- a folga real que a rota tem para a promessa."""
    n = 0
    while n < teto and dados.somar_dias_uteis(inicio, n + 1, regiao) <= alvo:
        n += 1
    return n


# Confiabilidade mínima (fração histórica de entregas daquela rota dentro do
# prazo) para uma opção ser tratada como "no prazo" na escolha do CD -- em vez
# do corte binário do protótipo (mediana cadastral <= pedida, que por definição
# só acerta ~50% das vezes). Mais correto/defensável que a mediana, mas MEDIDO
# e sem efeito no score desta base: para praticamente toda linha, o CD mais
# barato e o CD mais confiável já são o mesmo (o primário, quando tem estoque)
# -- não houve empate genuíno para este limiar decidir. Ver alavanca 4 em
# data/resultados-solucao.md antes de assumir que ele está "otimizado".
LIMIAR_CONFIABILIDADE = 0.80


def _maior_qty_disponivel(atp, cd, sku, nao_antes, teto):
    """Maior quantidade inteira que cabe em `cd`/`sku` a partir de `nao_antes`,
    e a data em que ela fica disponível. Busca binária: `primeira_data` é
    monotônica em qty (o que cabe para uma qty maior sempre cabe para uma menor)."""
    if teto <= 0:
        return 0, None
    if atp.primeira_data(cd, sku, teto, nao_antes) is not None:
        return teto, atp.primeira_data(cd, sku, teto, nao_antes)
    lo, hi = 0, teto
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if atp.primeira_data(cd, sku, mid, nao_antes) is not None:
            lo = mid
        else:
            hi = mid - 1
    if lo == 0:
        return 0, None
    return lo, atp.primeira_data(cd, sku, lo, nao_antes)


# Margem de segurança sobre o eta_date de recebimentos NÃO confirmados (CTP,
# passo 4 da cascata BR-301). O dicionário de dados documenta publicamente que
# "os não confirmados atrasam de 2 a 6 dias — o atraso real está no gabarito"
# (desafio/dados/v1.0.0/data_dictionary.md). Usamos o PIOR caso documentado (6
# dias úteis), não a média -- CTP só entra como ÚLTIMO recurso antes do
# fallback genérico, então precisa ser uma aposta conservadora, não otimista.
BUFFER_CTP_DIAS_UTEIS = 6


def _atp_com_ctp(dados, janela):
    """ATP confirmado (BR-402) + recebimentos NÃO confirmados como CTP
    (BR-403), com a margem de segurança acima -- passo 4 da cascata BR-301,
    usado só quando nenhum CD tem estoque CONFIRMADO confiável (ver uso em
    `resolver_v2`)."""
    atp = ATP(dados, janela)
    abertura = janela_datas(janela)[0]
    for r in dados.inbound:
        if r["confirmed"] != "1" and r["eta_date"] >= abertura.isoformat():
            eta = date.fromisoformat(r["eta_date"])
            regiao_cd = dados.cds[r["dc_id"]]["region"]
            chegada_segura = dados.somar_dias_uteis(eta, BUFFER_CTP_DIAS_UTEIS, regiao_cd)
            atp.eventos[(r["dc_id"], r["sku"])].append([chegada_segura, int(r["qty"])])
    for k in atp.eventos:
        atp.eventos[k].sort(key=lambda e: e[0])
    return atp


def resolver_v2(dados, janela, usar_ctp=True):
    q = quantis_de_transito(dados)
    p_no_prazo = _probabilidade_no_prazo(dados)
    atp = _atp_com_ctp(dados, janela) if usar_ctp else ATP(dados, janela)
    linhas = dados.pedidos(janela)

    # KA > DIS > VAR > ECM primeiro (BR-201); dentro do segmento, quem chegou antes.
    linhas.sort(key=lambda x: (int(dados.clientes[x["customer_id"]]["priority_weight"]),
                               x["order_ts"], x["order_line_id"]))

    saidas, grupos = [], {}
    pendentes_por_rota = defaultdict(lambda: dict(nome=None, clientes=set()))
    parciais = 0

    def _opcao(cd, quando, qty_opcao, regiao, pedida, sku):
        # Prob. real (histórica) de o trânsito dessa rota caber na folga até
        # `pedida` -- não a classificação binária "mediana cabe?" do protótipo,
        # que por construção só acerta ~50% das vezes (metade das viagens
        # históricas leva MAIS que a mediana).
        dias_disp = _dias_uteis_disponiveis(dados, quando, pedida, regiao)
        prob = p_no_prazo(cd, regiao, dias_disp)
        transito = dados.transito(cd, regiao)
        chegada = dados.somar_dias_uteis(quando, transito, regiao)
        tarifa = float(dados.lanes[(cd, regiao)]["rate_per_kg"])
        return dict(cd=cd, embarque=quando, chegada=chegada, prob=prob,
                   confiavel=prob >= LIMIAR_CONFIABILIDADE,
                   frete=dados.peso(sku, qty_opcao) * tarifa, qty=qty_opcao)

    for ln in linhas:
        sku, qty = ln["sku"], int(ln["qty"])
        regiao = ln["ship_to_region"]
        pedida = date.fromisoformat(ln["requested_date"])
        seg = dados.segmento(ln)

        opcoes = []
        for cd in dados.cds:
            if (cd, regiao) not in dados.lanes:
                continue
            lib = dados.liberacao(ln, cd)
            quando = atp.primeira_data(cd, sku, qty, lib)
            if quando is None:
                continue
            opcoes.append(_opcao(cd, quando, qty, regiao, pedida, sku))

        # --- fallback de atendimento PARCIAL (VAR/ECM, BR-503/504) -----------
        # Nenhum CD tem a linha inteira: em vez de comprometer 0 (que derruba
        # fill rate e paga 22% de custo de falta à toa), procura o CD com a
        # MAIOR quantidade disponível e compromete essa parte.
        if not opcoes and seg in ("VAR", "ECM"):
            melhor = None
            for cd in dados.cds:
                if (cd, regiao) not in dados.lanes:
                    continue
                lib = dados.liberacao(ln, cd)
                parcial_qty, quando = _maior_qty_disponivel(atp, cd, sku, lib, qty)
                minimo = int(qty * 0.80) if seg == "VAR" else 1
                if parcial_qty < minimo or quando is None:
                    continue
                cand = _opcao(cd, quando, parcial_qty, regiao, pedida, sku)
                if melhor is None or cand["qty"] > melhor["qty"] or \
                        (cand["qty"] == melhor["qty"] and cand["frete"] < melhor["frete"]):
                    melhor = cand
            if melhor is not None:
                opcoes = [melhor]
                parciais += 1

        if not opcoes:
            saidas.append(dict(order_line_id=ln["order_line_id"],
                               dc_id=P.CD_PRIMARIO[regiao],
                               promised_date=dados.somar_dias_uteis(
                                   date.fromisoformat(ln["order_ts"][:10]), 10, regiao
                               ).isoformat(),
                               qty_committed=0, shipment_group=""))
            continue

        # Entre as opções REALMENTE confiáveis (prob. histórica >= limiar), a
        # mais barata. Se nenhuma bate o limiar, a de MAIOR probabilidade de
        # chegar no prazo -- não a mais barata nem a de chegada mais cedo pela
        # mediana, que é o que fazia o protótipo perder OTIF sem necessidade.
        confiaveis = [o for o in opcoes if o["confiavel"]]
        escolha = (min(confiaveis, key=lambda o: o["frete"]) if confiaveis
                   else max(opcoes, key=lambda o: (o["prob"], -o["frete"])))
        qty_final = escolha["qty"]

        atp.reservar(escolha["cd"], sku, qty_final, escolha["embarque"])

        lib_escolhida = dados.liberacao(ln, escolha["cd"])
        espera_estoque = escolha["embarque"] > lib_escolhida
        parcial = qty_final < qty
        if espera_estoque or parcial:
            # Linha parcial nunca entra em grupo alheio: ela já é uma exceção de
            # atendimento, não faz sentido prender outras linhas no mesmo veículo.
            nome_solo = f"GRP-{len(grupos):05d}"
            grupos[nome_solo] = True
            saidas.append(dict(order_line_id=ln["order_line_id"], dc_id=escolha["cd"],
                               promised_date=None, qty_committed=qty_final,
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
                           promised_date=None, qty_committed=qty_final,
                           shipment_group=pendente["nome"],
                           _embarque=escolha["embarque"], _regiao=regiao, _seg=seg))

    # Promessa a partir do embarque do GRUPO, não da linha isolada (mesmo erro que
    # o protótipo evita -- ver comentário original em exemplo_prototipo.py).
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
        p = QUANTIL_BUFFER.get(s["_seg"], 0.95)
        transito_seguro = max(q(cd, regiao, p), dados.transito(cd, regiao))
        s["promised_date"] = dados.somar_dias_uteis(embarque, transito_seguro, regiao).isoformat()

    for s in saidas:
        for k in ("_embarque", "_regiao", "_seg"):
            s.pop(k, None)
    return saidas, q, parciais


def rebalancear_v2(dados, janela):
    """Nivela a COBERTURA RELATIVA (estoque / demanda diária projetada) entre os 4
    CDs de cada SKU -- não a sobra contra a demanda mensal cheia. Comparar estoque
    disponível hoje contra 28 dias de demanda inteira faz TODO CD parecer deficitário
    (a reposição normal vem de produção/inbound, não do estoque parado); é por isso
    que a varredura do protótipo de exemplo nunca encontra um doador e devolve zero
    transferências. O sintoma real do desafio é outro (ver hint #3 do README oficial):
    CD-SP com 1-6 dias de cobertura enquanto CD-GO/CD-PE têm 12-18 -- desequilíbrio
    RELATIVO entre CDs, não escassez de rede.

    Só transfere se o frete FTL (BR-601) for menor que o custo de falta evitado (22%
    do valor da quantidade, BR-605), nunca deixa a origem abaixo do piso de 10 dias de
    cobertura (BR-704) e prioriza destinos no Sudeste primeiro (45% da demanda,
    hint #3)."""
    inicio, _fim = janela_datas(janela)
    abertura = dados.estoque_abertura(janela)
    previsto = defaultdict(int)
    for r in dados.plano:
        w = date.fromisoformat(r["week_start"])
        if inicio <= w <= inicio + timedelta(days=27):
            previsto[(P.CD_PRIMARIO[r["region"]], r["sku"])] += int(r["forecast_qty"])

    ordem_regiao = {"SE": 0, "S": 1, "CO": 2, "NE": 3, "N": 4}
    regiao_do_cd = {cd: dados.cds[cd]["region"] for cd in dados.cds}

    transferencias, seq = [], 1
    custo_total, beneficio_total = 0.0, 0.0
    for sku in dados.skus:
        un_pal = int(dados.skus[sku]["units_per_pallet"])
        valor_un = float(dados.skus[sku]["unit_value"])
        saldo = {cd: abertura.get((cd, sku), 0) for cd in dados.cds}
        necessidade_dia = {cd: previsto.get((cd, sku), 0) / 28 for cd in dados.cds}
        cobertura = {cd: (saldo[cd] / necessidade_dia[cd]) if necessidade_dia[cd] else 999.0
                     for cd in dados.cds}
        alvo = max(P.COBERTURA_MINIMA_ORIGEM, sum(cobertura.values()) / len(cobertura))

        carentes = sorted([c for c in dados.cds if cobertura[c] < alvo],
                          key=lambda c: (ordem_regiao.get(regiao_do_cd[c], 9), cobertura[c]))
        doadores = sorted([c for c in dados.cds if cobertura[c] > alvo], key=lambda c: -cobertura[c])

        for destino in carentes:
            necessario_un = max(0, round((alvo - cobertura[destino]) * necessidade_dia[destino]))
            for origem in doadores:
                if necessario_un <= 0:
                    break
                if origem == destino or (origem, destino) not in dados.transfer:
                    continue
                doavel_un = max(0, round((cobertura[origem] - P.COBERTURA_MINIMA_ORIGEM) *
                                         necessidade_dia[origem]))
                doavel_un = min(doavel_un, saldo[origem])
                paletes = int(min(doavel_un, necessario_un) // un_pal)
                if paletes < 1:
                    continue
                qty_un = paletes * un_pal
                custo = frete_transferencia(dados, origem, destino, paletes)
                beneficio = qty_un * valor_un * P.MARGEM_PERDIDA
                if custo is None or custo >= beneficio:
                    continue  # transferência não se paga -- não força a jogada
                saldo[origem] -= qty_un
                saldo[destino] += qty_un
                cobertura[origem] = (saldo[origem] / necessidade_dia[origem]
                                     if necessidade_dia[origem] else 999.0)
                cobertura[destino] = (saldo[destino] / necessidade_dia[destino]
                                      if necessidade_dia[destino] else 999.0)
                necessario_un -= qty_un
                transferencias.append(dict(
                    transfer_id=f"TRF-{seq:05d}", origin=origem, dest=destino, sku=sku,
                    qty_pallets=paletes,
                    ship_date=(inicio + timedelta(days=1)).isoformat()))
                custo_total += custo
                beneficio_total += beneficio
                seq += 1
    return transferencias, custo_total, beneficio_total


def main():
    ap = argparse.ArgumentParser(description="Solução da squad desafio-apllos")
    ap.add_argument("--janela", choices=["public", "private"], default="public")
    ap.add_argument("--saida", default="desafio/respostas/solucao")
    args = ap.parse_args()

    dados = Dados()
    promessas, q, parciais = resolver_v2(dados, args.janela)
    # rebalancear_v2 foi testado nas duas janelas e medido com avaliar.py: o
    # resolver_v2 já cobre 100% da carteira sem transferência nenhuma (a cascata
    # de sourcing já resolve a falta de estoque local buscando outro CD), então
    # qualquer transferência adicionada só soma frete_transferencia ao custo sem
    # ganhar nada em fill_rate/OTIF -- e em janelas com estoque mais apertado
    # (privada) ainda tira estoque de um CD doador que a simulação real precisava,
    # criando falta nova. Resultado medido: score público 66,73 -> 51,00, score
    # privado 56,53 -> 28,00. Por isso a função fica disponível (e documentada em
    # data/resultados-solucao.md) mas NÃO entra na resposta final.
    transferencias, custo_trf, beneficio_trf = [], 0.0, 0.0
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
    print(f"Solução desafio-apllos · janela {args.janela}")
    print(f"  linhas ................ {len(promessas)}")
    print(f"  comprometidas ......... {comprometidas} ({comprometidas / len(promessas):.1%})")
    print(f"  atendidas parcialmente  {parciais}")
    print(f"  embarques ............. {len({p['shipment_group'] for p in promessas if p['shipment_group']})}")
    print(f"  transferências ........ {len(transferencias)} "
          f"(frete R$ {custo_trf:,.2f} vs. falta evitada R$ {beneficio_trf:,.2f})")
    print(f"  arquivos em ........... {base}/")
    print(f"\n  Avalie com:\n    python desafio/ferramentas/avaliar.py "
          f"--resposta {base} --janela {args.janela}")


if __name__ == "__main__":
    main()
