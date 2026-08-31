"""
Monta o site estático do desafio em `docs/`, pronto para o GitHub Pages.

O GitHub Pages publica `docs/` da branch principal sem nenhuma configuração
extra — daí a escolha da pasta. O site inclui os CSVs, então o time baixa tudo
direto da página, sem pedir acesso a ninguém.

Produz:
    docs/index.html        página inicial: o que é o desafio e como começar
    docs/dados.html        todos os arquivos, com tamanho, linhas e checksum
    docs/regras.html       as 40 regras de negócio (versão autônoma)
    docs/conceitos.html    material auxiliar de supply chain (versão autônoma)
    docs/assets/site.css   folha de estilo compartilhada
    docs/dados/v1.0.0/     os CSVs, o dicionário e o pacote .zip
    docs/.nojekyll         impede o Jekyll de esconder arquivos

Uso:
    python desafio/gerador/gerar_site.py
"""

import csv
import hashlib
import os
import shutil
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parametros as P  # noqa: E402
from gerar_dicionario import TABELAS  # noqa: E402
import placar_html  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DADOS = os.path.join(RAIZ, "desafio", "dados", "v" + P.VERSAO)
SITE = os.path.join(RAIZ, "docs")
FONTES = os.path.join(SITE, "desafio")

FONTES_HTML = [
    ("regras-da-rede.html", "regras.html", "Regras de Atendimento"),
    ("supply-chain-do-zero.html", "conceitos.html", "Supply Chain do Zero"),
]

CABECA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
"""

NAV = """<nav class="sitenav">
  <div class="sitenav-in">
    <a class="marca" href="./index.html">Desafio&nbsp;Supply&nbsp;Chain</a>
    <span class="sep"></span>
    <a href="./index.html"{a0}>Início</a>
    <a href="./dados.html"{a1}>Dados</a>
    <a href="./placar.html"{a4}>Placar</a>
    <a href="./regras.html"{a2}>Regras</a>
    <a href="./conceitos.html"{a3}>Conceitos</a>
  </div>
