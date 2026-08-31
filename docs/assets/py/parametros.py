"""
Parâmetros da rede do Desafio Supply Chain.

Fonte da verdade compartilhada entre gerador, baseline e avaliador.
Qualquer número aqui tem contrapartida no documento de regras
(docs/desafio/01-business-scope.md).
"""

from datetime import date

SEED = 42
VERSAO = "1.0.0"

# ---------------------------------------------------------------- janelas
HIST_INICIO = date(2025, 9, 1)
HIST_FIM = date(2026, 8, 28)      # data de corte: fim do histórico
PUB_INICIO = date(2026, 8, 31)    # public test — leaderboard
PUB_FIM = date(2026, 9, 11)
PRI_INICIO = date(2026, 9, 14)    # private test — ranking final
PRI_FIM = date(2026, 9, 25)

HORIZONTE_REBALANCEAMENTO = 28    # BR-705
SEMANAS_CONGELADAS = 2            # BR-706

# ---------------------------------------------------------------- regiões
REGIOES = ["SE", "S", "CO", "NE", "N"]
SHARE_REGIAO = {"SE": 0.45, "S": 0.20, "CO": 0.10, "NE": 0.20, "N": 0.05}
CRESCIMENTO_MES = {"SE": 0.000, "S": 0.002, "CO": 0.004, "NE": 0.008, "N": 0.005}

# ---------------------------------------------------------------- produtos
# peso kg | volume m3 | valor R$ | unidades por palete | shelf life | classe
SKUS = {
    "P1": dict(descricao="Linha básica, alto giro", classe="A", peso=0.80,
               volume=0.0025, valor=12.0, un_palete=700, shelf_life=365,
               demanda_mes=240000, allow_partial=1),
    "P2": dict(descricao="Linha padrão", classe="A", peso=1.20,
               volume=0.0040, valor=28.0, un_palete=450, shelf_life=365,
               demanda_mes=150000, allow_partial=1),
    "P3": dict(descricao="Linha premium", classe="B", peso=0.50,
               volume=0.0060, valor=180.0, un_palete=300, shelf_life=540,
               demanda_mes=40000, allow_partial=0),
    "P4": dict(descricao="Linha sazonal", classe="B", peso=1.50,
               volume=0.0060, valor=45.0, un_palete=300, shelf_life=365,
               demanda_mes=60000, allow_partial=1),
    "P5": dict(descricao="Lançamento / promocional", classe="C", peso=0.90,
               volume=0.0035, valor=60.0, un_palete=500, shelf_life=90,
               demanda_mes=25000, allow_partial=1),
}

# fator sazonal por mês (1 = janeiro)
SAZONALIDADE = {
    "P1": {11: 1.15, 12: 1.25, 1: 0.90, 2: 0.92},
    "P2": {11: 1.10, 12: 1.20, 1: 0.92, 2: 0.94},
    "P3": {11: 1.20, 12: 1.35, 1: 0.85, 2: 0.88},
    "P4": {9: 1.40, 10: 2.20, 11: 3.00, 12: 2.60, 1: 0.60, 2: 0.45, 3: 0.50},
    "P5": {},   # lançamento: sem padrão sazonal, alta incerteza
}

# incerteza da demanda diária (desvio log-normal)
SIGMA_DEMANDA = {"P1": 0.16, "P2": 0.18, "P3": 0.22, "P4": 0.28, "P5": 0.42}

# fator por dia da semana (0 = segunda)
FATOR_DIA_SEMANA = [1.18, 1.12, 1.04, 0.96, 0.70, 0.0, 0.0]

# ---------------------------------------------------------------- plantas
PLANTAS = {
    "PL-01": dict(nome="Sumaré / SP", regiao="SE", skus=["P1", "P2", "P3", "P4"],
                  capacidade_mes=348000),
    "PL-02": dict(nome="Feira de Santana / BA", regiao="NE", skus=["P1", "P2", "P5"],
                  capacidade_mes=162000),
}

# ---------------------------------------------------------------- CDs
CDS = {
    "CD-SP": dict(nome="Cajamar / SP", regiao="SE", capacidade_paletes=12000,
                  cutoff="18:00", sabado_util=1, cobertura_alvo=21),
    "CD-PR": dict(nome="Curitiba / PR", regiao="S", capacidade_paletes=5000,
                  cutoff="18:00", sabado_util=1, cobertura_alvo=28),
    "CD-GO": dict(nome="Goiânia / GO", regiao="CO", capacidade_paletes=4000,
                  cutoff="18:00", sabado_util=0, cobertura_alvo=28),
    "CD-PE": dict(nome="Recife / PE", regiao="NE", capacidade_paletes=6000,
                  cutoff="18:00", sabado_util=0, cobertura_alvo=35),
}

