# equipe-2rm

**Score local (modo TREINO):** 66,74/90 pública · 58,19/90 privada — bem acima do
baseline (0) e do protótipo oficial (41,73 / 29,65).

## Abordagem, em 3 frases

Reaproveitamos os Passos 1 (quantis de trânsito), 2 (ATP) e 5 (previsão) do
protótipo oficial sem alteração. No Passo 3 (sourcing), calibramos o quantil de
buffer de promessa por segmento contra a fórmula real da rubrica (que pontua
contra o baseline, não contra a meta absoluta), adicionamos atendimento parcial
para VAR/ECM e implementamos CTP (recebimentos não confirmados, com margem de
segurança de 6 dias — o pior caso documentado em `data_dictionary.md`) como
último recurso antes do backorder. Testamos rebalanceamento entre CDs (Passo 4)
e o **descartamos**: media com o avaliador antes de decidir, e ele piorava o
score nas duas janelas — a evidência está na documentação abaixo.

## Código

`solucao.py` nesta pasta (roda de qualquer lugar dentro do repositório:
`python respostas/equipe-2rm/solucao.py --janela public --saida respostas/equipe-2rm`).

Metodologia completa, com cada decisão testada e seus números — incluindo o que
não funcionou e por quê — e um painel visual com os mesmos dados:

- Metodologia: https://github.com/rogeriooctaviano-eng/desafio-supply-chain/blob/resposta/equipe-2rm/respostas/equipe-2rm/METODOLOGIA.md
- Painel: https://claude.ai/code/artifact/38c42d15-ca84-461e-b549-82cf3b00cecb

## Bibliotecas

Nenhuma dependência externa — só a biblioteca padrão do Python 3.10+.

## Uso de IA

Gerado com assistência do **Claude Code** (Anthropic, modelo Claude Sonnet 5):
implementação, testes contra `avaliar.py`/`avaliar_pr.py` e esta documentação,
sob orientação e revisão de Rogerio Octaviano.
