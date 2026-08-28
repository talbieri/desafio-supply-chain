# Desafio Supply Chain — Promessa de Data e Rebalanceamento de Rede

Desafio técnico interno para as equipes de **Dados** e **Supply Chain**: uma rede com 2 plantas,
4 centros de distribuição e 5 produtos atende quatro tipos de cliente com exigências diferentes.
O estoque já está posicionado. Decida de qual CD sai cada linha de pedido, que data prometer ao
cliente e o que embarca junto.

---

## Publicar o site

O site do desafio está em [`docs/`](docs/), no formato que o GitHub Pages publica sem nenhuma
configuração extra:

1. **Settings → Pages**
2. **Source:** Deploy from a branch
3. **Branch:** `main` · **Folder:** `/docs`
4. Salvar. Em ~1 minuto o site sobe em `https://<org>.github.io/<repo>/`

> **Repositório privado?** Páginas em repositórios privados exigem plano pago (GitHub Pro, Team
> ou Enterprise). Em plano gratuito, ou o repositório é público, ou o site precisa ser hospedado
> em outro lugar — a pasta `docs/` é estática e funciona em qualquer host.

O site inclui os CSVs: o time baixa tudo direto da página, sem pedir acesso a ninguém.

| Página | O que é |
|--------|---------|
| `docs/index.html` | O desafio, o baseline a bater e como começar em 30 minutos |
| `docs/dados.html` | Os 21 arquivos com tamanho, linhas e checksum, e o formato de resposta |
| `docs/regras.html` | As 40 regras de negócio, a rede, os custos e os KPIs |
| `docs/conceitos.html` | Material auxiliar: ATP, CTP, abastecimento, lead time e frete |

---

## Estrutura

```
desafio/
├── README.md                    guia do participante
├── dados/v1.0.0/                o pacote: 21 arquivos, 4,6 MB
├── ferramentas/
│   ├── comum.py                 leitura dos dados, calendário, custos
│   ├── baseline_guloso.py       a política que a operação usa hoje
│   ├── exemplo_prototipo.py     protótipo comentado — a receita dos 5 passos
│   └── avaliar.py               o avaliador oficial
├── gerador/                     como os dados foram construídos (seed 42)
└── privado/                     GABARITO — fora do git, fora do site

docs/                            o site publicado (GitHub Pages)
└── desafio/                     os documentos-fonte em Markdown
```

---

## Reconstruir tudo

Um comando regenera os dados, o dicionário, os checksums, o pacote `.zip` e o site:

```bash
python desafio/gerador/gerar_pacote.py
```

Ele confere duas coisas ao final e falha se alguma quebrar:

- **Determinismo** — mesma seed, mesmos checksums. Se dois builds divergirem, algo no gerador
  deixou de ser reprodutível.
- **Vazamento de gabarito** — nenhum arquivo de `desafio/privado/` pode entrar no `.zip`.

---

## O gabarito

`desafio/privado/` contém o trânsito realizado e o atraso real dos recebimentos não confirmados
das janelas de teste. É o que o avaliador usa e o que os participantes **não** podem ter.

A pasta está no `.gitignore` e o build recusa publicar um pacote que a contenha. Se você for
hospedar os arquivos em outro lugar, confira antes.

---

## Rodar o desafio

Python 3.10+ e biblioteca padrão. Sem pandas, sem solver, sem instalar nada.

```bash
# a política atual, para ter a referência
python desafio/ferramentas/baseline_guloso.py --janela public
python desafio/ferramentas/avaliar.py --resposta desafio/respostas/baseline/public

# o protótipo de exemplo, que corta 21,6% do custo
python desafio/ferramentas/exemplo_prototipo.py --janela public
python desafio/ferramentas/avaliar.py --resposta desafio/respostas/exemplo/public
```

---

## Documentos

| Documento | Para quê |
|-----------|----------|
| [desafio/README.md](desafio/README.md) | Guia do participante: começar em 30 minutos |
| [docs/desafio/01-business-scope.md](docs/desafio/01-business-scope.md) | As 40 regras de negócio, `BR-101` a `BR-509` |
| [docs/desafio/conceitos-supply-chain.md](docs/desafio/conceitos-supply-chain.md) | Supply chain para quem nunca viu supply chain |
| [desafio/dados/v1.0.0/data_dictionary.md](desafio/dados/v1.0.0/data_dictionary.md) | Toda coluna, tipo e unidade |

---

*Produzido pelo squad `desafio-supply-chain-squad` (AIOX).*