</nav>
"""

ESTILO_NAV = """
/* barra de navegação do site — injetada pelo gerador */
.sitenav { background: var(--ink); border-bottom: 1px solid var(--ink); }
.sitenav-in {
  max-width: 1140px; margin: 0 auto; padding: 0 28px;
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
}
.sitenav a {
  display: block; padding: 12px 12px; text-decoration: none;
  font-family: var(--mono); font-size: 11.5px; letter-spacing: .1em;
  text-transform: uppercase; color: #9fb3ae;
}
.sitenav a:hover, .sitenav a:focus-visible { color: #fff; }
.sitenav a.ativo { color: #fff; box-shadow: inset 0 -2px 0 var(--accent); }
.sitenav .marca {
  font-family: var(--display); font-weight: 700; font-size: 14px;
  letter-spacing: -.01em; text-transform: none; color: #fff; padding-left: 0;
}
.sitenav .sep { flex: 1; }
@media (max-width: 720px) { .sitenav-in { padding: 0 20px; } .sitenav .sep { flex: 0; } }
"""


def nav(ativo):
    marcas = ["", "", "", "", ""]
    if ativo is not None:
        marcas[ativo] = ' class="ativo"'
    return NAV.format(a0=marcas[0], a1=marcas[1], a2=marcas[2], a3=marcas[3],
                      a4=marcas[4])


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def kb(caminho):
    tam = os.path.getsize(caminho)
    return f"{tam / 1024 / 1024:.2f} MB" if tam > 900_000 else f"{tam / 1024:.0f} KB"


def linhas_csv(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)


# ====================================================================
# Páginas autônomas a partir das fontes
# ====================================================================

def converter(origem, destino, indice_nav):
    """Envelopa a fonte (formato de artifact) num documento HTML completo."""
    with open(origem, encoding="utf-8") as f:
        conteudo = f.read()
    corte = conteudo.index("<header")
    cabeca, corpo = conteudo[:corte], conteudo[corte:]
    cabeca = cabeca.replace("</style>", ESTILO_NAV + "</style>")
    html = CABECA + cabeca + "</head>\n<body>\n" + nav(indice_nav) + corpo + "\n</body>\n</html>\n"
    with open(destino, "w", encoding="utf-8") as f:
        f.write(html)
    return len(html)


# ====================================================================
# Folha de estilo compartilhada
# ====================================================================

CSS = """/* Desafio Supply Chain — folha compartilhada das páginas do site.
   Mesma paleta das páginas de regras e conceitos: teal de despacho e
   âmbar de sinalização sobre neutros levemente esverdeados. */

:root {
  --ground:#E9EDEB; --surface:#FDFEFD; --surface-2:#DFE5E2;
  --line:#C6CFCB; --line-soft:#D8DFDC;
  --ink:#101715; --ink-2:#3D4B47; --ink-3:#66756F;
  --accent:#0D5B60; --accent-2:#E3EDED;
  --signal:#A8480D; --signal-2:#F6E6DA; --moss:#3D6B3E;
  --shadow:0 1px 2px rgba(16,23,21,.05), 0 8px 24px -16px rgba(16,23,21,.28);
  --display:"Archivo","Helvetica Neue",Arial,sans-serif;
  --body:"Source Serif 4",Georgia,"Times New Roman",serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --measure:68ch; --wide:1140px;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:#0D1412; --surface:#151E1B; --surface-2:#1D2825;
    --line:#2C3B37; --line-soft:#23302C;
    --ink:#E7EDEA; --ink-2:#B3C1BC; --ink-3:#82918C;
    --accent:#52B7BC; --accent-2:#18302F;
    --signal:#DE8B4A; --signal-2:#33251A; --moss:#7FAE7A;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 28px -18px rgba(0,0,0,.8);
  }
}
:root[data-theme="dark"] {
  --ground:#0D1412; --surface:#151E1B; --surface-2:#1D2825;
  --line:#2C3B37; --line-soft:#23302C;
  --ink:#E7EDEA; --ink-2:#B3C1BC; --ink-3:#82918C;
  --accent:#52B7BC; --accent-2:#18302F;
  --signal:#DE8B4A; --signal-2:#33251A; --moss:#7FAE7A;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 28px -18px rgba(0,0,0,.8);
}

* { box-sizing:border-box; }
body {
  margin:0; background:var(--ground); color:var(--ink);
  font-family:var(--body); font-size:17px; line-height:1.65;
  -webkit-font-smoothing:antialiased;
}
.shell { max-width:var(--wide); margin:0 auto; padding:0 28px; }
.col { max-width:var(--measure); }

/* nav do site */
.sitenav { background:var(--ink); }
.sitenav-in { max-width:var(--wide); margin:0 auto; padding:0 28px; display:flex; align-items:center; gap:4px; flex-wrap:wrap; }
.sitenav a { display:block; padding:12px; text-decoration:none; font-family:var(--mono); font-size:11.5px; letter-spacing:.1em; text-transform:uppercase; color:#9fb3ae; }
.sitenav a:hover, .sitenav a:focus-visible { color:#fff; }
.sitenav a.ativo { color:#fff; box-shadow:inset 0 -2px 0 var(--accent); }
.sitenav .marca { font-family:var(--display); font-weight:700; font-size:14px; letter-spacing:-.01em; text-transform:none; color:#fff; padding-left:0; }
.sitenav .sep { flex:1; }

/* cabeçalho */
.masthead { border-bottom:1px solid var(--line); background:var(--surface); padding:64px 0 44px; }
.kicker { font-family:var(--mono); font-size:11.5px; letter-spacing:.18em; text-transform:uppercase; color:var(--accent); margin:0 0 22px; display:flex; align-items:center; gap:12px; }
.kicker::after { content:""; flex:1; height:1px; background:var(--line); max-width:220px; }
h1 { font-family:var(--display); font-weight:800; font-size:clamp(40px,7vw,74px); line-height:.96; letter-spacing:-.035em; margin:0 0 22px; text-wrap:balance; max-width:17ch; }
h1 em { font-style:normal; color:var(--accent); }
.standfirst { font-size:20px; line-height:1.5; color:var(--ink-2); max-width:58ch; margin:0 0 30px; }

.facts { display:grid; grid-template-columns:repeat(auto-fit,minmax(148px,1fr)); gap:1px; background:var(--line); border:1px solid var(--line); }
.fact { background:var(--surface); padding:16px 18px; }
.fact b { display:block; font-family:var(--display); font-weight:700; font-size:27px; letter-spacing:-.02em; line-height:1.1; font-variant-numeric:tabular-nums; }
.fact span { font-family:var(--mono); font-size:10.5px; letter-spacing:.13em; text-transform:uppercase; color:var(--ink-3); }

/* seções */
main { padding-bottom:80px; }
section { padding:56px 0; border-bottom:1px solid var(--line-soft); }
section:last-of-type { border-bottom:none; }
.tag { font-family:var(--mono); font-size:11px; letter-spacing:.16em; text-transform:uppercase; color:var(--signal); margin:0 0 10px; }
h2 { font-family:var(--display); font-weight:700; font-size:clamp(26px,3.4vw,36px); letter-spacing:-.025em; line-height:1.1; margin:0 0 14px; text-wrap:balance; }
h3 { font-family:var(--display); font-weight:700; font-size:17px; margin:36px 0 12px; }
p { margin:0 0 18px; }
.lead { font-size:19px; color:var(--ink-2); }
a { color:var(--accent); }
code { font-family:var(--mono); font-size:.855em; background:var(--surface-2); padding:1.5px 5px; border-radius:3px; color:var(--ink); }

/* tabelas */
.scroll { overflow-x:auto; margin:0 0 22px; border:1px solid var(--line); background:var(--surface); }
table { width:100%; border-collapse:collapse; font-family:var(--display); font-size:14.5px; min-width:520px; }
thead th { text-align:left; font-family:var(--mono); font-weight:600; font-size:10.5px; letter-spacing:.12em; text-transform:uppercase; color:var(--ink-3); padding:12px 16px; border-bottom:1px solid var(--line); background:var(--surface-2); white-space:nowrap; }
tbody td { padding:11px 16px; border-bottom:1px solid var(--line-soft); vertical-align:top; color:var(--ink-2); }
tbody tr:last-child td { border-bottom:none; }
tbody td:first-child { color:var(--ink); font-weight:600; }
td.num, th.num { text-align:right; font-family:var(--mono); font-variant-numeric:tabular-nums; white-space:nowrap; }
tbody tr:hover td { background:var(--accent-2); }
tr.destaque td { background:var(--signal-2); }
tr.destaque:hover td { background:var(--signal-2); }

/* cartões */
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(268px,1fr)); gap:1px; background:var(--line); border:1px solid var(--line); margin-bottom:24px; }
.cell { background:var(--surface); padding:20px; }
.cell .code { font-family:var(--mono); font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--accent); display:block; margin-bottom:8px; }
.cell h4 { font-family:var(--display); font-weight:700; font-size:15.5px; margin:0 0 7px; }
.cell p { margin:0; font-size:15.5px; color:var(--ink-2); }

/* download */
.baixar { display:flex; flex-wrap:wrap; gap:14px; align-items:center; margin:0 0 26px; }
.btn { display:inline-block; padding:14px 24px; background:var(--accent); color:#fff; text-decoration:none; font-family:var(--display); font-weight:700; font-size:15px; border:1px solid transparent; }
.btn:hover { filter:brightness(1.1); }
.btn.sec { background:var(--surface); color:var(--accent); border-color:var(--line); }
.baixar .meta { font-family:var(--mono); font-size:12px; color:var(--ink-3); }

pre { font-family:var(--mono); font-size:13px; line-height:1.7; background:var(--surface); border:1px solid var(--line); padding:18px 20px; overflow-x:auto; margin:0 0 22px; color:var(--ink-2); }
pre b { color:var(--ink); font-weight:600; }
pre .c { color:var(--ink-3); }

.note { border-left:3px solid var(--signal); background:var(--signal-2); padding:18px 22px; margin:24px 0; font-size:16.5px; color:var(--ink-2); }
.note b { color:var(--ink); }
.note :last-child { margin-bottom:0; }
.callout { background:var(--accent-2); border:1px solid var(--line); padding:18px 22px; margin:24px 0; font-size:16px; color:var(--ink-2); }
.callout b { color:var(--ink); }
.callout :last-child { margin-bottom:0; }

.passos { counter-reset:passo; display:grid; gap:1px; background:var(--line); border:1px solid var(--line); margin-bottom:24px; }
.passo { background:var(--surface); padding:20px 22px; display:grid; grid-template-columns:40px 1fr; gap:18px; }
.passo::before { counter-increment:passo; content:counter(passo); font-family:var(--display); font-weight:800; font-size:26px; color:var(--accent); line-height:1; }
.passo h4 { margin:0 0 6px; font-family:var(--display); font-size:16px; color:var(--ink); font-weight:700; }
.passo p { margin:0; font-size:15.5px; color:var(--ink-2); }


/* tokens usados pelos diagramas SVG — sem eles o texto cai no serif do corpo
   e estoura as caixas, porque SVG não quebra linha sozinho */
.svg-label { font-family:var(--display); font-weight:600; font-size:13px; }
.svg-small { font-family:var(--mono); font-size:10.5px; letter-spacing:.04em; }
.svg-num   { font-family:var(--mono); font-size:11px; font-weight:500; }
.s-ink   { fill:var(--ink); }
.s-ink2  { fill:var(--ink-2); }
.s-ink3  { fill:var(--ink-3); }
.s-accent{ fill:var(--accent); }
.s-signal{ fill:var(--signal); }
.figure { margin:28px 0 24px; }
.figure .frame { border:1px solid var(--line); background:var(--surface); padding:26px 22px; overflow-x:auto; box-shadow:var(--shadow); }
.figure svg { display:block; width:100%; height:auto; min-width:560px; }
figcaption { font-family:var(--mono); font-size:11.5px; line-height:1.6; color:var(--ink-3); margin-top:12px; max-width:76ch; }
figcaption b { color:var(--ink-2); font-weight:600; }


/* ---------- testador de resposta no navegador ---------- */
.testador { border:1px solid var(--line); background:var(--surface); padding:22px; margin:0 0 24px; }
.testador-controles { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:14px; align-items:end; }
.campo-arquivo { display:flex; flex-direction:column; gap:5px; cursor:pointer; }
.campo-arquivo input[type=file] { position:absolute; width:1px; height:1px; opacity:0; }
.campo-arquivo .rotulo, .campo-janela .rotulo { font-family:var(--mono); font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-3); }
.campo-arquivo .rotulo em { font-style:normal; color:var(--accent); }
.campo-arquivo .nome { font-family:var(--mono); font-size:12.5px; color:var(--ink); border:1px dashed var(--line); padding:9px 11px; background:var(--surface-2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.campo-arquivo:hover .nome, .campo-arquivo input:focus-visible + .rotulo + .nome { border-color:var(--accent); color:var(--accent); }
.campo-janela { display:flex; flex-direction:column; gap:5px; font-family:var(--mono); font-size:12.5px; color:var(--ink-2); }
.campo-janela label { display:inline-flex; align-items:center; gap:6px; cursor:pointer; }
.testador .btn { align-self:end; }
.testador .btn:disabled { background:var(--surface-2); color:var(--ink-3); cursor:not-allowed; }
.testador-estado { font-family:var(--mono); font-size:12.5px; color:var(--ink-3); margin:18px 0 0; }
.testador-estado.erro { color:var(--alerta); }
.testador-estado code { font-size:12px; }

.sha { font-family:var(--mono); font-size:11px; color:var(--ink-3); }

/* ---------- gráficos do placar ----------
   Paleta validada com o validador da skill dataviz nos dois modos:
   claro  #00889E / #B85C00  ΔE 17.9 (protan) · 24.3 (visão normal)
   escuro #1E9DB4 / #D07E3A  dentro da banda L 0.48–0.67
   Toda barra traz o valor escrito ao lado e todo status vem com rótulo:
   a cor nunca é a única portadora de informação. */
:root {
  --serie-1:#00889E; --serie-2:#B85C00;
  --bom:#1F7A3D; --alerta:#B3480C;
  --trilho:#DFE5E2;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --serie-1:#1E9DB4; --serie-2:#D07E3A;
    --bom:#5CA36F; --alerta:#DE8B4A;
    --trilho:#22302C;
  }
}
:root[data-theme="dark"] {
  --serie-1:#1E9DB4; --serie-2:#D07E3A;
  --bom:#5CA36F; --alerta:#DE8B4A;
  --trilho:#22302C;
}

.sr { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }

.trilho { position:relative; height:16px; background:var(--trilho); margin:0 0 4px; }
.trilho.baixo { height:11px; margin-bottom:3px; }
.barra { height:100%; border-radius:0 3px 3px 0; transition:filter .12s; }
.barra.serie-1 { background:var(--serie-1); }
.barra.serie-2 { background:var(--serie-2); }
.trilho:hover .barra { filter:brightness(1.12); }
.marca-meta { position:absolute; top:-3px; bottom:-3px; left:var(--meta,95%); width:2px; background:var(--ink); opacity:.75; }

.legenda { display:flex; flex-wrap:wrap; gap:20px; font-family:var(--mono); font-size:12px; color:var(--ink-2); margin:0 0 22px; }
.legenda span { display:flex; align-items:center; gap:7px; }
.chip { display:inline-block; width:11px; height:11px; border-radius:2px; flex-shrink:0; }
.chip.serie-1 { background:var(--serie-1); }
.chip.serie-2 { background:var(--serie-2); }
.chip-meta { display:inline-block; width:2px; height:13px; background:var(--ink); opacity:.75; flex-shrink:0; }

.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(310px,1fr)); gap:1px; background:var(--line); border:1px solid var(--line); margin-bottom:24px; }
.kpi { background:var(--surface); padding:20px; }
.kpi-topo { display:flex; align-items:baseline; justify-content:space-between; gap:12px; margin-bottom:4px; }
.kpi h3 { font-family:var(--display); font-size:15.5px; margin:0; }
.kpi-nota { font-size:14px; color:var(--ink-3); margin:0 0 14px; }
.valores { font-family:var(--mono); font-size:12px; color:var(--ink-3); display:flex; align-items:center; gap:7px; margin:0 0 12px; }
.valores b { color:var(--ink); font-variant-numeric:tabular-nums; }
.valores .meta-txt { margin-left:auto; }

.pill { font-family:var(--mono); font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; padding:3px 8px; border:1px solid currentColor; white-space:nowrap; }
.pill.bom { color:var(--bom); }
.pill.alerta { color:var(--alerta); }
.bom-txt { color:var(--bom); }
.alerta-txt { color:var(--alerta); }

.tabela-corte td.cel-barra { width:42%; min-width:180px; padding-top:14px; }
.tabela-corte tbody tr:hover td { background:transparent; }
.tabela-corte th[scope="row"] { color:var(--ink); font-weight:600; white-space:nowrap; }

@media (max-width:720px) { .tabela-corte td.cel-barra { min-width:120px; } }


footer { padding:34px 0 60px; font-family:var(--mono); font-size:11.5px; line-height:1.8; color:var(--ink-3); border-top:1px solid var(--line); }
footer a { color:var(--accent); }

@media (max-width:720px) {
  body { font-size:16px; }
  .shell, .sitenav-in { padding:0 20px; }
  .masthead { padding:40px 0 32px; }
}
@media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; } }
"""


# ====================================================================
# Página de dados
# ====================================================================

def pagina_dados():
    arquivos = sorted(a for a in os.listdir(DADOS) if a.endswith((".csv", ".md", ".txt")))
    grupos = {
        "Pedidos": ["orders_history.csv", "orders_test_public.csv", "orders_test_private.csv",
                    "historical_deliveries.csv"],
        "Estoque e suprimento": ["inventory_snapshot.csv", "inventory_opening.csv",
                                 "inbound_plan.csv", "demand_plan.csv"],
        "Cadastros e rede": ["sku_master.csv", "customer_master.csv", "dc_master.csv",
                             "plant_master.csv", "lanes.csv", "transfer_lanes.csv",
                             "vehicles.csv", "holidays_calendar.csv"],
        "Formato de resposta": ["resposta_exemplo_promessa.csv",
                                 "resposta_exemplo_rebalanceamento.csv",
                                 "resposta_exemplo_previsao.csv"],
        "Documentação": ["data_dictionary.md", "CHECKSUMS.txt"],
    }
    zip_nome = f"desafio-supply-chain-v{P.VERSAO}.zip"
    zip_path = os.path.join(RAIZ, "desafio", "dados", zip_nome)

    linhas = [CABECA,
              "<title>Dados do Desafio</title>",
              '<link rel="preconnect" href="https://fonts.googleapis.com">',
              '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
              '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800'
              '&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">',
              '<link rel="stylesheet" href="./assets/site.css">',
              "</head>", "<body>", nav(1),
              '<header class="masthead"><div class="shell">',
              '<p class="kicker">Pacote de dados · versão ' + P.VERSAO + '</p>',
              "<h1>Os <em>arquivos</em> do desafio</h1>",
              f'<p class="standfirst">{len(arquivos)} arquivos, 4,6&nbsp;MB descompactados. CSV UTF-8, '
              'separador vírgula, decimal ponto. Sem cadastro, sem login, sem pedir acesso a ninguém.</p>',
              '<div class="baixar">']
    if os.path.exists(zip_path):
        linhas.append(f'<a class="btn" href="./dados/{zip_nome}" download>Baixar tudo: dados + ferramentas (.zip)</a>')
        linhas.append(f'<span class="meta">{kb(zip_path)} · sha256 {sha256(zip_path)[:16]}…</span>')
    linhas.append('<a class="btn sec" href="./dados/v' + P.VERSAO + '/data_dictionary.md">Dicionário de dados</a>')
    linhas.append("</div></div></header>")
    linhas.append('<main class="shell">')

    linhas.append('<section><p class="tag">Verifique antes de usar</p>'
                  "<h2>Confira a integridade</h2>"
                  '<div class="col"><p>Todo arquivo publicado tem checksum. Se algum não bater, '
                  "o download veio corrompido — baixe de novo antes de perder tempo depurando "
                  "o que não é problema seu.</p></div>"
                  "<pre><b>python desafio/ferramentas/conferir_dados.py</b>\n"
                  "<span class='c'># funciona em Windows, macOS e Linux</span>\n\n"
                  "<span class='c'># em macOS, Linux ou Git Bash, o equivalente nativo:</span>\n"
                  "cd desafio/dados/v" + P.VERSAO + " &amp;&amp; sha256sum -c CHECKSUMS.txt</pre>"
                  '<div class="note"><p><b>No Windows, use a primeira linha.</b> '
                  "<code>sha256sum</code> não existe no PowerShell nem no cmd — o verificador "
                  "é em Python justamente para não depender de qual terminal você abriu.</p></div>"
                  '<div class="callout"><p><b>Split temporal — não embaralhe.</b> O histórico vai '
                  "de " + P.HIST_INICIO.strftime("%d/%m/%Y") + " a " + P.HIST_FIM.strftime("%d/%m/%Y") +
                  ". A janela pública (leaderboard) vai de " + P.PUB_INICIO.strftime("%d/%m") + " a " +
                  P.PUB_FIM.strftime("%d/%m") + " e a privada (ranking final) de " +
                  P.PRI_INICIO.strftime("%d/%m") + " a " + P.PRI_FIM.strftime("%d/%m") + ".</p></div>"
                  "</section>")

    vistos = set()
    for titulo, nomes in grupos.items():
        presentes = [n for n in nomes if n in arquivos]
        if not presentes:
            continue
        vistos.update(presentes)
        linhas.append(f'<section><p class="tag">{titulo}</p><h2>{titulo}</h2>')
        linhas.append('<div class="scroll"><table><thead><tr>'
                      "<th>Arquivo</th><th>O que tem</th><th class='num'>Linhas</th>"
                      "<th class='num'>Tamanho</th><th class='num'>Baixar</th></tr></thead><tbody>")
        for nome in presentes:
            caminho = os.path.join(DADOS, nome)
            meta = TABELAS.get(nome, {})
            desc = meta.get("desc", "—")
            n = f"{linhas_csv(caminho):,}".replace(",", ".") if nome.endswith(".csv") else "—"
            href = f"./dados/v{P.VERSAO}/{nome}"
            linhas.append(f"<tr><td><code>{nome}</code><br><span class='sha'>sha256 "
                          f"{sha256(caminho)[:16]}…</span></td><td>{desc}</td>"
                          f"<td class='num'>{n}</td><td class='num'>{kb(caminho)}</td>"
                          f"<td class='num'><a href='{href}' download>baixar</a></td></tr>")
        linhas.append("</tbody></table></div></section>")

    restantes = [a for a in arquivos if a not in vistos]
    if restantes:
        linhas.append('<section><p class="tag">Outros</p><h2>Demais arquivos</h2>'
                      '<div class="scroll"><table><thead><tr><th>Arquivo</th>'
                      "<th class='num'>Tamanho</th><th class='num'>Baixar</th></tr></thead><tbody>")
        for nome in restantes:
            caminho = os.path.join(DADOS, nome)
            linhas.append(f"<tr><td><code>{nome}</code></td><td class='num'>{kb(caminho)}</td>"
                          f"<td class='num'><a href='./dados/v{P.VERSAO}/{nome}' download>baixar</a></td></tr>")
        linhas.append("</tbody></table></div></section>")

    linhas.append('<section><p class="tag">O que você devolve</p><h2>Formato de resposta</h2>'
                  '<div class="col"><p>Três arquivos. Só o primeiro é obrigatório — e ele precisa '
                  "cobrir <b>todas</b> as linhas da janela.</p></div>"
                  "<pre><b>resposta_promessa.csv</b>   <span class='c'>obrigatório</span>\n"
                  "order_line_id,dc_id,promised_date,qty_committed,shipment_group\n"
                  "OL-0125001,CD-SP,2026-09-04,1400,SHP-00012\n\n"
                  "<b>resposta_rebalanceamento.csv</b>  <span class='c'>opcional — é onde está o jogo</span>\n"
                  "transfer_id,origin,dest,sku,qty_pallets,ship_date\n"
                  "TRF-00001,CD-PE,CD-SP,P3,12,2026-09-15\n\n"
                  "<b>resposta_previsao.csv</b>   <span class='c'>opcional — vale 20 pontos</span>\n"
                  "dc_id,region,ship_date,transit_q50,transit_q90\n"
                  "CD-SP,SE,2026-09-01,2,4</pre>"
                  '<div class="note"><p><b>O <code>shipment_group</code> não é formalidade.</b> '
                  "Linhas com o mesmo grupo viajam juntas e dividem um frete — e o grupo só parte "
                  "quando a última delas tem estoque. É a sua alavanca de composição de carga.</p></div>"
                  "</section>")

    linhas.append("</main>")
    linhas.append(rodape())
    linhas.append("</body></html>")
    return "\n".join(linhas)


def rodape():
    return ('<footer class="shell">Desafio Supply Chain · pacote de dados v' + P.VERSAO +
            " · gerado em " + date.today().strftime("%d/%m/%Y") + "<br>"
            "Dados sintéticos determinísticos (seed " + str(P.SEED) + "). Nenhum dado real de "
            "cliente foi usado.<br>"
            'Páginas geradas por <code>desafio/gerador/gerar_site.py</code>.</footer>')


# ====================================================================
# Página inicial
# ====================================================================

def pagina_inicial():
    zip_nome = f"desafio-supply-chain-v{P.VERSAO}.zip"
    zip_path = os.path.join(RAIZ, "desafio", "dados", zip_nome)
    tamanho = kb(zip_path) if os.path.exists(zip_path) else "—"

    return f"""{CABECA}<title>Desafio Supply Chain</title>
