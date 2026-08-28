"""
Confere a integridade do pacote de dados.

Faz o mesmo que `sha256sum -c CHECKSUMS.txt`, mas funciona em Windows, macOS e
Linux — `sha256sum` não existe no PowerShell nem no cmd, e o primeiro passo do
guia não pode depender de qual terminal você abriu.

Uso:
    python desafio/ferramentas/conferir_dados.py
    python desafio/ferramentas/conferir_dados.py --dados desafio/dados/v1.0.0
"""

import argparse
import hashlib
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

PADRAO = os.path.join("desafio", "dados", "v1.0.0")


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="Confere os checksums do pacote de dados")
    ap.add_argument("--dados", default=PADRAO, help="pasta com CHECKSUMS.txt")
    args = ap.parse_args()

    arquivo = os.path.join(args.dados, "CHECKSUMS.txt")
    if not os.path.exists(arquivo):
        print(f"Não encontrei {arquivo}")
        print()
        print("  Rode a partir da raiz do projeto, ou aponte a pasta:")
        print("    python desafio/ferramentas/conferir_dados.py --dados caminho/para/v1.0.0")
        sys.exit(2)

    esperados = []
    with open(arquivo, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            digest, _, nome = linha.partition("  ")
            if digest and nome:
                esperados.append((nome, digest))

    ok, quebrados, faltando = 0, [], []
    for nome, esperado in esperados:
        caminho = os.path.join(args.dados, nome)
        if not os.path.exists(caminho):
            faltando.append(nome)
            continue
        if sha256(caminho) == esperado:
            ok += 1
        else:
            quebrados.append(nome)

    print(f"Conferindo {len(esperados)} arquivos em {args.dados}")
    print()
    print(f"  íntegros ....... {ok}")
    if faltando:
        print(f"  faltando ....... {len(faltando)}")
        for n in faltando[:10]:
            print(f"      {n}")
    if quebrados:
        print(f"  corrompidos .... {len(quebrados)}")
        for n in quebrados[:10]:
            print(f"      {n}")

    print()
    if quebrados or faltando:
        print("  O download veio incompleto ou corrompido. Baixe o pacote de novo")
        print("  antes de perder tempo depurando o que não é problema seu.")
        sys.exit(1)

    print("  Pacote íntegro. Pode começar.")
    print()
    print("  Próximo passo:")
    print("    python desafio/ferramentas/baseline_atual.py --janela public")


if __name__ == "__main__":
    main()
