/*
 * Avalia a resposta do participante dentro do navegador, com Pyodide.
 *
 * Roda o MESMO avaliar.py que o robô do pull request executa. Reimplementar o
 * avaliador em JavaScript daria duas versões que divergem — e uma nota que
 * discorda do CI é pior do que nota nenhuma.
 *
 * O gabarito não vem para cá: ele revelaria os tempos de trânsito reais e o
 * desafio acabaria. Sem ele, o avaliador entra em modo TREINO sozinho.
 */

(function () {
  'use strict';

  var PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/';
  var DADOS = './dados/v1.0.0/';

  // Tudo que Dados() carrega, mais o histórico que o oráculo de treino usa
  var ARQUIVOS = [
    'sku_master.csv', 'customer_master.csv', 'dc_master.csv', 'plant_master.csv',
    'lanes.csv', 'transfer_lanes.csv', 'vehicles.csv', 'holidays_calendar.csv',
    'inbound_plan.csv', 'demand_plan.csv', 'inventory_snapshot.csv',
    'inventory_opening.csv', 'orders_test_public.csv', 'orders_test_private.csv',
    'orders_history.csv', 'historical_deliveries.csv'
  ];
  var FONTES = [
    ['./assets/py/parametros.py', '/desafio/gerador/parametros.py'],
    ['./assets/py/comum.py', '/desafio/ferramentas/comum.py'],
    ['./assets/py/avaliar.py', '/desafio/ferramentas/avaliar.py'],
    ['./assets/py/baseline_atual.py', '/desafio/ferramentas/baseline_atual.py'],
    ['./assets/avaliador_navegador.py', '/desafio/ferramentas/avaliador_navegador.py']
  ];

  var pyodide = null, carregando = null;
  var el = function (id) { return document.getElementById(id); };

  function estado(txt, erro) {
    var p = el('estado');
    if (!p) return;
    p.innerHTML = txt;
    p.className = 'testador-estado' + (erro ? ' erro' : '');
  }

  function pct(v) { return (v * 100).toFixed(1).replace('.', ',') + '%'; }
  function reais(v) {
    return 'R$ ' + Math.round(v).toLocaleString('pt-BR');
  }

  async function iniciar() {
    if (pyodide) return pyodide;
    if (carregando) return carregando;
    carregando = (async function () {
      estado('Baixando o Python… (só na primeira vez)');
      await new Promise(function (ok, falha) {
        var s = document.createElement('script');
        s.src = PYODIDE + 'pyodide.js';
        s.onload = ok;
        s.onerror = function () { falha(new Error('não consegui baixar o Pyodide')); };
        document.head.appendChild(s);
      });
      var py = await loadPyodide({ indexURL: PYODIDE });

      estado('Baixando os dados do desafio…');
      py.FS.mkdirTree('/desafio/dados/v1.0.0');
      py.FS.mkdirTree('/desafio/ferramentas');
      py.FS.mkdirTree('/desafio/gerador');
      py.FS.mkdirTree('/entrada');

      var baixados = 0;
      await Promise.all(ARQUIVOS.map(async function (nome) {
        var r = await fetch(DADOS + nome);
        if (!r.ok) throw new Error('faltou ' + nome);
        py.FS.writeFile('/desafio/dados/v1.0.0/' + nome, new Uint8Array(await r.arrayBuffer()));
        baixados++;
        estado('Baixando os dados do desafio… ' + baixados + ' de ' + ARQUIVOS.length);
      }));

      await Promise.all(FONTES.map(async function (par) {
        var r = await fetch(par[0]);
        if (!r.ok) throw new Error('faltou ' + par[0]);
        py.FS.writeFile(par[1], await r.text());
      }));

      estado('Preparando o avaliador…');
      py.runPython(
        'import sys\n' +
        'sys.path.insert(0, "/desafio/ferramentas")\n' +
        'sys.path.insert(0, "/desafio/gerador")\n' +
        'import avaliador_navegador as motor\n' +
        'motor.preparar()\n');
      pyodide = py;
      return py;
    })();
    return carregando;
  }

  function barra(largura, serie) {
    var w = Math.max(0.6, Math.min(100, largura));
    return '<div class="trilho baixo"><div class="barra ' + serie +
           '" style="width:' + w.toFixed(1) + '%"></div></div>';
  }

  function linha(rot, valor, meta, base, inverso) {
    var ok = inverso ? valor <= meta : valor >= meta;
    var melhor = inverso ? valor < base : valor > base;
    var teto = inverso ? 0.15 : 1;
    return '<tr><th scope="row">' + rot + '</th>' +
      '<td class="cel-barra">' + barra(valor / teto * 100, 'serie-1') +
      barra(base / teto * 100, 'serie-2') + '</td>' +
      '<td class="num"><b>' + pct(valor) + '</b></td>' +
      '<td class="num">' + pct(base) + '</td>' +
      '<td class="num">' + pct(meta) + '</td>' +
      '<td class="num">' + (ok ? '<span class="pill bom">atinge</span>'
        : '<span class="pill alerta">abaixo</span>') +
      (melhor ? ' <span class="bom-txt">↑</span>' : '') + '</td></tr>';
  }

  function render(d) {
    var alvo = el('resultado');
    if (!d.valida) {
      alvo.innerHTML = '<div class="note"><p><b>Resposta reprovada.</b> O avaliador não pontua ' +
        'uma resposta que falha nos gates — igual ao ranking final.</p><pre>' +
        d.erros.map(function (e) { return e.replace(/</g, '&lt;'); }).join('\n') +
        (d.total_erros > d.erros.length
          ? '\n… e mais ' + (d.total_erros - d.erros.length) + ' erros' : '') +
        '</pre></div>';
      return;
    }
    var m = d.metricas, b = d.baseline, sc = d.score;
    var teto = { promise_reliability: 25, otif: 12, fill_rate: 8, custo: 25, preditiva: 20 };
    var comp = Object.keys(sc.componentes).map(function (k) {
      return '<tr><th scope="row">' + k + '</th>' +
        '<td class="cel-barra">' + barra(sc.componentes[k] / teto[k] * 100, 'serie-1') + '</td>' +
        '<td class="num"><b>' + sc.componentes[k].toFixed(2) + '</b></td>' +
        '<td class="num">' + teto[k] + '</td></tr>';
    }).join('');

    alvo.innerHTML =
      '<div class="facts" style="margin:26px 0 22px">' +
        '<div class="fact"><b>' + sc.total.toFixed(2) + '</b><span>Score de 90 pontos</span></div>' +
        '<div class="fact"><b>' + reais(m.custo_total) + '</b><span>Custo total</span></div>' +
        '<div class="fact"><b>' + pct(m.otif) + '</b><span>OTIF</span></div>' +
        '<div class="fact"><b>' + pct(m.otif_ka) + '</b><span>OTIF Key Account</span></div>' +
      '</div>' +
      '<div class="legenda">' +
        '<span><span class="chip serie-1"></span> Sua resposta</span>' +
        '<span><span class="chip serie-2"></span> Baseline</span>' +
      '</div>' +
      '<div class="scroll"><table class="tabela-corte"><thead><tr><th>Métrica</th>' +
      '<th>Você (cima) e baseline (baixo)</th><th class="num">Você</th>' +
      '<th class="num">Baseline</th><th class="num">Meta</th><th class="num"></th></tr></thead><tbody>' +
      linha('OTIF', m.otif, 0.95, b.otif) +
      linha('OTIF Key Account', m.otif_ka, 0.98, b.otif_ka) +
      linha('Promise Reliability', m.promise_reliability, 0.96, b.promise_reliability) +
      linha('Fill Rate (valor)', m.fill_rate_valor, 0.96, b.fill_rate_valor) +
      linha('Ocupação do veículo', m.ocupacao_media_veiculo, 0.80, b.ocupacao_media_veiculo) +
      linha('Custo logístico / receita', m.custo_logistico_pct, 0.085,
            b.custo_total ? m.custo_logistico_pct : 0.063, true) +
      '</tbody></table></div>' +
      '<h3>Score por dimensão</h3>' +
      '<div class="scroll"><table class="tabela-corte"><thead><tr><th>Dimensão</th>' +
      '<th>Aproveitamento</th><th class="num">Pontos</th><th class="num">Teto</th>' +
      '</tr></thead><tbody>' + comp + '</tbody></table></div>' +
      '<p class="col" style="font-family:var(--mono);font-size:12px;color:var(--ink-3)">' +
      'Custo do baseline nesta janela: ' + reais(b.custo_total) + '. ' +
      'Diferença: <b>' + reais(b.custo_total - m.custo_total) + '</b>.</p>';
  }

  async function avaliar() {
    var arq = el('arq-promessa').files[0];
    if (!arq) { estado('Escolha o <code>resposta_promessa.csv</code> primeiro.', true); return; }
    var botao = el('btn-avaliar');
    botao.disabled = true;
    el('resultado').innerHTML = '';
    try {
      var py = await iniciar();
      estado('Avaliando…');

      py.FS.writeFile('/entrada/resposta_promessa.csv', await arq.text());
      for (var par of [['arq-rebal', 'resposta_rebalanceamento.csv'],
                       ['arq-prev', 'resposta_previsao.csv']]) {
        var caminho = '/entrada/' + par[1];
        var f = el(par[0]).files[0];
        try { py.FS.unlink(caminho); } catch (e) { /* não existia */ }
        if (f) py.FS.writeFile(caminho, await f.text());
      }

      var janela = document.querySelector('input[name="janela"]:checked').value;
      py.globals.set('_janela', janela);
      var bruto = py.runPython('motor.avaliar_entrada(_janela)');
      var dados = JSON.parse(bruto);
      render(dados);
      estado(dados.valida
        ? 'Pronto. Esta é a nota do <b>modo treino</b> — a oficial sai no encerramento.'
        : 'A resposta não passou nos gates. Os motivos estão abaixo.', !dados.valida);
    } catch (e) {
      estado('Não consegui avaliar: ' + (e && e.message ? e.message : e), true);
    } finally {
      botao.disabled = false;
    }
  }

  function ligar() {
    var promessa = el('arq-promessa');
    if (!promessa) return;
    [['arq-promessa', 'nome-promessa'], ['arq-rebal', 'nome-rebal'],
     ['arq-prev', 'nome-prev']].forEach(function (par) {
      el(par[0]).addEventListener('change', function () {
        var f = this.files[0];
        el(par[1]).textContent = f ? f.name : 'nenhum arquivo';
        if (par[0] === 'arq-promessa') {
          el('btn-avaliar').disabled = !f;
          if (f) estado('Pronto para avaliar <code>' + f.name + '</code>.');
        }
      });
    });
    el('btn-avaliar').addEventListener('click', avaliar);
  }

  document.addEventListener('DOMContentLoaded', ligar);
})();
