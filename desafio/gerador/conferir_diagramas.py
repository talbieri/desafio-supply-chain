"""
Detecta texto sobreposto nos diagramas SVG das páginas.

SVG não quebra linha e não avisa quando um rótulo invade o vizinho — o erro só
aparece no navegador, e só se alguém olhar. Este script estima a extensão de
cada <text> pela classe que ele usa e acusa três problemas:

  1. texto que passa da borda do viewBox
  2. texto que invade um retângulo em que não está contido
  3. texto que colide com outro texto na mesma faixa vertical

As larguras são estimativas por caractere, calibradas para as fontes do site.
Não substituem olhar a página, mas pegam o que o olho deixa passar.

Uso:
    python desafio/gerador/conferir_diagramas.py
    python desafio/gerador/conferir_diagramas.py --pagina docs/conceitos.html
"""

import argparse
import glob
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

# largura média por caractere, em unidades do viewBox
# Calibrado contra a medição real do navegador (getBBox), com folga de 5%:
# a estimativa anterior deixava passar um estouro de 9px na figura dos fluxos.
LARGURA = {"svg-small": 6.7, "svg-num": 6.95, "svg-label": 7.9, "": 8.4}
ALTURA = {"svg-small": 11, "svg-num": 11, "svg-label": 14, "": 16}


def largura_texto(texto, classes):
    for c, w in LARGURA.items():
        if c and c in classes:
            return len(texto) * w, ALTURA[c]
    return len(texto) * LARGURA[""], ALTURA[""]


def extrair_svgs(html):
    return re.findall(r"<svg\b[^>]*viewBox=\"0 0 ([\d.]+) ([\d.]+)\"[^>]*>(.*?)</svg>",
                      html, re.S)


def analisar(nome, largura_vb, altura_vb, corpo, indice):
    achados = []
    textos = []
    for m in re.finditer(r'<text\s+x="([-\d.]+)"\s+y="([-\d.]+)"([^>]*)>([^<]*)</text>', corpo):
        x, y, atrs, txt = float(m.group(1)), float(m.group(2)), m.group(3), m.group(4)
        if not txt.strip():
            continue
        w, h = largura_texto(txt, atrs)
        ancora = "middle" if 'text-anchor="middle"' in atrs else "start"
        girado = "transform=" in atrs
        x0 = x - w / 2 if ancora == "middle" else x
        textos.append(dict(x=x0, y=y, w=w, h=h, txt=txt, girado=girado))

    rects = [(float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))
             for m in re.finditer(
                 r'<rect\s+x="([-\d.]+)"\s+y="([-\d.]+)"\s+width="([\d.]+)"\s+height="([\d.]+)"',
                 corpo)]

    for t in textos:
        if t["girado"]:
            continue
        # 1. fora do viewBox
        if t["x"] + t["w"] > largura_vb + 1:
            achados.append(("borda", f'"{t["txt"][:44]}" termina em '
                                     f'{t["x"] + t["w"]:.0f}, viewBox tem {largura_vb:.0f}'))
        if t["y"] > altura_vb - 1:
            achados.append(("borda", f'"{t["txt"][:44]}" em y={t["y"]:.0f}, '
                                     f'viewBox tem {altura_vb:.0f}'))

        # 2. invade retângulo em que não começa
        for rx, ry, rw, rh in rects:
            dentro_inicio = rx <= t["x"] <= rx + rw and ry <= t["y"] <= ry + rh
            cruza = (t["x"] < rx < t["x"] + t["w"]) and (ry - 4 <= t["y"] <= ry + rh + 4)
            if cruza and not dentro_inicio:
                achados.append(("caixa", f'"{t["txt"][:44]}" invade a caixa em x={rx:.0f} '
                                         f'(texto vai de {t["x"]:.0f} a {t["x"] + t["w"]:.0f})'))
                break

    # 3. texto contra texto
    for i, a in enumerate(textos):
        for b in textos[i + 1:]:
            if a["girado"] or b["girado"]:
                continue
            if abs(a["y"] - b["y"]) > max(a["h"], b["h"]) * 0.7:
                continue
            if a["x"] < b["x"] + b["w"] - 2 and b["x"] < a["x"] + a["w"] - 2:
                achados.append(("texto", f'"{a["txt"][:30]}" e "{b["txt"][:30]}" '
                                         f'se sobrepõem em y≈{a["y"]:.0f}'))

    return achados


def main():
    ap = argparse.ArgumentParser(description="Confere colisões nos diagramas SVG")
    ap.add_argument("--pagina", default=None)
    args = ap.parse_args()

    paginas = ([args.pagina] if args.pagina
               else sorted(glob.glob(os.path.join("docs", "*.html")) +
                           glob.glob(os.path.join("docs", "desafio", "*.html"))))

    total = 0
    for pag in paginas:
        if not os.path.exists(pag):
            continue
        html = open(pag, encoding="utf-8").read()
        svgs = extrair_svgs(html)
        if not svgs:
            continue
        problemas_pagina = []
        for i, (lv, av, corpo) in enumerate(svgs, 1):
            for tipo, msg in analisar(pag, float(lv), float(av), corpo, i):
                problemas_pagina.append((i, tipo, msg))
        marca = "OK" if not problemas_pagina else f"{len(problemas_pagina)} problemas"
        print(f"{pag}  ({len(svgs)} diagramas)  {marca}")
        for i, tipo, msg in problemas_pagina:
            print(f"    fig {i} · {tipo:<6} {msg}")
        total += len(problemas_pagina)

    print(f"\ntotal: {total} problemas")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