<meta name="description" content="Desafio técnico de promessa de data e rebalanceamento de rede: 2 plantas, 4 CDs, 5 produtos e 4 tipos de cliente.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<link rel="stylesheet" href="./assets/site.css">
</head>
<body>
{nav(0)}
<header class="masthead">
  <div class="shell">
    <p class="kicker">Desafio técnico interno · Dados + Supply Chain</p>
    <h1>Chegou um pedido. De onde você <em>atende</em>?</h1>
    <p class="standfirst">
      Uma rede com 2 plantas, 4 centros de distribuição e 5 produtos atende quatro tipos de
      cliente com exigências diferentes. O estoque já está posicionado. Decida de qual CD sai
      cada linha, que data prometer e o que embarca junto.
    </p>
    <div class="baixar">
      <a class="btn" href="./dados/{zip_nome}" download>Baixar o pacote ({tamanho})</a>
      <a class="btn sec" href="./dados.html">Ver os arquivos um a um</a>
    </div>
    <div class="facts">
      <div class="fact"><b>2</b><span>Plantas</span></div>
      <div class="fact"><b>4</b><span>Centros de distribuição</span></div>
      <div class="fact"><b>5</b><span>Produtos</span></div>
      <div class="fact"><b>4</b><span>Tipos de cliente</span></div>
      <div class="fact"><b>40</b><span>Regras de negócio</span></div>
      <div class="fact"><b>25.079</b><span>Linhas de histórico</span></div>
    </div>
  </div>
