"""
Renderiza docs/ranking.html a partir de docs/dados/ranking.json.

O leaderboard público sai em modo TREINO: é o robô que o atualiza a cada envio
aprovado, e o robô não tem o gabarito. A nota que vale é a oficial, calculada no
encerramento — a página diz isso em toda visita, sem letra miúda.

Mesmas barras em HTML e CSS do placar, mesma paleta validada.
"""

import json
import os


def _pct(v):
    return f"{v * 100:.1f}".replace(".", ",") + "%"


def _reais(v):
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def barra(largura, serie="serie-1"):
    w = max(0.6, min(100.0, largura))
    return f'<div class="trilho baixo"><div class="barra {serie}" style="width:{w:.1f}%"></div></div>'


def linhas_tabela(equipes, teto):
    saida = []
    for x in equipes:
        pri, pub = x.get("privada"), x.get("publica")
        nome = x["equipe"]
        if not pri or not pri.get("valida"):
            motivo = (pri or {}).get("motivo") or "sem resposta na janela privada"
            saida.append(f'''
        <tr>
          <td class="num pos">—</td>
          <th scope="row">{nome}</th>
          <td colspan="4"><span class="pill alerta">reprovada</span>
            <span class="motivo">{motivo[:120]}</span></td>
        </tr>''')
            continue
        sp = f"{pub['score']:.2f}" if pub and pub.get("valida") else "—"
        # quem vai muito melhor na pública que na privada otimizou o leaderboard
        suspeita = (pub and pub.get("valida")
                    and pub["score"] - pri["score"] > 8)
        marca = ('<span class="pill alerta" title="score bem maior na janela pública">'
                 'só na pública</span>') if suspeita else ""
        saida.append(f'''
        <tr>
          <td class="num pos">{x["posicao"]}º</td>
          <th scope="row">{nome}</th>
          <td class="cel-barra">{barra(pri["score"] / teto * 100)}</td>
          <td class="num destaque-num">{pri["score"]:.2f}</td>
          <td class="num">{_pct(pri["otif"])}</td>
          <td class="num">{_reais(pri["custo_total"])}</td>
          <td class="num">{sp} {marca}</td>
        </tr>''')
    return "".join(saida)


def render(dados, cabeca, nav, rodape):
    eqs = dados.get("equipes", [])
    validas = [e for e in eqs if e.get("privada") and e["privada"].get("valida")]
    teto = max([e["privada"]["score"] for e in validas] or [90]) or 90
    melhor = f"{validas[0]['privada']['score']:.2f}" if validas else "—"
    treino = dados.get("modo") != "oficial"

    tabela_ou_vazio = ("""
    <div class="callout">
      <p><b>Nenhuma equipe enviou ainda.</b> A primeira resposta aprovada aparece aqui
      automaticamente — e quem chegar primeiro fica em primeiro até alguém tirar.</p>
    </div>""" if not eqs else """
    <div class="scroll">
      <table class="tabela-corte">
        <thead><tr>
          <th class="num">#</th><th>Equipe</th><th>Score na privada</th>
          <th class="num">Score</th><th class="num">OTIF</th>
          <th class="num">Custo</th><th class="num">Pública</th>
        </tr></thead>
        <tbody>""" + linhas_tabela(eqs, teto) + """</tbody>
      </table>
    </div>""")

    aviso = ('''
    <div class="note">
      <p><b>Este leaderboard é do modo TREINO.</b> O trânsito realizado das janelas de teste
      fica lacrado com os organizadores — o robô que atualiza esta página não o tem, e sorteia
      o trânsito da distribuição histórica com semente fixa.</p>
      <p>Serve para acompanhar e comparar. <b>A nota que vale sai no encerramento</b>, calculada
      contra o gabarito. Espere alguns pontos de diferença — e não otimize contra este número.</p>
    </div>''' if treino else '''
    <div class="callout">
      <p><b>Ranking OFICIAL</b>, calculado contra o gabarito. É este que vale.</p>
    </div>''')

    return f"""{cabeca}<title>Ranking das Equipes</title>
<meta name="description" content="Como as equipes estão no desafio, atualizado a cada envio.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="./assets/site.css">
</head>
<body>
{nav}
<header class="masthead">
  <div class="shell">
    <p class="kicker">Ranking · modo {'treino' if treino else 'oficial'} ·
      atualizado em {dados.get("gerado_em", "")[:16].replace("T", " ")}</p>
    <h1>Como as equipes <em>estão</em></h1>
    <p class="standfirst">
      Atualiza sozinho a cada envio aprovado. A ordem é pela janela privada — a mesma
      que decide o resultado final.
    </p>
    <div class="facts">
      <div class="fact"><b>{len(validas)}</b><span>Equipes na disputa</span></div>
      <div class="fact"><b>{melhor}</b><span>Melhor score</span></div>
      <div class="fact"><b>{len(eqs) - len(validas)}</b><span>Respostas reprovadas</span></div>
      <div class="fact"><b>90</b><span>Pontos automáticos</span></div>
    </div>
  </div>
</header>

<main class="shell">

  <section>
    <p class="tag">Classificação</p>
    <h2>Pela janela privada</h2>
    <div class="col">
      <p>A coluna <b>pública</b> fica ao lado de propósito: quem pontua muito mais nela do que
      na privada ajustou parâmetro no leaderboard em vez de resolver o problema.</p>
    </div>
    {tabela_ou_vazio}
    {aviso}
  </section>

  <section>
    <p class="tag">Como entrar</p>
    <h2>Enviar é abrir um pull request</h2>
    <div class="col">
      <p>Coloque a sua resposta em <code>respostas/&lt;sua-equipe&gt;/</code>, com as pastas
      <code>public/</code> e <code>private/</code>, e abra o pull request. O robô avalia,
      comenta a nota no próprio PR, e quando o envio é aprovado esta página se atualiza sozinha.</p>
    </div>
    <pre>git checkout -b resposta/minha-equipe
python minha_solucao.py --janela public  --saida respostas/minha-equipe
python minha_solucao.py --janela private --saida respostas/minha-equipe
git add respostas/minha-equipe &amp;&amp; git commit -m "resposta: minha-equipe"
gh pr create --title "Resposta · minha-equipe"</pre>
    <div class="callout">
      <p>Quer conferir a nota antes de enviar? <a href="./placar.html#testar">Solte o arquivo
      na página do placar</a> — o avaliador roda no seu navegador e devolve o mesmo número.</p>
    </div>
  </section>

</main>
{rodape}
</body>
</html>
"""


def gerar(raiz, cabeca, nav, rodape):
    caminho = os.path.join(raiz, "docs", "dados", "ranking.json")
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    destino = os.path.join(raiz, "docs", "ranking.html")
    with open(destino, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(dados, cabeca, nav, rodape))
    return destino