# CD primário por região de entrega (BR-301 passo 1)
CD_PRIMARIO = {"SE": "CD-SP", "S": "CD-PR", "CO": "CD-GO", "NE": "CD-PE", "N": "CD-GO"}

# capacidade de manuseio por CD, em paletes expedidos por dia útil
CAPACIDADE_DIARIA_PALETES = {"CD-SP": 900, "CD-PR": 380, "CD-GO": 300, "CD-PE": 440}

# ---------------------------------------------------------------- lanes CD -> região
# transit_days (dias úteis) e tarifa R$/kg
TRANSITO_DISTRIBUICAO = {
    "CD-SP": {"SE": 2, "S": 3, "CO": 4, "NE": 6, "N": 8},
    "CD-PR": {"SE": 3, "S": 1, "CO": 5, "NE": 8, "N": 10},
    "CD-GO": {"SE": 3, "S": 5, "CO": 1, "NE": 5, "N": 3},
    "CD-PE": {"SE": 6, "S": 8, "CO": 5, "NE": 2, "N": 4},
}
TARIFA_KG = {"SE": 0.68, "S": 0.82, "CO": 1.05, "NE": 1.24, "N": 1.68}

# A tarifa acima é a do CD primário da região. Atender de um CD mais distante
# encarece o frete por quilo: +18% para cada dia útil de trânsito a mais que a
# rota primária. É o que dá preço ao trade-off "prazo vs. frete" (BR-603).
ACRESCIMO_POR_DIA_EXTRA = 0.18

# variabilidade real do trânsito: (prob_atraso, atraso_max_dias)
VARIABILIDADE_LANE = {
    "SE": (0.09, 2), "S": (0.11, 2), "CO": (0.15, 3),
    "NE": (0.18, 4), "N": (0.26, 5),
}

# ---------------------------------------------------------------- transferências
DISTANCIA_KM = {
    ("PL-01", "CD-SP"): 90, ("PL-01", "CD-PR"): 480,
    ("PL-01", "CD-GO"): 930, ("PL-01", "CD-PE"): 2660,
    ("PL-02", "CD-SP"): 1960, ("PL-02", "CD-PR"): 2380,
    ("PL-02", "CD-GO"): 1600, ("PL-02", "CD-PE"): 800,
    ("CD-SP", "CD-PR"): 410, ("CD-SP", "CD-GO"): 930, ("CD-SP", "CD-PE"): 2660,
    ("CD-PR", "CD-GO"): 1340, ("CD-PR", "CD-PE"): 3070,
    ("CD-GO", "CD-PE"): 1900,
}
TRANSITO_SUPRIMENTO = {
    ("PL-01", "CD-SP"): 1, ("PL-01", "CD-PR"): 2,
    ("PL-01", "CD-GO"): 3, ("PL-01", "CD-PE"): 5,
    ("PL-02", "CD-SP"): 4, ("PL-02", "CD-PR"): 6,
    ("PL-02", "CD-GO"): 4, ("PL-02", "CD-PE"): 1,
    ("CD-SP", "CD-PR"): 2, ("CD-SP", "CD-GO"): 3, ("CD-SP", "CD-PE"): 5,
    ("CD-PR", "CD-GO"): 4, ("CD-PR", "CD-PE"): 6,
    ("CD-GO", "CD-PE"): 4,
}

# ---------------------------------------------------------------- veículos
VEICULO_TRANSFERENCIA = dict(paletes=30, peso_kg=24000, volume_m3=90.0)
VEICULO_DISTRIBUICAO = dict(paletes=12, peso_kg=8000, volume_m3=24.0)

# ---------------------------------------------------------------- segmentos
SEGMENTOS = {
    "KA": dict(nome="Key Account", sla_horas_se_s=48, sla_horas_outras=72,
               pedido_completo=1, multa_pct=0.03, prioridade=1,
               lote="palete", paletes_linha=(1, 4), linhas_pedido=(2, 6),
               n_clientes=12),
    "DIS": dict(nome="Distribuidor / atacado", sla_horas_se_s=96, sla_horas_outras=96,
                pedido_completo=0, multa_pct=0.0, prioridade=2,
                lote="palete", paletes_linha=(1, 3), linhas_pedido=(2, 5),
                n_clientes=34),
    "VAR": dict(nome="Varejo regional", sla_horas_se_s=72, sla_horas_outras=72,
                pedido_completo=0, multa_pct=0.0, prioridade=3,
                lote="camada", paletes_linha=(1, 6), linhas_pedido=(1, 4),
                n_clientes=600),
    "ECM": dict(nome="E-commerce / pequeno varejo", sla_horas_se_s=120, sla_horas_outras=120,
                pedido_completo=0, multa_pct=0.0, prioridade=4,
                lote="livre", paletes_linha=(1, 1), linhas_pedido=(1, 3),
                n_clientes=170),
}