</header>

<main class="shell">

  <section>
    <p class="tag">O problema</p>
    <h2>O plano já rodou. O pedido real não obedece.</h2>
    <div class="col">
      <p class="lead">
        A demanda foi planejada semanas atrás e o produto está posicionado na rede. O desafio
        começa exatamente onde o planejamento termina: no momento em que o pedido real entra
        e diverge do que foi previsto.
      </p>
      <p>
        Atender rápido custa frete. Atender barato custa prazo. E o cliente que representa 41%
        da receita tem multa contratual de 3% se o OTIF dele cair abaixo de 95%. Não existe
        decisão que ganhe em tudo — existe a decisão que você consegue defender com números.
      </p>
    </div>

    <div class="grid">
      <div class="cell"><span class="code">Sourcing</span><h4>Qual CD atende?</h4><p>Primário, secundário, transferência ou produção. A cascata tem custo e prazo crescentes.</p></div>
      <div class="cell"><span class="code">Promessa</span><h4>Que data prometer?</h4><p>Curta ganha o cliente e quebra a confiança. Longa entrega confiabilidade e perde a venda.</p></div>
      <div class="cell"><span class="code">Serviço</span><h4>Quem tem prioridade?</h4><p>Key Account tem multa. Mas há piso de fill rate por segmento — a cauda longa não pode ser sacrificada.</p></div>
      <div class="cell"><span class="code">Carga</span><h4>Embarca ou consolida?</h4><p>Embarque imediato cumpre o prazo. Veículo a 5% de ocupação destrói o custo unitário.</p></div>
      <div class="cell"><span class="code">Rebalanceamento</span><h4>O que se transfere?</h4><p>No corte, o CD-SP está em ruptura nos 5 produtos e o Sudeste é 45% da demanda.</p></div>
      <div class="cell"><span class="code">Predição</span><h4>Quanto a rota atrasa?</h4><p>9% de chance de atraso no Sudeste, 26% no Norte. Buffer fixo é caro onde não precisa.</p></div>
    </div>
  </section>


  <section>
    <p class="tag">Como funciona</p>
    <h2>Três partes, e só uma delas é treino</h2>
    <div class="col">
      <p class="lead">
        O desafio não se divide em “treinar” e “testar”. São três blocos de tempo, e confundir o
        papel de cada um é o erro estratégico mais caro que uma equipe pode cometer aqui.
      </p>
    </div>

    <figure class="figure">
      <div class="frame">
        <svg viewBox="0 0 920 332" role="img" aria-label="Linha do tempo do desafio: doze meses de histórico para treino, janela pública para feedback e janela privada para o ranking final">
          <text x="0" y="18" class="svg-small s-ink3">A LINHA DO TEMPO DO DESAFIO</text>

          <rect x="0" y="64" width="470" height="76" fill="var(--surface-2)" stroke="var(--line)" stroke-width="1.5"/>
          <text x="20" y="92" class="svg-label s-ink">HISTÓRICO</text>
          <text x="20" y="112" class="svg-small s-ink3">01/09/2025 a 28/08/2026 · 25.079 linhas</text>

          <rect x="490" y="64" width="185" height="76" fill="var(--accent-2)" stroke="var(--accent)" stroke-width="1.8"/>
          <text x="508" y="92" class="svg-label s-ink">JANELA PÚBLICA</text>
          <text x="508" y="112" class="svg-small s-accent">31/08 a 11/09</text>
          <text x="508" y="126" class="svg-small s-accent">919 linhas</text>

          <rect x="695" y="64" width="225" height="76" fill="var(--signal-2)" stroke="var(--signal)" stroke-width="1.8"/>
          <text x="713" y="92" class="svg-label s-ink">JANELA PRIVADA</text>
          <text x="713" y="112" class="svg-small s-signal">14/09 a 25/09 · 976 linhas</text>

          <line x1="478" y1="52" x2="478" y2="160" stroke="var(--ink)" stroke-width="1.5" stroke-dasharray="4 3"/>
          <text x="478" y="46" class="svg-small s-ink" text-anchor="middle">data de corte</text>

          <text x="0" y="176" class="svg-small s-ink3">O QUE VOCÊ FAZ EM CADA UMA</text>
          <g>
            <rect x="0" y="190" width="470" height="72" fill="none" stroke="var(--line)"/>
            <text x="20" y="214" class="svg-label s-accent">TREINA</text>
            <text x="20" y="233" class="svg-small s-ink2">aprende os padrões: atraso por rota, sazonalidade,</text>
            <text x="20" y="250" class="svg-small s-ink2">erro do plano de demanda</text>

            <rect x="490" y="190" width="185" height="72" fill="none" stroke="var(--accent)" stroke-width="1.5"/>
            <text x="508" y="214" class="svg-label s-accent">DECIDE</text>
            <text x="508" y="233" class="svg-small s-ink2">e vê o score</text>
            <text x="508" y="247" class="svg-small s-ink2">até 5× por dia</text>

            <rect x="695" y="190" width="225" height="72" fill="none" stroke="var(--signal)" stroke-width="1.5"/>
            <text x="713" y="214" class="svg-label s-signal">DECIDE</text>
            <text x="713" y="233" class="svg-small s-ink2">e a nota sai uma vez só,</text>
            <text x="713" y="247" class="svg-small s-ink2">no encerramento</text>
          </g>

          <text x="0" y="298" class="svg-small s-ink3">As duas janelas são conjuntos de TESTE. A pública dá feedback; a privada dá a nota.</text>
          <text x="0" y="316" class="svg-small s-signal">Só o histórico é material de treino.</text>
        </svg>
      </div>
      <figcaption>
        <b>As duas janelas não se sobrepõem</b> e nenhuma delas é material de treino. A pública
        existe para você calibrar o instinto com feedback rápido; a privada, para medir se o que
        você aprendeu vale fora do conjunto que já viu.
      </figcaption>
    </figure>

    <div class="scroll">
      <table>
        <thead><tr><th>Parte</th><th>Período</th><th class="num">Linhas</th><th>Papel</th></tr></thead>
        <tbody>
          <tr><td>Histórico</td><td>01/09/2025 a 28/08/2026</td><td class="num">25.079</td><td><b>Treino.</b> Aqui estão os padrões: atraso real por rota, sazonalidade, erro do plano de demanda</td></tr>
          <tr><td>Janela pública</td><td>31/08 a 11/09/2026</td><td class="num">919</td><td><b>Teste com feedback.</b> Você promete, envia e vê o score — até 5 vezes por dia</td></tr>
          <tr class="destaque"><td>Janela privada</td><td>14/09 a 25/09/2026</td><td class="num">976</td><td><b>Teste final.</b> Você promete, e a nota sai uma única vez, no encerramento</td></tr>
        </tbody>
      </table>
    </div>

    <h3>Por que duas janelas, e não uma</h3>
    <div class="col">
      <p>
        Com uma janela só e cinco tentativas por dia durante duas semanas, daria para achar a
        resposta por tentativa e erro: envia, olha o placar, ajusta, repete. Setenta tentativas
        encontram os parâmetros que funcionam <em>naquele</em> conjunto — sem entender nada do
        problema. Isso tem nome: <b>overfitting no leaderboard</b>.
      </p>
      <p>
        A janela privada fecha esse atalho. Quem ajustou parâmetro no olho perde ali; quem
        entendeu o problema, não.
      </p>
    </div>

    <div class="note">
      <p><b>Não confunda: a janela pública não é treino.</b> Ela é um conjunto de teste igual à
      privada — mesmos pedidos a promissar, mesmas regras, mesmos gates. A única diferença é
      quantas vezes você vê o resultado.</p>
      <p><b>E a privada não é uma carteira nova.</b> São os mesmos clientes, a mesma rede, os
      mesmos produtos — <b>zero clientes novos</b>, todos já aparecem no histórico. O que muda é
      o momento: o estoque já foi consumido pela janela pública e entra um choque de demanda de
      P5 no Sudeste. É um <em>hold-out temporal</em>, não um teste de generalização para clientes
      desconhecidos.</p>
      <p>A pergunta não é “seu modelo funciona com quem nunca viu?”. É <b>“sua decisão continua
      boa quando a rede aperta?”</b> — e a resposta do baseline é não: o OTIF cai de 93,5% para
      91,2% e a multa de Key Account sobe de R$ 95.562 para R$ 105.966.</p>
    </div>

    <h3>Isto não é um problema de machine learning</h3>
    <div class="col">
      <p>
        A trilha preditiva vale <b>20 dos 90 pontos automáticos</b>. Os outros 70 vêm de decisões:
        de qual CD atender, que data prometer, o que consolidar num embarque, o que transferir
        entre CDs.
      </p>
      <p>
        Dá para somar 70 pontos sem treinar modelo nenhum — e dá para treinar um forecast
        excelente e ainda assim ir mal. Foi exatamente o que aconteceu com o protótipo de exemplo:
        <b>tirou os 20 pontos preditivos completos e zerou os 45 de serviço</b>.
      </p>
      <p>
        É um problema de <b>decisão sob incerteza</b>, com um componente preditivo dentro. Quem
        tratar como ML puro otimiza justamente a parte que vale menos.
      </p>
    </div>

    <div class="callout">
      <p><b>Consequência prática: rode sempre as duas janelas.</b> Uma solução que vai bem só na
      pública é sinal de alerta, não de vitória.</p>
      <pre style="margin:12px 0 0">python desafio/ferramentas/baseline_atual.py --janela public
