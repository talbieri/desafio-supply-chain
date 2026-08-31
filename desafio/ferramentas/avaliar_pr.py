"""
Avalia as respostas enviadas e escreve a nota em Markdown.

É a peça que o GitHub Actions chama quando alguém abre um pull request com uma
resposta. Roda igual na sua máquina, então dá para conferir o que o robô vai
dizer antes de abrir o PR.

Espera esta estrutura:

    respostas/
      <nome-da-equipe>/
        public/
          resposta_promessa.csv
          resposta_rebalanceamento.csv   (opcional)
          resposta_previsao.csv          (opcional)
        private/
          ...

Uso:
    python desafio/ferramentas/avaliar_pr.py                      # todas as equipes
    python desafio/ferramentas/avaliar_pr.py --equipe minha-equipe
    python desafio/ferramentas/avaliar_pr.py --saida nota.md
"""

import argparse
import json
import os
import subprocess
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
AVALIAR = os.path.join(RAIZ, "desafio", "ferramentas", "avaliar.py")
RESPOSTAS = os.path.join(RAIZ, "respostas")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def roda(pasta, janela):
    """Chama o avaliador e devolve (ok, dados_ou_erro)."""
    r = subprocess.run([sys.executable, AVALIAR, "--resposta", pasta,
                        "--janela", janela, "--json"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=RAIZ)
    if r.returncode != 0 or not r.stdout.strip().startswith("{"):
        motivo = (r.stdout or r.stderr or "").strip()
        return False, motivo[:1500]
    return True, json.loads(r.stdout)


def equipes():
    if not os.path.isdir(RESPOSTAS):
        return []
    return sorted(d for d in os.listdir(RESPOSTAS)
                  if os.path.isdir(os.path.join(RESPOSTAS, d))
                  and not d.startswith(".") and d != "EXEMPLO")


def linha_metrica(rot, valor, meta, fmt="%", direcao=1):
    ok = (valor >= meta) if direcao == 1 else (valor <= meta)
    marca = "✅" if ok else "⚠️"
    if fmt == "%":
        casas = 1 if round(meta * 100, 1) != round(meta * 100) else 0
        v = f"{valor:.1%}".replace(".", ",")
        m = f"{meta * 100:.{casas}f}".replace(".", ",") + "%"
    else:
        v, m = f"R$ {valor:,.0f}".replace(",", "."), "—"
    return f"| {rot} | {v} | {m} | {marca} |"


def bloco(nome, janela, ok, dados):
    if not ok:
        return (f"### {janela}\n\n"
                f"**Resposta reprovada.** O avaliador não pontua uma resposta que falha "
                f"nos gates — igual ao ranking final.\n\n```\n{dados}\n```\n")
    m = dados["metricas"]
    sc = dados.get("score", {})
    linhas = [f"### {janela}", "",
              "| Métrica | Sua resposta | Meta | |",
              "|---|---|---|---|",
              linha_metrica("OTIF (data do cliente)", m["otif"], 0.95),
              linha_metrica("OTIF Key Account", m["otif_ka"], 0.98),
              linha_metrica("Promise Reliability", m["promise_reliability"], 0.96),
              linha_metrica("In Full", m["in_full"], 0.97),
              linha_metrica("Fill Rate (valor)", m["fill_rate_valor"], 0.96),
              linha_metrica("Ocupação do veículo", m["ocupacao_media_veiculo"], 0.80),
              linha_metrica("Custo logístico / receita", m["custo_logistico_pct"], 0.085,
                            direcao=-1),
              f"| **Custo total** | **R$ {m['custo_total']:,.0f}".replace(",", ".") +
              "** | — | |", ""]
    if sc:
        linhas += [f"**Score: {sc['total']:.2f} de {sc['maximo_automatico']:.0f} pontos "
                   f"automáticos**", "",
                   "| Dimensão | Pontos | Teto |", "|---|---|---|"]
        teto = {"promise_reliability": 25, "otif": 12, "fill_rate": 8,
                "custo": 25, "preditiva": 20}
        for k, v in sc["componentes"].items():
            linhas.append(f"| {k} | {v:.2f} | {teto.get(k, '—')} |")
        if sc.get("penalidades"):
            linhas.append(f"\nPenalidades aplicadas: `{sc['penalidades']}`")
        linhas.append("")
    return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser(description="Avalia respostas e escreve a nota em Markdown")
    ap.add_argument("--equipe", default=None, help="avalia só esta equipe")
    ap.add_argument("--saida", default=None, help="grava o Markdown neste arquivo")
    args = ap.parse_args()

    alvos = [args.equipe] if args.equipe else equipes()
    if not alvos:
        texto = ("Nenhuma resposta encontrada em `respostas/`.\n\n"
                 "Crie `respostas/<sua-equipe>/public/resposta_promessa.csv` "
                 "e abra o pull request de novo.")
        print(texto)
        if args.saida:
            open(args.saida, "w", encoding="utf-8").write(texto)
        return 0

    partes = ["## Nota da sua resposta", ""]
    houve_falha = False
    modos = set()
    for eq in alvos:
        partes.append(f"### Equipe `{eq}`")
        partes.append("")
        for janela, rot in (("public", "Janela pública"), ("private", "Janela privada")):
            pasta = os.path.join("respostas", eq, janela)
            if not os.path.exists(os.path.join(RAIZ, pasta, "resposta_promessa.csv")):
                partes.append(f"### {rot}\n\nSem `resposta_promessa.csv` — janela não avaliada.\n")
                continue
            ok, dados = roda(pasta, janela)
            houve_falha = houve_falha or not ok
            if ok:
                modos.add(dados.get("modo", "treino"))
            partes.append(bloco(eq, rot, ok, dados))
        partes.append("---\n")

    if "oficial" in modos:
        partes += [
            "> **Nota OFICIAL**, calculada contra o gabarito. É esta que vale.",
        ]
    else:
        partes += [
            "> **Esta nota é do modo TREINO.** O trânsito realizado das janelas de teste fica "
            "lacrado com os organizadores; aqui ele é sorteado da distribuição histórica com "
            "semente fixa. Roda sempre igual e serve para comparar duas versões da sua "
            "solução — mas espere alguns pontos de diferença para a nota oficial, calculada "
            "no encerramento.",
            "",
            "> Os **gates são os mesmos** nos dois modos. Se reprovou aqui, reprova lá.",
        ]

    texto = "\n".join(partes)
    print(texto)
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as f:
            f.write(texto)
    return 1 if houve_falha else 0


if __name__ == "__main__":
    sys.exit(main())
