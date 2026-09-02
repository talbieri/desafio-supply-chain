"""
Renderiza docs/placar.html a partir de docs/dados/placar.json.

As barras são HTML e CSS, não SVG: acompanham a largura da tela, aceitam hover
sem script e não têm como estourar a caixa — problema que texto em SVG tem por
não quebrar linha sozinho.

Paleta validada com o validador da skill dataviz, nos dois modos:
  claro   #00889E / #B85C00   ΔE 17.9 (protan) · 24.3 (visão normal)
  escuro  #1E9DB4 / #D07E3A   dentro da banda L 0.48–0.67
Toda barra traz o valor escrito ao lado e todo status vem com rótulo, então a
cor nunca é a única portadora de informação.
"""

import json
import os

JANELAS = [("public", "Janela pública", "serie-1"),
           ("private", "Janela privada", "serie-2")]


def _pct(v):
    return f"{v * 100:.1f}".replace(".", ",") + "%"


def _reais(v):
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def barra(largura_pct, serie, titulo):
    largura = max(0.6, min(100.0, largura_pct))
    return (f'<div class="barra {serie}" style="width:{largura:.1f}%">'
            f'<span class="sr">{titulo}</span></div>')


def bloco_kpis(dados):
    pub = {k["chave"]: k for k in dados["janelas"]["public"]["kpis"]}
    pri = {k["chave"]: k for k in dados["janelas"]["private"]["kpis"]}
    linhas = []
    for base in dados["janelas"]["public"]["kpis"]:
        c = base["chave"]
        a, b = pub[c], pri[c]
        meta = base["meta"]
        # escala: percentuais vão de 0 a 100; o custo logístico usa 0 a 15%
        teto = 0.15 if c == "custo_logistico_pct" else 1.0
        status = "bom" if a["atinge"] else "alerta"
        rot = "atinge" if a["atinge"] else "abaixo da meta"
        linhas.append(f'''
        <div class="kpi">
          <div class="kpi-topo">
            <h3>{base["rotulo"]}</h3>
            <span class="pill {status}">{rot}</span>
          </div>
          <p class="kpi-nota">{base["nota"]}</p>
          <div class="trilho" style="--meta:{meta / teto * 100:.1f}%">
            {barra(a["valor"] / teto * 100, "serie-1", "janela pública")}
            <div class="marca-meta" title="meta {_pct(meta)}"></div>
          </div>
          <div class="valores"><span class="chip serie-1"></span>pública
            <b>{_pct(a["valor"])}</b></div>
          <div class="trilho" style="--meta:{meta / teto * 100:.1f}%">
            {barra(b["valor"] / teto * 100, "serie-2", "janela privada")}
            <div class="marca-meta" title="meta {_pct(meta)}"></div>
          </div>
          <div class="valores"><span class="chip serie-2"></span>privada
            <b>{_pct(b["valor"])}</b>
            <span class="meta-txt">meta {_pct(meta)}</span></div>
        </div>''')
    return "".join(linhas)


def bloco_custo(dados):
    pub = {c["chave"]: c for c in dados["janelas"]["public"]["custo"]}
    pri = {c["chave"]: c for c in dados["janelas"]["private"]["custo"]}
    chaves = sorted(set(pub) | set(pri), key=lambda k: -max(pub.get(k, {}).get("valor", 0),
                                                            pri.get(k, {}).get("valor", 0)))
    teto = max([c["valor"] for c in list(pub.values()) + list(pri.values())] or [1])
    linhas = []
    for k in chaves:
        nome = (pub.get(k) or pri.get(k))["nome"]
        va = pub.get(k, {}).get("valor", 0.0)
        vb = pri.get(k, {}).get("valor", 0.0)
        linhas.append(f'''
        <tr>
          <th scope="row">{nome}</th>
          <td class="cel-barra">
            <div class="trilho baixo">{barra(va / teto * 100, "serie-1", nome)}</div>
            <div class="trilho baixo">{barra(vb / teto * 100, "serie-2", nome)}</div>
          </td>
          <td class="num">{_reais(va)}</td>
          <td class="num">{_reais(vb)}</td>
        </tr>''')
    return "".join(linhas)