python desafio/ferramentas/baseline_atual.py --janela private</pre>
    </div>
  </section>

  <section>
    <p class="tag">Comece aqui</p>
    <h2>Primeiro score em 30 minutos</h2>
    <div class="col">
      <p>Você precisa de <b>Python 3.10+</b> e nada mais. Sem pandas, sem solver, sem instalar nada.</p>
    </div>

    <div class="passos">
      <div class="passo"><div><h4>Baixe e descompacte</h4><p>O pacote traz os dados <b>e as ferramentas</b> — baseline, avaliador e protótipo. Descompacte e rode <code>python desafio/ferramentas/conferir_dados.py</code> — funciona em qualquer sistema.</p></div></div>
      <div class="passo"><div><h4>Rode o baseline</h4><p><code>python desafio/ferramentas/baseline_atual.py --janela public</code> — é a política que a operação usa hoje.</p></div></div>
      <div class="passo"><div><h4>Avalie</h4><p><code>python desafio/ferramentas/avaliar.py --resposta desafio/respostas/baseline/public</code> e veja o placar de referência.</p></div></div>
      <div class="passo"><div><h4>Leia o protótipo de exemplo</h4><p><code>exemplo_prototipo.py</code> tem a receita dos 5 passos comentada linha a linha. Ele corta 21,6% do custo.</p></div></div>
      <div class="passo"><div><h4>Faça melhor</h4><p>Copie, mexa, avalie de novo. Até 5 respostas por dia.</p></div></div>
    </div>

    <h3>O que a política atual entrega hoje</h3>
    <div class="scroll">
      <table>
        <thead><tr><th>Métrica</th><th class="num">Janela pública</th><th class="num">Janela privada</th><th class="num">Meta</th></tr></thead>
        <tbody>
          <tr><td>Promise Reliability</td><td class="num">94,8%</td><td class="num">94,7%</td><td class="num">≥ 96%</td></tr>
          <tr><td>OTIF (vs. data do cliente)</td><td class="num">93,5%</td><td class="num">91,2%</td><td class="num">≥ 95%</td></tr>
          <tr class="destaque"><td>OTIF Key Account</td><td class="num">86,7%</td><td class="num">86,6%</td><td class="num">≥ 98%</td></tr>
          <tr><td>Fill Rate (valor)</td><td class="num">100,0%</td><td class="num">100,0%</td><td class="num">≥ 96%</td></tr>
          <tr class="destaque"><td>Ocupação média do veículo</td><td class="num">4,7%</td><td class="num">4,6%</td><td class="num">≥ 80%</td></tr>
          <tr><td>Custo logístico / receita</td><td class="num">6,3%</td><td class="num">5,4%</td><td class="num">≤ 8,5%</td></tr>
          <tr><td><b>Custo total</b></td><td class="num"><b>R$ 491.736</b></td><td class="num"><b>R$ 463.201</b></td><td class="num">—</td></tr>
        </tbody>
      </table>
    </div>
    <div class="callout">
      <p><b>Seu score local é uma estimativa, e isso é de propósito.</b> O trânsito realizado
      das janelas de teste fica lacrado com os organizadores — se estivesse no repositório,
      bastaria ler o arquivo para prometer datas perfeitas.</p>
      <p>Rodando localmente, o avaliador entra em <b>modo TREINO</b>: sorteia o trânsito da
      distribuição observada no histórico, com semente fixa. Roda sempre igual e é uma amostra
      plausível — mas espere alguns pontos de diferença para a nota oficial. Ele avisa na
      primeira linha em que modo rodou.</p>
    </div>

    <div class="note">
      <p><b>Duas linhas valem dinheiro imediato.</b> O OTIF de Key Account em 86,7% aciona
      R$ 95.562 de multa por janela, e a ocupação de 4,7% significa frete mínimo pago em quase
      todo embarque — sobre R$ 305.083 de frete de distribuição.</p>
    </div>
  </section>


  <section>
    <p class="tag">O ponto de partida</p>
    <h2>Comece copiando o protótipo, não do zero</h2>
    <div class="col">
      <p class="lead">
        <code>exemplo_prototipo.py</code> tem 409 linhas comentadas e faz o percurso inteiro:
        lê os dados, decide, grava a resposta no formato certo e passa nos gates. Copie e mexa —
        assim você começa otimizando, em vez de montando encanamento.
      </p>
    </div>

    <pre><span class="c"># 1. copie</span>
