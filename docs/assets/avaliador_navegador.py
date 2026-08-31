"""
Driver executado dentro do Pyodide.

Roda o MESMO avaliador que o robô do pull request usa — não uma reimplementação
em JavaScript. Duas implementações divergiriam, e uma nota que discorda do CI é
pior do que nota nenhuma.

Sem gabarito no navegador (ele revelaria os tempos de trânsito reais), então o
avaliador cai no modo TREINO: sorteia o trânsito da distribuição histórica com
semente fixa.
"""

import json
import os
import sys

sys.path.insert(0, "/desafio/ferramentas")
sys.path.insert(0, "/desafio/gerador")

from comum import Dados, escrever_csv          # noqa: E402
import avaliar                                  # noqa: E402
import baseline_atual                           # noqa: E402

_dados = None
_referencia = {}


def preparar():
    """Carrega os cadastros uma vez e gera o baseline de referência do score."""
    global _dados
    _dados = Dados("/desafio/dados/v1.0.0")
    return {"ok": True}


def _baseline(janela):
    if janela in _referencia:
        return _referencia[janela]
    pasta = f"/baseline/{janela}"
    if not os.path.exists(f"{pasta}/resposta_promessa.csv"):
        promessas = baseline_atual.gerar_promessas(_dados, janela)
        transf = baseline_atual.gerar_rebalanceamento(_dados, janela)
        escrever_csv(f"{pasta}/resposta_promessa.csv",
                     ["order_line_id", "dc_id", "promised_date", "qty_committed",
                      "shipment_group"], promessas)
        escrever_csv(f"{pasta}/resposta_rebalanceamento.csv",
                     ["transfer_id", "origin", "dest", "sku", "qty_pallets", "ship_date"],
                     transf)
    gab = avaliar.carregar_gabarito("/sem-gabarito", _dados)
    _res, m, _p = avaliar.rodar(_dados, pasta, janela, gab, silencioso=True)
    _referencia[janela] = m
    return m


def avaliar_entrada(janela):
    """Avalia o que o navegador gravou em /entrada e devolve JSON."""
    gab = avaliar.carregar_gabarito("/sem-gabarito", _dados)
    res, m, pinball = avaliar.rodar(_dados, "/entrada", janela, gab)
    if not res.valida:
        return json.dumps({"valida": False, "erros": res.erros[:20],
                           "total_erros": len(res.erros)}, ensure_ascii=False)
    ref = _baseline(janela)
    saida = {"valida": True, "modo": "treino", "janela": janela,
             "metricas": m, "score": avaliar.pontuar(m, ref, pinball),
             "baseline": {k: ref[k] for k in
                          ("promise_reliability", "otif", "otif_ka", "fill_rate_valor",
                           "ocupacao_media_veiculo", "custo_total")},
             "avisos": res.avisos[:6]}
    return json.dumps(saida, ensure_ascii=False, default=str)