def bloco_corte(dados, campo, titulo, legenda):
    pub = dados["janelas"]["public"][campo]
    linhas = []
    for item in pub:
        larg = item["otif"] * 100
        crit = "alerta" if item["otif"] < 0.95 else "bom"
        linhas.append(f'''
        <tr>
          <th scope="row">{item["nome"]}</th>
          <td class="cel-barra">
            <div class="trilho baixo" style="--meta:95%">
              {barra(larg, "serie-1", item["nome"])}
              <div class="marca-meta"></div>
            </div>
          </td>
          <td class="num"><b>{_pct(item["otif"])}</b></td>
          <td class="num">{item["atrasadas"]} de {item["linhas"]}</td>
          <td class="num {crit}-txt">{_reais(item["valor_atrasado"])}</td>
        </tr>''')
    return f'''
    <h3>{titulo}</h3>
    <p class="col">{legenda}</p>
    <div class="scroll">
      <table class="tabela-corte">
        <thead><tr><th>{titulo.split()[-1]}</th><th>OTIF na janela pública</th>
        <th class="num">OTIF</th><th class="num">Atrasadas</th>
        <th class="num">Valor atrasado</th></tr></thead>
        <tbody>{"".join(linhas)}</tbody>
      </table>
    </div>'''


def render(dados, cabeca, nav, rodape):
    pub = dados["janelas"]["public"]
    pri = dados["janelas"]["private"]
    falha_pub = sum(1 for k in pub["kpis"] if not k["atinge"])
    multa = next((c["valor"] for c in pub["custo"] if c["chave"] == "multa_ka"), 0)
    frete = next((c["valor"] for c in pub["custo"] if c["chave"] == "frete_distribuicao"), 0)

    return f"""{cabeca}<title>Placar do Baseline</title>
<meta name="description" content="O resultado que a política atual entrega e que as equipes precisam superar.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="./assets/site.css">
</head>
<body>
{nav}
<header class="masthead">
  <div class="shell">
    <p class="kicker">Placar · pacote v{dados["versao"]} · avaliação oficial</p>
    <h1>O resultado a ser <em>batido</em></h1>
    <p class="standfirst">
      Isto é o que a política atual da operação entrega hoje, medido pelo avaliador oficial
      contra o gabarito. Todo ponto que a sua equipe marca é ganho medido contra estes números.
    </p>
    <div class="facts">
      <div class="fact"><b>{_reais(pub["custo_total"])}</b><span>Custo · janela pública</span></div>
      <div class="fact"><b>{_reais(pri["custo_total"])}</b><span>Custo · janela privada</span></div>
      <div class="fact"><b>{falha_pub} de 8</b><span>KPIs abaixo da meta</span></div>
      <div class="fact"><b>{_reais(multa)}</b><span>Multa de Key Account</span></div>
    </div>
  </div>
</header>

<main class="shell">

  <section>
    <p class="tag">Leitura rápida</p>
    <h2>Onde estão os pontos</h2>
    <div class="col">
      <p class="lead">
        O baseline não é ruim em tudo — ele entrega 100% de fill rate e fica dentro do custo
        logístico alvo. Ele falha em três lugares específicos, e é lá que a disputa acontece.
      </p>
    </div>
    <div class="grid">
      <div class="cell">
        <span class="code">Alvo 1 · {_reais(multa)}</span>
        <h4>A multa de Key Account</h4>
        <p>O OTIF de KA está em {_pct(next(k["valor"] for k in pub["kpis"] if k["chave"] == "otif_ka"))}
        e a multa de 3% dispara abaixo de 95%. É o segundo maior item de custo, e nem o baseline
        nem o protótipo de exemplo encostam nele.</p>
      </div>
      <div class="cell">
        <span class="code">Alvo 2 · {_reais(frete)}</span>
        <h4>O frete de distribuição</h4>
        <p>Com {_pct(next(k["valor"] for k in pub["kpis"] if k["chave"] == "ocupacao_media_veiculo"))}
        de ocupação, a operação paga frete mínimo de R$ 180 em quase todo embarque. Consolidar o
        que já está disponível no mesmo dia corta ~17% sem atrasar ninguém.</p>
      </div>
      <div class="cell">
        <span class="code">Alvo 3 · prazo</span>
        <h4>O buffer de tamanho único</h4>
        <p>O baseline promete lead time + 2 dias para toda região. Sudeste atrasa 9% das vezes,
        Nordeste 18% até 4 dias. O buffer cobre um e não cobre o outro — e o OTIF mostra
        exatamente isso.</p>
      </div>
    </div>
  </section>

  <section>
    <p class="tag">Indicadores</p>
    <h2>Cada KPI contra a sua meta</h2>
    <div class="col">
      <p>A marca vertical em cada barra é a meta da rubrica. As duas janelas aparecem sempre
      juntas: uma solução que só vai bem na pública é sinal de alerta.</p>
    </div>
    <div class="legenda">
      <span><span class="chip serie-1"></span> Janela pública</span>
      <span><span class="chip serie-2"></span> Janela privada</span>
      <span><span class="chip-meta"></span> Meta da rubrica</span>
    </div>
    <div class="kpis">{bloco_kpis(dados)}</div>
  </section>

  <section>
    <p class="tag">Custo</p>
    <h2>Para onde o dinheiro vai</h2>
    <div class="col">
      <p>Barra superior é a janela pública, inferior a privada. As duas na mesma escala, para
      a comparação ser visual e não aritmética.</p>
    </div>
    <div class="scroll">
      <table class="tabela-corte">
        <thead><tr><th>Componente</th><th>Pública (cima) e privada (baixo)</th>
        <th class="num">Pública</th><th class="num">Privada</th></tr></thead>
        <tbody>{bloco_custo(dados)}</tbody>
      </table>
    </div>
    <div class="note">
      <p><b>Custo de falta zerado nas duas janelas.</b> O baseline nunca recusa um pedido: quando
      falta estoque, ele promete uma data mais tarde. Isso protege o fill rate e transfere o
      problema para o OTIF — que é onde ele perde.</p>
    </div>
  </section>

  <section>
    <p class="tag">Diagnóstico</p>
    <h2>Onde o OTIF se perde</h2>
    <div class="col">
      <p class="lead">
        As {sum(x["atrasadas"] for x in pub["por_regiao"])} linhas atrasadas da janela pública
        não estão espalhadas. Elas se concentram, e a concentração diz o que consertar.
      </p>
    </div>
    {bloco_corte(dados, "por_cd", "Por CD de origem",
                 "CD-PE e CD-GO servem as rotas mais longas e mais variáveis. É de lá que sai quase todo atraso.")}
    {bloco_corte(dados, "por_regiao", "Por região de entrega",
                 "Nordeste e Centro-Oeste têm a maior probabilidade de atraso — e recebem o mesmo buffer de 2 dias que o Sudeste.")}
    {bloco_corte(dados, "por_segmento", "Por segmento de cliente",
                 "Key Account tem poucas linhas atrasadas, mas elas carregam o maior valor — e disparam a multa contratual.")}
  </section>


  <section id="testar">
    <p class="tag">Teste a sua resposta</p>
    <h2>Solte o seu arquivo e veja a nota</h2>
    <div class="col">
      <p class="lead">
        O avaliador roda <b>dentro do seu navegador</b> — o mesmo <code>avaliar.py</code> que o
        robô do pull request usa, não uma reimplementação. Nada é enviado a lugar nenhum.
      </p>
    </div>

    <div class="testador">
      <div class="testador-controles">
        <label class="campo-arquivo">
          <input type="file" id="arq-promessa" accept=".csv">
          <span class="rotulo">resposta_promessa.csv</span>
          <span class="nome" id="nome-promessa">nenhum arquivo</span>
        </label>
        <label class="campo-arquivo">
          <input type="file" id="arq-rebal" accept=".csv">
          <span class="rotulo">resposta_rebalanceamento.csv <em>opcional</em></span>
          <span class="nome" id="nome-rebal">nenhum arquivo</span>
        </label>
        <label class="campo-arquivo">
          <input type="file" id="arq-prev" accept=".csv">
          <span class="rotulo">resposta_previsao.csv <em>opcional · 20 pontos</em></span>
          <span class="nome" id="nome-prev">nenhum arquivo</span>
        </label>
        <div class="campo-janela">
          <span class="rotulo">Janela</span>
          <label><input type="radio" name="janela" value="public" checked> pública</label>
          <label><input type="radio" name="janela" value="private"> privada</label>
        </div>
        <button class="btn" id="btn-avaliar" type="button" disabled>Avaliar</button>
      </div>
      <p class="testador-estado" id="estado" role="status">
        Escolha o <code>resposta_promessa.csv</code> para começar.
      </p>
      <div id="resultado"></div>

      <div id="envio" hidden>
        <h3>Gostou do número? Envie.</h3>
        <div class="col">
          <p>Escreva o nome da equipe e os comandos aparecem prontos, já com o nome no lugar
          certo. É o mesmo envio que entra no <a href="./ranking.html">ranking</a>.</p>
        </div>
        <div class="envio-linha">
          <label class="campo-equipe">
            <span class="rotulo">Nome da equipe</span>
            <input type="text" id="nome-equipe" placeholder="torre-de-controle"
                   autocomplete="off" spellcheck="false" maxlength="40">
          </label>
          <button class="btn sec" id="btn-copiar" type="button">Copiar os comandos</button>
          <button class="btn sec" id="btn-baixar" type="button">Baixar a pasta pronta</button>
        </div>
        <p class="envio-dica" id="envio-dica">Minúsculas e hífens. É como a equipe aparece no ranking.</p>
        <pre id="comandos"><span class="c"># escreva o nome da equipe acima</span></pre>
      </div>
    </div>

    <div class="note">
      <p><b>A nota daqui é do modo TREINO</b>, igual à do pull request. O trânsito realizado
      fica lacrado com os organizadores — se estivesse no navegador, bastaria abrir o DevTools
      para lê-lo e prometer datas perfeitas.</p>
      <p>Use esta página para calibrar rápido. Quando gostar do número,
      <b>abra o pull request</b> — é ele que registra o envio com data e autoria, e é o que
      vale para o ranking.</p>
    </div>

    <p class="col" style="font-family:var(--mono);font-size:12px;color:var(--ink-3)">
      Na primeira avaliação o navegador baixa o Python (~10 MB) e os dados do desafio
      (~4,5 MB). Leva de 15 a 40 segundos. Depois disso fica em cache e responde em segundos.
    </p>
  </section>

  <section>
    <p class="tag">Como reproduzir</p>
    <h2>Rode você mesmo</h2>
    <pre><span class="c"># gera a resposta do baseline nas duas janelas</span>
python desafio/ferramentas/baseline_atual.py --janela public
python desafio/ferramentas/baseline_atual.py --janela private

<span class="c"># avalia</span>
python desafio/ferramentas/avaliar.py --resposta desafio/respostas/baseline/public
python desafio/ferramentas/avaliar.py --resposta desafio/respostas/baseline/private --janela private</pre>
    <div class="callout">
      <p><b>Os números desta página são do modo OFICIAL</b>, calculado contra o gabarito lacrado.
      Na sua máquina o avaliador roda em modo TREINO e sorteia o trânsito da distribuição
      histórica — espere alguns pontos de diferença, para cima ou para baixo.</p>
    </div>
  </section>

</main>
{rodape}
<script src="./assets/testador.js"></script>
</body>
</html>
"""


def gerar(raiz, cabeca, nav, rodape):
    caminho = os.path.join(raiz, "docs", "dados", "placar.json")
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    html = render(dados, cabeca, nav, rodape)
    destino = os.path.join(raiz, "docs", "placar.html")
    with open(destino, "w", encoding="utf-8") as f:
        f.write(html)
    return destino