cp desafio/ferramentas/exemplo_prototipo.py minha_solucao.py

<span class="c"># 2. rode como está, para ver o ponto de partida</span>
python desafio/ferramentas/exemplo_prototipo.py --janela public
python desafio/ferramentas/avaliar.py --resposta desafio/respostas/exemplo/public

<span class="c"># 3. mexa no seu arquivo e avalie de novo</span>
python minha_solucao.py --janela public --saida minhas_respostas
python desafio/ferramentas/avaliar.py --resposta minhas_respostas/public</pre>

    <h3>Os cinco passos, e onde mexer em cada um</h3>
    <div class="scroll">
      <table>
        <thead><tr><th>Passo</th><th>Função</th><th>O que faz</th><th>Onde está a alavanca</th></tr></thead>
        <tbody>
          <tr>
            <td>1 · Aprender</td><td><code>quantis_de_transito</code></td>
            <td>Extrai do histórico a distribuição real de atraso por rota</td>
            <td>Trocar o quantil fixo por um modelo que use dia da semana, volume ou congestionamento do CD</td>
          </tr>
          <tr>
            <td>2 · ATP</td><td><code>class ATP</code></td>
            <td>Monta a linha do tempo de disponibilidade por CD × SKU</td>
            <td>Já está correto — <code>primeira_data</code> usa o mínimo do saldo à frente. Não simplifique isso</td>
          </tr>
          <tr class="destaque">
            <td>3 · Decidir</td><td><code>resolver</code></td>
            <td>Escolhe CD, data e embarque para cada linha</td>
            <td><b>É aqui que se ganha o desafio.</b> Decide linha a linha, na ordem de prioridade — um otimizador resolve o conjunto</td>
          </tr>
          <tr>
            <td>4 · Rebalancear</td><td><code>rebalancear</code></td>
            <td>Compara estoque com demanda prevista e transfere</td>
            <td>Não compara o custo da transferência contra a falta evitada. Faz por gatilho, não por conta</td>
          </tr>
          <tr>
            <td>5 · Prever</td><td><code>previsao</code></td>
            <td>Publica os quantis q50 e q90 por rota</td>
            <td>Vale 20 pontos e sai de graça do passo 1. Um modelo de verdade rende mais</td>
          </tr>
        </tbody>
      </table>
    </div>

    <h3>Três linhas que valem experimento imediato</h3>
    <div class="grid">
      <div class="cell">
        <span class="code">linha 289</span>
        <h4>O quantil da promessa</h4>
        <p><code>p = 0.97 if seg in ("KA","DIS") else 0.90</code><br>
        Quantil alto entrega confiabilidade e alonga o prazo. Baixo faz o contrário. Cada segmento
        tem SLA e multa diferentes — por que o corte seria o mesmo?</p>
      </div>
      <div class="cell">
        <span class="code">linha 208</span>
        <h4>O critério de escolha do CD</h4>
        <p>Entre os CDs que chegam na data pedida, ele pega <b>o mais barato</b>. Poderia pesar a
        confiabilidade da rota, o risco de multa do cliente ou o custo de esvaziar aquele CD para
        os pedidos seguintes.</p>
      </div>
      <div class="cell">
        <span class="code">linha 244</span>
        <h4>O tamanho do grupo de embarque</h4>
        <p><code>limite = 3 if seg in ("KA","DIS") else 8</code><br>
        Grupo maior divide mais o frete e acopla mais gente: uma linha sem estoque segura o veículo
        inteiro. O ponto de equilíbrio é empírico.</p>
      </div>
    </div>

    <h3>Onde ele chega — e onde para</h3>
    <div class="scroll">
      <table>
        <thead><tr><th>Dimensão</th><th class="num">Protótipo</th><th class="num">Teto</th><th>Leitura</th></tr></thead>
        <tbody>
          <tr><td>Qualidade preditiva</td><td class="num">20,00</td><td class="num">20</td><td>Completo — sai do histórico</td></tr>
          <tr><td>Eficiência de custo</td><td class="num">21,62</td><td class="num">25</td><td>Quase tudo, via consolidação de embarques</td></tr>
          <tr class="destaque"><td>Promise Reliability</td><td class="num">0,00</td><td class="num">25</td><td>Não supera o baseline</td></tr>
          <tr class="destaque"><td>OTIF</td><td class="num">0,00</td><td class="num">12</td><td>Não supera o baseline</td></tr>
          <tr class="destaque"><td>Fill Rate</td><td class="num">0,00</td><td class="num">8</td><td>Não supera o baseline</td></tr>
          <tr><td><b>Total automático</b></td><td class="num"><b>41,62</b></td><td class="num"><b>90</b></td><td><b>48,4 pontos na mesa</b></td></tr>
        </tbody>
      </table>
    </div>

    <div class="note">
      <p><b>Repare no que ele não faz — é deliberado.</b> Ele ganha onde a solução é mecânica
      (previsão sai do histórico, consolidação é aritmética) e <b>zera nos 45 pontos de serviço</b>,
      porque não bate o baseline em nenhum deles.</p>
      <p>Na prática: corta R$ 106 mil de custo e <b>paga a multa de Key Account inteira</b>,
      R$ 95.562 — a mesma que o baseline paga. A alavanca mais óbvia do desafio segue intocada.</p>
      <p>E metade da economia dele vem de <b>não ter feito transferência nenhuma</b> na janela
      pública. Não é otimização, é omissão que aparece como ganho. Quando ele efetivamente
      rebalanceia, na janela privada, o score cai de 41,6 para 31,3 — sinal de que rebalanceia
      mal, não de que rebalancear seja ruim.</p>
    </div>

    <h3>O que você não precisa reescrever</h3>
    <div class="col">
      <p>
        <code>comum.py</code> entrega pronto o que dá mais trabalho e menos vantagem competitiva:
        calendário com cutoff e feriados por região, cálculo de frete com ad valorem e GRIS,
        conversão para paletes, e a data mínima viável de cada linha.
      </p>
      <pre>dados.liberacao(linha, cd)            <span class="c"># aplica cutoff das 18h e calendário do CD</span>