# fração do volume de cada SKU destinada a cada segmento
SHARE_SEGMENTO = {
    "P1": {"KA": 0.44, "DIS": 0.32, "VAR": 0.18, "ECM": 0.06},
    "P2": {"KA": 0.43, "DIS": 0.30, "VAR": 0.19, "ECM": 0.08},
    "P3": {"KA": 0.41, "DIS": 0.28, "VAR": 0.21, "ECM": 0.10},
    "P4": {"KA": 0.42, "DIS": 0.32, "VAR": 0.19, "ECM": 0.07},
    "P5": {"KA": 0.38, "DIS": 0.30, "VAR": 0.23, "ECM": 0.09},
}

CANAIS = {"KA": ["EDI"], "DIS": ["EDI", "PORTAL"],
          "VAR": ["PORTAL", "TELEVENDAS"], "ECM": ["PORTAL"]}

# ---------------------------------------------------------------- custos
FRETE_TRANSF_FIXO = 380.0          # BR-601
FRETE_TRANSF_KM = 4.20             # BR-601
FRETE_MINIMO = 180.0               # BR-602
AD_VALOREM = 0.0035                # BR-602
GRIS = 0.0012                      # BR-602
ARMAZ_POSICAO_MES = 38.0           # BR-604
ARMAZ_MOVIMENTACAO = 2.10          # BR-604
MARGEM_PERDIDA = 0.22              # BR-605
MULTA_KA_PCT = 0.03                # BR-606
OTIF_GATILHO_MULTA = 0.95          # BR-606
ESCOLTA_CUSTO = 1850.0             # BR-305
ESCOLTA_LIMIAR = 150000.0          # BR-305
REENTREGA_PCT = 0.60               # BR-206
EXPEDICAO_EXTRA_MULT = 4.0         # BR-607
OVERFLOW_PALETE_MES = 95.0         # BR-608
OVERFLOW_LIMIAR = 0.95             # BR-608

# ---------------------------------------------------------------- regras
CUSTO_INCREMENTAL_MAX = 0.08       # BR-303
OCUPACAO_MINIMA_VEICULO = 0.75     # BR-505
MAX_PONTOS_ENTREGA = 8             # BR-506
FILL_RATE_PISO_SEGMENTO = 0.85     # BR-205
SHELF_LIFE_MINIMO_P5 = 60          # BR-306
DIAS_RESERVA_KA = 5                # BR-203
COBERTURA_GATILHO = 7              # BR-702
COBERTURA_MINIMA_ORIGEM = 10       # BR-704
CONSUMO_FORECAST_GATILHO = 1.10    # BR-701
BUFFER_BASELINE = 2                # baseline operacional

# ---------------------------------------------------------------- feriados
FERIADOS = [
    # 2025
    ("2025-09-07", "Independência", "ALL"), ("2025-10-12", "N. Sra. Aparecida", "ALL"),
    ("2025-11-02", "Finados", "ALL"), ("2025-11-15", "Proclamação da República", "ALL"),
    ("2025-11-20", "Consciência Negra", "ALL"), ("2025-12-25", "Natal", "ALL"),
    # 2026
    ("2026-01-01", "Confraternização", "ALL"), ("2026-02-16", "Carnaval", "ALL"),
    ("2026-02-17", "Carnaval", "ALL"), ("2026-04-03", "Sexta-feira Santa", "ALL"),
    ("2026-04-21", "Tiradentes", "ALL"), ("2026-05-01", "Dia do Trabalho", "ALL"),
    ("2026-06-04", "Corpus Christi", "ALL"), ("2026-07-09", "Revolução (SP)", "SE"),
    ("2026-07-02", "Independência da Bahia", "NE"), ("2026-09-07", "Independência", "ALL"),
    ("2026-10-12", "N. Sra. Aparecida", "ALL"), ("2026-11-02", "Finados", "ALL"),
    ("2026-11-15", "Proclamação da República", "ALL"),
]
