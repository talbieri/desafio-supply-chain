"""
Consolida o resultado de todas as equipes em um ranking.

Roda a avaliação OFICIAL de cada pasta em respostas/ e ordena. Só funciona na
máquina de quem tem o gabarito — o que é o ponto: a nota que vale sai daqui,
não do robô do pull request, que trabalha em modo treino.

O ranking final é calculado na JANELA PRIVADA. A pública entra na tabela como
referência, para dar para ver quem otimizou no leaderboard e não generalizou.

Desempate, na ordem da rubrica:
  1. maior Promise Reliability
  2. menor custo total
  3. quem enviou primeiro (data do arquivo)

Uso:
    python desafio/gerador/gerar_ranking.py
    python desafio/gerador/gerar_ranking.py --publicar   # grava docs/dados/ranking.json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
AVALIAR = os.path.join(RAIZ, "desafio", "ferramentas", "avaliar.py")
RESPOSTAS = os.path.join(RAIZ, "respostas")
PRIVADO = os.path.join(RAIZ, "desafio", "privado")
DESTINO = os.path.join(RAIZ, "docs", "dados", "ranking.json")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def equipes():
    if not os.path.isdir(RESPOSTAS):
        return []
    return sorted(d for d in os.listdir(RESPOSTAS)
                  if os.path.isdir(os.path.join(RESPOSTAS, d))
                  and not d.startswith(".") and d != "EXEMPLO")


def avaliar(equipe, janela):
    pasta = os.path.join("respostas", equipe, janela)
    if not os.path.exists(os.path.join(RAIZ, pasta, "resposta_promessa.csv")):
        return None
    r = subprocess.run([sys.executable, AVALIAR, "--resposta", pasta,
                        "--janela", janela, "--json"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=RAIZ)
    if not r.stdout.strip().startswith("{"):
        return {"valida": False, "motivo": (r.stdout or r.stderr).strip()[:400]}
    return json.loads(r.stdout)


def enviado_em(equipe):
    """Data do arquivo mais recente da equipe — critério do terceiro desempate."""
    mais_novo = 0
    for raiz, _d, arqs in os.walk(os.path.join(RESPOSTAS, equipe)):
        for a in arqs:
            mais_novo = max(mais_novo, os.path.getmtime(os.path.join(raiz, a)))
    return datetime.fromtimestamp(mais_novo, timezone.utc).isoformat() if mais_novo else ""


def coletar():
    linhas = []
    for eq in equipes():
        pub, pri = avaliar(eq, "public"), avaliar(eq, "private")
        item = {"equipe": eq, "enviado_em": enviado_em(eq)}
        for rot, d in (("publica", pub), ("privada", pri)):
            if d is None:
                item[rot] = None
            elif not d.get("valida"):
                item[rot] = {"valida": False,
                             "motivo": d.get("motivo") or "; ".join(d.get("erros", [])[:3])}
            else:
                m, sc = d["metricas"], d.get("score", {})
                item[rot] = {"valida": True, "score": sc.get("total", 0.0),
                             "promise_reliability": m["promise_reliability"],
                             "otif": m["otif"], "otif_ka": m["otif_ka"],
                             "fill_rate": m["fill_rate_valor"],
                             "custo_total": m["custo_total"],
                             "componentes": sc.get("componentes", {})}
        linhas.append(item)

    def chave(x):
        p = x.get("privada")
        if not p or not p.get("valida"):
            return (1, 0, 0, "")            # inválidas vão para o fim
        return (0, -p["score"], -p["promise_reliability"], p["custo_total"])

    linhas.sort(key=chave)
    for i, x in enumerate(linhas, 1):
        p = x.get("privada")
        x["posicao"] = i if (p and p.get("valida")) else None
    return linhas


def tabela(linhas):
    print(f"\n{'#':<4}{'equipe':<22}{'score':>8}{'OTIF':>9}{'OTIF KA':>9}"
          f"{'custo':>14}   {'pública':>8}")
    print("-" * 78)
    for x in linhas:
        pri, pub = x.get("privada"), x.get("publica")
        pos = f"{x['posicao']}º" if x["posicao"] else "—"
        if not pri or not pri.get("valida"):
            motivo = (pri or {}).get("motivo", "sem resposta na janela privada")
            print(f"{pos:<4}{x['equipe']:<22}{'REPROVADA':>8}   {motivo[:38]}")
            continue
        sp = f"{pub['score']:.1f}" if pub and pub.get("valida") else "—"
        print(f"{pos:<4}{x['equipe']:<22}{pri['score']:>8.2f}"
              f"{pri['otif']:>9.1%}{pri['otif_ka']:>9.1%}"
              f"{'R$ ' + format(pri['custo_total'], ',.0f').replace(',', '.'):>14}"
              f"   {sp:>8}")
    print("\n  ranking pela janela PRIVADA · a coluna 'pública' é só referência")
    print("  quem vai muito melhor na pública que na privada otimizou o leaderboard")


def main():
    ap = argparse.ArgumentParser(description="Consolida o ranking das equipes")
    ap.add_argument("--publicar", action="store_true",
                    help="grava docs/dados/ranking.json para o site")
    args = ap.parse_args()

    oficial = os.path.exists(os.path.join(PRIVADO, "realized_transit.csv"))
    if not oficial:
        print("Gabarito ausente — o ranking oficial só sai na máquina dos organizadores.")
        print(f"Esperado em: {PRIVADO}")
        sys.exit(2)

    linhas = coletar()
    if not linhas:
        print("Nenhuma equipe em respostas/. Nada a ranquear.")
        return 0

    tabela(linhas)

    if args.publicar:
        saida = {"gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "modo": "oficial", "equipes": linhas}
        os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
        with open(DESTINO, "w", encoding="utf-8", newline="\n") as f:
            json.dump(saida, f, ensure_ascii=False, indent=1)
        print(f"\n  ranking gravado em {DESTINO}")
        print("  rode gerar_site.py para publicar a página")
    return 0


if __name__ == "__main__":
    sys.exit(main())