dados.somar_dias_uteis(d, n, regiao)  <span class="c"># dias úteis da região, com feriados</span>
dados.data_minima_viavel(linha, cd)   <span class="c"># o piso do BR-406</span>
dados.estoque_abertura(janela)        <span class="c"># o ponto de partida certo do ATP</span>
frete_distribuicao(dados, cd, itens, regiao)</pre>
      <p>
        Somar dias corridos em vez de dias úteis é a armadilha número um do desafio. Use as
        funções e ela desaparece.
      </p>
    </div>
  </section>

  <section>
    <p class="tag">Avaliação</p>
    <h2>Como você é pontuado</h2>
    <div class="scroll">
      <table>
        <thead><tr><th>Dimensão</th><th class="num">Peso</th><th>Composição</th></tr></thead>
        <tbody>
          <tr><td>Nível de serviço</td><td class="num">45</td><td>Promise Reliability 25 · OTIF 12 · Fill Rate 8</td></tr>
          <tr><td>Eficiência de custo</td><td class="num">25</td><td>Custo total contra o baseline</td></tr>
          <tr><td>Qualidade preditiva</td><td class="num">20</td><td>Pinball loss do lead time (q50 e q90)</td></tr>
          <tr><td>Qualidade da entrega</td><td class="num">10</td><td>Júri humano: código, reprodutibilidade, defesa da abordagem</td></tr>
        </tbody>
      </table>
    </div>

    <div class="callout">
      <p><b>Promise Reliability e OTIF medem coisas diferentes.</b> A primeira compara com a data
      que <em>você</em> prometeu; a segunda, com a data que <em>o cliente</em> pediu. Empurrar as
      promessas para a frente melhora uma e não salva a outra — o atalho não existe.</p>
    </div>

    <h3>Gates que reprovam a resposta inteira</h3>
    <div class="scroll">
      <table>
        <thead><tr><th>Gate</th><th>Regra</th></tr></thead>
        <tbody>
          <tr><td>Cobertura</td><td>Toda linha da janela precisa de uma promessa</td></tr>
          <tr><td><code>BR-406</code></td><td>Data prometida não pode ser anterior ao lead time mínimo viável</td></tr>
          <tr><td><code>BR-102</code></td><td>Data prometida precisa cair em dia útil da região</td></tr>
          <tr><td><code>BR-501/502</code></td><td>KA e DIS não aceitam linha parcial: comprometa 0 ou tudo</td></tr>
          <tr><td><code>BR-506</code></td><td>Um embarque atende no máximo 8 pontos, em uma única região</td></tr>
          <tr><td><code>BR-704</code></td><td>Transferência não pode tirar estoque que a origem não tem</td></tr>
          <tr class="destaque"><td><code>BR-205</code></td><td>Nenhum segmento pode ficar com fill rate abaixo de 85%</td></tr>
        </tbody>
      </table>
    </div>
    <p class="col">
      O último existe para fechar a saída fácil: recusar os pedidos difíceis para inflar as
      métricas dos fáceis.
    </p>
  </section>

  <section>
    <p class="tag">Para onde ir</p>
    <h2>Os três documentos</h2>
    <div class="grid">
      <div class="cell">
        <span class="code">Se você nunca viu supply chain</span>
        <h4><a href="./conceitos.html">Supply Chain do Zero</a></h4>
        <p>ATP, CTP, abastecimento, lead time e frete explicados com exemplos numéricos deste
        mesmo cenário. Termina com a receita de 5 passos do protótipo. Vinte minutos.</p>
      </div>
      <div class="cell">
        <span class="code">O contrato do desafio</span>
        <h4><a href="./regras.html">Regras de Atendimento</a></h4>
        <p>As 40 regras de negócio numeradas, a topologia da rede, os custos, os KPIs e os
        cinco cenários que a equipe precisa saber defender.</p>
      </div>
      <div class="cell">
        <span class="code">O número a bater</span>
        <h4><a href="./placar.html">Placar do baseline</a></h4>
        <p>O resultado que a política atual entrega, KPI por KPI contra a meta, com a
        decomposição do custo e o diagnóstico de onde o OTIF se perde.</p>
      </div>
      <div class="cell">
        <span class="code">Os arquivos</span>
        <h4><a href="./dados.html">Dados do desafio</a></h4>
        <p>Os 21 arquivos com tamanho, número de linhas e checksum, mais o dicionário de dados
        coluna a coluna e o formato de resposta.</p>
      </div>
    </div>
  </section>

  <section>
    <p class="tag">Regras de participação</p>
    <h2>O combinado</h2>
    <div class="scroll">
      <table>
        <thead><tr><th>Item</th><th>Regra</th></tr></thead>
        <tbody>
          <tr><td>Equipes</td><td>Até 3 pessoas, com pelo menos dois perfis distintos (SCM, IA, otimização)</td></tr>
          <tr><td>Respostas</td><td>Até 5 por dia; cada equipe escolhe 2 para o ranking final</td></tr>
          <tr><td>Ranking final</td><td>100% na janela privada. A pública serve só para feedback</td></tr>
          <tr><td>Bibliotecas</td><td>Livres, desde que open source e declaradas no README da solução</td></tr>
          <tr><td>Uso de IA</td><td>Permitido e esperado. Declare o que foi gerado e por qual ferramenta</td></tr>
          <tr><td>Dados externos</td><td>Não permitidos — o cenário é sintético, não há fonte externa válida</td></tr>
          <tr><td>Erratas</td><td>Correção de dados gera nova versão do pacote e aviso nesta página</td></tr>
        </tbody>
      </table>
    </div>
  </section>

