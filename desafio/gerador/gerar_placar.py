"""
Extrai os números do baseline e grava em docs/dados/placar.json.

O placar publicado precisa dos números OFICIAIS, calculados contra o gabarito.
Como o gabarito não vai para o repositório, este script só roda na máquina dos
organizadores — o JSON resultante é versionado e a página o consome.

Se rodar sem o gabarito, avisa e não sobrescreve o arquivo existente.

Uso:
    python desafio/gerador/gerar_placar.py
"""

import csv
import json
import os
import sys
from collections import defaultdict

RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(RAIZ, "desafio", "ferramentas"))
sys.path.insert(0, os.path.join(RAIZ, "desafio", "gerador"))

from comum import Dados  # noqa: E402
from avaliar import carregar_gabarito, simular, metricas  # noqa: E402
import parametros as P  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

DESTINO = os.path.join(RAIZ, "docs", "dados", "placar.json")

# metas publicadas na rubrica; direcao 1 = maior e melhor, -1 = menor e melhor
METAS = [
    ("OTIF", "otif", 0.95, 1, "contra a data que o cliente pediu"),
    ("OTIF Key Account", "otif_ka", 0.98, 1, "abaixo de 95% dispara multa de 3%"),
    ("Promise Reliability", "promise_reliability", 0.96, 1, "contra a data que você prometeu"),
    ("In Full", "in_full", 0.97, 1, "linhas entregues completas"),
    ("Fill Rate (valor)", "fill_rate_valor", 0.96, 1, "piso de 85% por segmento"),
    ("Aderência ao CD primário", "aderencia_cd_primario", 0.85, 1, "quanto sai do CD natural"),
    ("Ocupação do veículo", "ocupacao_media_veiculo", 0.80, 1, "peso ou volume, o que estourar antes"),
    ("Custo logístico / receita", "custo_logistico_pct", 0.085, -1, "quanto da receita vira custo"),
]

ROTULO_CUSTO = {
    "frete_distribuicao": "Frete de distribuição",
    "frete_transferencia": "Frete de transferência",
    "multa_ka": "Multa de Key Account",
    "armazenagem": "Armazenagem",
    "falta": "Custo de falta",
    "reentrega": "Reentrega",
    "movimentacao": "Movimentação",
    "escolta": "Escolta",
    "overflow": "Overflow de CD",
}


class Silencio:
    erros, avisos = [], []
    valida = True

    def erro(self, *a):
        pass

    def aviso(self, *a):
        pass


def coleta(dados, gabarito, janela):
    pasta = os.path.join(RAIZ, "desafio", "respostas", "baseline", janela)
    linhas = dados.pedidos(janela)
    prom = list(csv.DictReader(open(f"{pasta}/resposta_promessa.csv", encoding="utf-8")))
    arq_reb = f"{pasta}/resposta_rebalanceamento.csv"
    reb = list(csv.DictReader(open(arq_reb, encoding="utf-8"))) if os.path.exists(arq_reb) else []

    res, custo, ocup = simular(dados, prom, reb, linhas, gabarito, janela, Silencio())
    m = metricas(dados, linhas, prom, res, custo, Silencio(), ocup)
    pl = {p["order_line_id"]: p for p in prom}

    def corte(chave):
        agg = defaultdict(lambda: {"linhas": 0, "no_prazo": 0, "valor_atrasado": 0.0})
        for ln in linhas:
            r = res.get(ln["order_line_id"])
            if not r or not r["entregue"]:
                continue
            k = chave(ln)
            agg[k]["linhas"] += 1
            if r["on_time_cliente"]:
                agg[k]["no_prazo"] += 1
            else:
                agg[k]["valor_atrasado"] += dados.valor(ln["sku"], int(ln["qty"]))
        saida = []
        for k, v in agg.items():
            saida.append(dict(nome=k, linhas=v["linhas"],
                              otif=round(v["no_prazo"] / v["linhas"], 4),
                              atrasadas=v["linhas"] - v["no_prazo"],
                              valor_atrasado=round(v["valor_atrasado"], 2)))
        return sorted(saida, key=lambda x: x["otif"])

    return dict(
        kpis=[dict(rotulo=r, chave=k, valor=round(m[k], 4), meta=meta,
                   direcao=d, nota=nota,
                   atinge=(m[k] >= meta) if d == 1 else (m[k] <= meta))
              for r, k, meta, d, nota in METAS],
        custo_total=round(m["custo_total"], 2),
        custo=[dict(nome=ROTULO_CUSTO.get(k, k), chave=k, valor=round(v, 2))
               for k, v in sorted(m["custo_detalhado"].items(), key=lambda x: -x[1])
               if v > 0],
        linhas=m["linhas"],
        valor_pedido=round(m["valor_pedido"], 2),
        por_regiao=corte(lambda l: l["ship_to_region"]),
        por_cd=corte(lambda l: pl[l["order_line_id"]]["dc_id"]),
        por_segmento=corte(lambda l: dados.segmento(l)),
        transferencias=len(reb),
    )


def main():
    privado = os.path.join(RAIZ, "desafio", "privado")
    oficial = os.path.exists(os.path.join(privado, "realized_transit.csv"))
    if not oficial:
        print("Gabarito ausente — o placar publicado precisa dos números oficiais.")
        print(f"Arquivo mantido como está: {DESTINO}")
        sys.exit(0)

    dados = Dados(os.path.join(RAIZ, "desafio", "dados", "v" + P.VERSAO))
    gab = carregar_gabarito(privado, dados)

    saida = dict(versao=P.VERSAO, modo="oficial",
                 janelas={j: coleta(dados, gab, j) for j in ("public", "private")})

    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    with open(DESTINO, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)

    for j, d in saida["janelas"].items():
        falha = [k["rotulo"] for k in d["kpis"] if not k["atinge"]]
        print(f"  {j:<8} custo R$ {d['custo_total']:>12,.2f}   "
              f"{len(falha)} de {len(d['kpis'])} KPIs abaixo da meta")
    print(f"\nplacar gravado em {DESTINO}")


if __name__ == "__main__":
    main()
