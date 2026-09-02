"""
Confere o contraste de cada par texto/fundo do site.

Existe por um motivo específico: o design system da Apllos é dark-only e o site
era light-first. Trocar os tokens sem medir é como se pinta texto preto em fundo
preto — e ninguém percebe até alguém abrir a página.

Mede o contraste WCAG (relação de luminância) e reprova o que ficar abaixo do
piso. Os pisos seguem a WCAG 2.1:

    4.5:1  texto corrido
    3.0:1  texto grande (>= 24px ou >= 19px em negrito) e elementos gráficos

Uso:
    python desafio/gerador/conferir_contraste.py
    python desafio/gerador/conferir_contraste.py --css docs/assets/site.css
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


# ------------------------------------------------------------------ cor
def _canal(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminancia(rgb):
    r, g, b = (_canal(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(frente, fundo):
    a, b = luminancia(frente), luminancia(fundo)
    claro, escuro = max(a, b), min(a, b)
    return (claro + 0.05) / (escuro + 0.05)


def ler_cor(txt, fundo=(18, 18, 18)):
    """Aceita #rgb, #rrggbb e rgba(); compõe alfa sobre o fundo informado."""
    txt = txt.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{3})", txt)
    if m:
        return tuple(int(c * 2, 16) for c in m.group(1))
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", txt)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)",
                     txt)
    if m:
        r, g, b = (float(m.group(i)) for i in (1, 2, 3))
        a = float(m.group(4)) if m.group(4) else 1.0
        return tuple(round(v * a + f * (1 - a)) for v, f in zip((r, g, b), fundo))
    return None


def resolver(valor, tokens, fundo, visitados=None):
    """Resolve var(--x) recursivamente até chegar num literal."""
    visitados = visitados or set()
    valor = valor.strip()
    m = re.fullmatch(r"var\(\s*(--[a-z0-9-]+)\s*(?:,[^)]*)?\)", valor)
    if m:
        nome = m.group(1)
        if nome in visitados or nome not in tokens:
            return None
        visitados.add(nome)
        return resolver(tokens[nome], tokens, fundo, visitados)
    return ler_cor(valor, fundo)


# ------------------------------------------------------------------ pares
# (nome do par, token do texto, token do fundo, piso)
PARES = [
    ("corpo sobre a página",            "--ink",      "--ground",    4.5),
    ("corpo sobre superfície",          "--ink",      "--surface",   4.5),
    ("corpo sobre superfície elevada",  "--ink",      "--surface-2", 4.5),
    ("texto secundário na página",      "--ink-2",    "--ground",    4.5),
    ("texto secundário na superfície",  "--ink-2",    "--surface",   4.5),
    ("texto apagado na página",         "--ink-3",    "--ground",    4.5),
    ("texto apagado na superfície",     "--ink-3",    "--surface",   4.5),
    ("acento sobre a página",           "--accent",   "--ground",    4.5),
    ("acento sobre superfície",         "--accent",   "--surface",   4.5),
    ("acento sobre tinta de acento",    "--accent",   "--accent-2",  4.5),
    ("sinal sobre a página",            "--signal",   "--ground",    4.5),
    ("sinal sobre tinta de sinal",      "--signal",   "--signal-2",  4.5),
    ("status bom sobre superfície",     "--bom",      "--surface",   4.5),
    ("status alerta sobre superfície",  "--alerta",   "--surface",   4.5),
    ("série 1 (gráfico)",               "--serie-1",  "--surface",   3.0),
    ("série 2 (gráfico)",               "--serie-2",  "--surface",   3.0),
    ("trilho do gráfico",               "--trilho",   "--surface",   1.2),
    ("borda sobre superfície",          "--line",     "--surface",   1.2),
]


def tokens_de(css, escopo=":root"):
    """Extrai os tokens declarados no primeiro bloco :root."""
    m = re.search(re.escape(escopo) + r"\s*\{(.*?)\}", css, re.S)
    if not m:
        return {}
    return {k.strip(): v.strip()
            for k, v in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", m.group(1))}


def conferir(css, nome_arquivo):
    tokens = tokens_de(css)
    if not tokens:
        return []
    fundo_base = ler_cor(tokens.get("--ground", "#121212")) or (18, 18, 18)
    achados = []
    for rotulo, tf, tb, piso in PARES:
        if tf not in tokens or tb not in tokens:
            continue
        cf = resolver(tokens[tf], tokens, fundo_base)
        cb = resolver(tokens[tb], tokens, fundo_base)
        if not cf or not cb:
            achados.append((rotulo, None, piso, "não consegui resolver a cor"))
            continue
        r = contraste(cf, cb)
        achados.append((rotulo, r, piso, "ok" if r >= piso else "ABAIXO DO PISO"))
    return achados


def cores_cruas(css):
    """Cores literais fora do bloco de tokens — candidatas a passar despercebidas."""
    corpo = re.sub(r":root[^{]*\{.*?\}", "", css, flags=re.S)
    achadas = set()
    for m in re.finditer(r"(?:color|background|background-color|fill|border-color)\s*:\s*"
                         r"(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))", corpo):
        achadas.add(m.group(1))
    return sorted(achadas)


def main():
    ap = argparse.ArgumentParser(description="Confere contraste dos pares texto/fundo")
    ap.add_argument("--css", default=None)
    args = ap.parse_args()

    alvos = ([args.css] if args.css
             else [os.path.join("docs", "assets", "site.css")] +
                  sorted(glob.glob(os.path.join("docs", "desafio", "*.html"))))

    falhas = 0
    for alvo in alvos:
        if not os.path.exists(alvo):
            continue
        css = open(alvo, encoding="utf-8").read()
        achados = conferir(css, alvo)
        if not achados:
            continue
        ruins = [a for a in achados if a[3] != "ok"]
        print(f"\n{alvo}   {len(achados)} pares · "
              f"{'todos acima do piso' if not ruins else str(len(ruins)) + ' ABAIXO'}")
        for rotulo, r, piso, estado in achados:
            marca = "  " if estado == "ok" else "!!"
            valor = f"{r:5.2f}:1" if r else "   ?  "
            print(f"  {marca} {rotulo:<34} {valor}  piso {piso}")
        cruas = cores_cruas(css)
        if cruas:
            print(f"     cores literais fora dos tokens: {', '.join(cruas[:8])}"
                  + (" …" if len(cruas) > 8 else ""))
        falhas += len(ruins)

    print(f"\ntotal abaixo do piso: {falhas}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
