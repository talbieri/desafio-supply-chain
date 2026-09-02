# Envio das respostas

Cada equipe envia sua resposta abrindo um **pull request** com uma pasta aqui. O robô avalia
sozinho e comenta a nota no próprio PR, em cerca de dois minutos.

---

## A estrutura

```
respostas/
└── nome-da-sua-equipe/
    ├── public/
    │   ├── resposta_promessa.csv          obrigatório
    │   ├── resposta_rebalanceamento.csv   opcional
    │   └── resposta_previsao.csv          opcional, vale 20 pontos
    └── private/
        └── ... os mesmos três arquivos
```

Nome da pasta em minúsculas, com hífens: `torre-de-controle`, `otif-ou-nada`. É como sua
equipe vai aparecer no placar.

---

## O passo a passo

```bash
# 1. crie sua branch
git checkout -b resposta/nome-da-sua-equipe

# 2. gere sua resposta direto na pasta certa
python minha_solucao.py --janela public  --saida respostas/nome-da-sua-equipe
python minha_solucao.py --janela private --saida respostas/nome-da-sua-equipe

# 3. confira a nota antes de enviar — é o mesmo cálculo que o robô faz
python desafio/ferramentas/avaliar_pr.py --equipe nome-da-sua-equipe

# 4. envie
git add respostas/nome-da-sua-equipe
git commit -m "resposta: nome-da-sua-equipe"
git push -u origin resposta/nome-da-sua-equipe
gh pr create --title "Resposta · nome-da-sua-equipe" --body "Envio da equipe."
```

O comentário com a nota é **atualizado**, não empilhado: a cada novo commit no mesmo PR, o
robô reescreve o mesmo comentário. O histórico dos seus envios fica nos commits.

---

## A nota que volta

Para cada janela, uma tabela com as métricas contra as metas, o custo total e o score por
dimensão. Se a resposta reprovar em algum gate, o comentário diz **qual** gate e a execução
falha — igual ao ranking final, que não pontua resposta inválida.

> **A nota do PR é do modo TREINO.** O trânsito realizado fica lacrado com os organizadores;
> aqui ele é sorteado da distribuição histórica com semente fixa. Roda sempre igual e serve
> para comparar duas versões da sua solução, mas espere alguns pontos de diferença para a nota
> oficial, calculada no encerramento.
>
> Os **gates são os mesmos** nos dois modos. Se reprovou aqui, reprova lá.

---

## Regras

| Item | Regra |
|------|-------|
| Envios | Até 5 por dia por equipe |
| Ranking final | Cada equipe escolhe 2 envios para valer na janela privada |
| Prazo | O último commit antes do encerramento é o que conta |
| Conflitos | Cada equipe mexe só na própria pasta — não deve haver conflito entre PRs |

---

## Antes de abrir o PR

- [ ] A pasta tem `public/` **e** `private/` — uma solução que só vai bem na pública é sinal de alerta
- [ ] `avaliar_pr.py --equipe <sua-equipe>` roda limpo na sua máquina
- [ ] O código da solução está no PR, ou o link para ele está na descrição (vale 10 pontos de júri)
- [ ] Você mexeu só na sua pasta

---

## Para os organizadores

O robô do pull request devolve a nota em **modo treino** — o gabarito não está no
repositório. A nota que vale sai na máquina de quem tem o gabarito:

```bash
# ranking consolidado de todas as equipes, em modo oficial
python desafio/gerador/gerar_ranking.py
```

```
#   equipe                   score     OTIF  OTIF KA         custo    pública
------------------------------------------------------------------------------
1º  torre-de-controle        58.40    94.1%    96.2%    R$ 331.204       61.2
2º  otif-ou-nada             47.15    92.8%    88.0%    R$ 358.911       44.9
—   equipe-x              REPROVADA   [BR-205] fill rate do segmento ECM = 71.2%
```

O ranking sai pela **janela privada**. A coluna `pública` fica ao lado de
propósito: quem vai muito melhor na pública do que na privada otimizou o
leaderboard em vez de resolver o problema.

Desempate, na ordem da rubrica: maior Promise Reliability, menor custo total,
envio mais antigo.

Para gravar o resultado em `docs/dados/ranking.json` e publicá-lo no site:

```bash
python desafio/gerador/gerar_ranking.py --publicar
python desafio/gerador/gerar_site.py
```