</main>
{rodape()}
</body>
</html>
"""


# ====================================================================
# Principal
# ====================================================================

def main():
    os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)
    destino_dados = os.path.join(SITE, "dados", "v" + P.VERSAO)
    if os.path.isdir(destino_dados):
        shutil.rmtree(destino_dados)
    shutil.copytree(DADOS, destino_dados)
    n_dados = len(os.listdir(destino_dados))

    zip_nome = f"desafio-supply-chain-v{P.VERSAO}.zip"
    zip_origem = os.path.join(RAIZ, "desafio", "dados", zip_nome)
    if os.path.exists(zip_origem):
        shutil.copy2(zip_origem, os.path.join(SITE, "dados", zip_nome))

    # o testador roda o MESMO avaliador dentro do navegador, via Pyodide:
    # estas fontes precisam estar publicadas para ele buscar
    destino_py = os.path.join(SITE, "assets", "py")
    os.makedirs(destino_py, exist_ok=True)
    for origem in (("ferramentas", "comum.py"), ("ferramentas", "avaliar.py"),
                   ("ferramentas", "baseline_atual.py"), ("gerador", "parametros.py")):
        shutil.copy2(os.path.join(RAIZ, "desafio", origem[0], origem[1]),
                     os.path.join(destino_py, origem[1]))

    with open(os.path.join(SITE, "assets", "site.css"), "w", encoding="utf-8") as f:
        f.write(CSS)
    with open(os.path.join(SITE, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")

    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(pagina_inicial())
    with open(os.path.join(SITE, "dados.html"), "w", encoding="utf-8") as f:
        f.write(pagina_dados())

    caminho = placar_html.gerar(RAIZ, CABECA, nav(4), rodape())
    if caminho:
        print(f"  placar.html        gerado a partir de dados/placar.json")
    else:
        print("  placar.html        pulado — docs/dados/placar.json ausente")

    for i, (origem, destino, titulo) in enumerate(FONTES_HTML):
        converter(os.path.join(FONTES, origem), os.path.join(SITE, destino), i + 2)
        print(f"  {destino:<18} ← {origem}  ({titulo})")

    print(f"\n  index.html         página inicial do desafio")
    print(f"  dados.html         {n_dados} arquivos listados com checksum")
    print(f"  dados/v{P.VERSAO}/     {n_dados} arquivos copiados")
    print(f"  assets/site.css    folha compartilhada")
    print(f"\nSite pronto em docs/. Para publicar:")
    print(f"  GitHub → Settings → Pages → Source: Deploy from a branch → main → /docs")


if __name__ == "__main__":
    main()
