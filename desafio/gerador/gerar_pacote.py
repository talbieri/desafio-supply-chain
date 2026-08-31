"""
Monta o pacote inteiro do desafio, na ordem certa.

  1. gera os dados          (gerar_dados.py)
  2. gera o dicionário      (gerar_dicionario.py)
  3. calcula os checksums   de tudo que será publicado
  4. empacota o .zip        distribuível
  5. confere que o gabarito não vazou para o pacote
  6. monta o site em docs/  pronto para o GitHub Pages
  7. confere os diagramas  procura texto sobreposto nos SVGs

Determinístico: mesma seed, mesmos checksums. Se dois builds divergirem,
alguma coisa no gerador deixou de ser reprodutível — investigue antes de publicar.

Uso:
    python desafio/gerador/gerar_pacote.py
    python desafio/gerador/gerar_pacote.py --verificar   # só confere, não regrava
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import zipfile
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parametros as P  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

PASTA = os.path.join("desafio", "dados", "v" + P.VERSAO)
PRIVADO = os.path.join("desafio", "privado")
PUBLICAVEIS = (".csv", ".md")


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def hashes_atuais():
    if not os.path.isdir(PASTA):
        return {}
    return {a: sha256(os.path.join(PASTA, a))
            for a in sorted(os.listdir(PASTA)) if a.endswith(PUBLICAVEIS)}


def rodar(script):
    print(f"\n─── {script}")
    r = subprocess.run([sys.executable, os.path.join("desafio", "gerador", script)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        sys.exit(f"falhou: {script}")
    for linha in r.stdout.strip().splitlines()[-4:]:
        print("    " + linha)


def escrever_checksums():
    arquivos = sorted(a for a in os.listdir(PASTA) if a.endswith(PUBLICAVEIS))
    linhas = [f"# Desafio Supply Chain - pacote de dados v{P.VERSAO}",
              f"# seed={P.SEED}",
              "# verificacao (qualquer sistema): python desafio/ferramentas/conferir_dados.py",
              "# verificacao (macOS/Linux/Git Bash): sha256sum -c CHECKSUMS.txt", ""]
    for a in arquivos:
        linhas.append(f"{sha256(os.path.join(PASTA, a))}  {a}")
    # newline="\n" em todo escritor: no Windows o padrão grava CRLF, o git
    # normaliza para LF ao versionar, e o checksum deixa de bater para quem
    # baixa em macOS ou Linux. O CI pegou exatamente isso.
    with open(os.path.join(PASTA, "CHECKSUMS.txt"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write("\n".join(linhas) + "\n")
    return len(arquivos)


def conferir_vazamento(caminho_zip):
    import zipfile
    with zipfile.ZipFile(caminho_zip) as z:
        nomes = z.namelist()
    suspeitos = [n for n in nomes
                 if "realized" in n or "/privado/" in n or "gabarito" in n]
    return nomes, suspeitos


def main():
    ap = argparse.ArgumentParser(description="Monta o pacote do desafio")
    ap.add_argument("--verificar", action="store_true",
                    help="regera e compara com o pacote atual, sem publicar")
    args = ap.parse_args()

    antes = hashes_atuais()

    rodar("gerar_dados.py")
    rodar("gerar_dicionario.py")

    n = escrever_checksums()
    print(f"\n─── checksums: {n} arquivos")

    depois = hashes_atuais()
    if antes:
        divergentes = [a for a in depois if antes.get(a) and antes[a] != depois[a]]
        novos = [a for a in depois if a not in antes]
        if divergentes:
            print(f"\n  ATENÇÃO: {len(divergentes)} arquivos mudaram entre builds:")
            for a in divergentes[:10]:
                print(f"    {a}")
            print("  O gerador deixou de ser determinístico. Não publique assim.")
        else:
            print(f"  determinismo confirmado: {len(depois) - len(novos)} arquivos idênticos "
                  "ao build anterior")

    if args.verificar:
        print("\nmodo --verificar: zip não regravado")
        return

    # O pacote leva os dados E as ferramentas. Só com os CSVs, quem baixa o zip
    # não consegue rodar o baseline nem o avaliador — o guia de 30 minutos
    # travaria no segundo passo. O layout espelha o repositório, então os
    # comandos documentados funcionam sem ajuste de caminho.
    caminho_zip = os.path.join("desafio", "dados",
                               f"desafio-supply-chain-v{P.VERSAO}.zip")
    if os.path.exists(caminho_zip):
        os.remove(caminho_zip)
    with zipfile.ZipFile(caminho_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for arq in sorted(os.listdir(PASTA)):
            z.write(os.path.join(PASTA, arq), f"desafio/dados/v{P.VERSAO}/{arq}")
        for pasta in ("ferramentas", "gerador"):
            base = os.path.join("desafio", pasta)
            for arq in sorted(os.listdir(base)):
                if arq.endswith(".py"):
                    z.write(os.path.join(base, arq), f"desafio/{pasta}/{arq}")
        z.write(os.path.join("desafio", "README.md"), "desafio/README.md")
        z.write("README.md", "README.md")
    nomes, suspeitos = conferir_vazamento(caminho_zip)

    print(f"\n─── pacote: {caminho_zip}")
    print(f"    {len(nomes)} arquivos · {os.path.getsize(caminho_zip) / 1024 / 1024:.2f} MB")
    if suspeitos:
        os.remove(caminho_zip)
        sys.exit(f"VAZAMENTO DE GABARITO — zip removido: {suspeitos}")
    print("    gabarito não vazou: OK")
    print(f"    gabarito segue em {PRIVADO}/ (não distribuir)")

    # o site publicado é montado por último, já com o pacote final
    rodar("gerar_site.py")

    # SVG não avisa quando um rótulo invade o vizinho: o erro só aparece no
    # navegador, e só se alguém olhar. Por isso o conferidor roda em todo build.
    print("\n─── conferir_diagramas.py")
    r = subprocess.run([sys.executable,
                        os.path.join("desafio", "gerador", "conferir_diagramas.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    saida = r.stdout.strip().splitlines()
    print("    " + (saida[-1] if saida else "sem saída"))
    if r.returncode != 0:
        for linha in saida:
            if " · " in linha:
                print("    " + linha.strip())
        print("    Corrija antes de publicar: há texto sobreposto nos diagramas.")

    print("\n─── site em docs/ — publique com GitHub Pages (branch main, pasta /docs)")


if __name__ == "__main__":
    main()
