# Órion · Ecossistema Inteligente de Gestão Hospitalar

Análise da pressão sobre a rede hospitalar do SUS nas 27 unidades federativas, a partir
de dados públicos do DATASUS e do IBGE. Pipeline em Python, indicadores validados,
clusterização por perfil de pressão, camada analítica no Oracle Autonomous AI Database e
painel interativo em Power BI.

**Desafio Oracle + FIAP · Sprint 2 · Equipe FIAPIANOS · Turma A · Data Science**

---

## Painel interativo

**[Acesse o painel publicado](https://app.powerbi.com/view?r=eyJrIjoiYTE3MDcyN2MtOWE4My00MWZjLWIxMWYtNzU2YTYyNTRiMDVkIiwidCI6IjExZGJiZmUyLTg5YjgtNDU0OS1iZTEwLWNlYzM2NGU1OTU1MSIsImMiOjR9)**

**Visão geral** — indicadores nacionais, dispersão dos três perfis de pressão hospitalar
e ranking de ocupação das 27 UFs.

**Detalhe por UF** — tabela completa com segmentador interativo e série mensal do estado
selecionado.

O arquivo de origem está em [`dashboard/`](dashboard/) e as capturas em
[`docs/capturas/`](docs/capturas/).

---

## Indicadores

Competências jan–dez/2025, Brasil:

| Indicador | Valor |
|---|---|
| AIHs aprovadas | 14.645.121 |
| Taxa de ocupação | 54,99% |
| Permanência média | 4,91 dias |
| Custo médio por AIH | R$ 1.759,72 |

Os quatro valores foram obtidos por **três caminhos independentes** — o pipeline em
Python, uma consulta SQL no Oracle e o Power BI lendo o banco diretamente — e conferem
entre si.

### Como cada um é calculado

```
AIHs aprovadas       Σ aih_aprovadas
Taxa de ocupação     Σ dias_permanência ÷ (leitos_sus × dias_no_mês) × 100
Permanência média    Σ dias_permanência ÷ Σ aih_aprovadas
Custo médio por AIH  Σ valor_total ÷ Σ aih_aprovadas
```

Ocupação e permanência são **razões de somas, não médias de médias**. Calculá-las como
média simples entre estados desloca o resultado em vários pontos percentuais.

---

## Fontes

| Fonte | Conteúdo | Competência |
|---|---|---|
| SIH/SUS · DATASUS | AIHs aprovadas, dias de permanência, valor total | jan–dez/2025 |
| CNES · DATASUS | Leitos SUS por UF | dez/2025 |
| IBGE · SIDRA | População residente estimada por UF | 2025 |

Extração em 12/08/2026. Os 11 arquivos originais estão em [`data/raw/`](data/raw/).

### Limitações

Dado público do DATASUS é publicado em lote mensal, com defasagem de cerca de dois
meses. **Este painel não opera em tempo real** — seu valor está na comparação entre
estados e na série do ano fechado.

A base é administrativa, de faturamento: uma AIH aprovada não equivale exatamente a uma
internação, e reinternações no período contam separadamente. Leitos do CNES refletem
cadastro na competência de referência, não ocupação instantânea.

---

## Modelo analítico

K-means com k=3 sobre taxa de ocupação, permanência média e leitos SUS por mil
habitantes, com variáveis padronizadas. Três perfis:

| Perfil | UFs |
|---|---|
| Alta pressão | 14 |
| Baixa rotatividade | 5 |
| Rede folgada | 8 |

**O silhouette de k=2 é maior que o de k=3.** Optou-se por k=3 por interpretabilidade:
dois grupos não separam rede folgada de baixa rotatividade. Os nomes dos perfis são
interpretação da equipe, não rótulos da fonte.

Como o cluster usa três dimensões, um estado pode ter ocupação menor que outro e ainda
assim pertencer ao grupo de maior pressão — o Acre, com 48,05%, é "Alta pressão"
enquanto Pernambuco, com 50,97%, é "Rede folgada".

---

## Arquitetura

```
CSVs públicos  →  pipeline Python  →  CSV processado  →  Oracle Autonomous  →  Power BI
 TabNet/SIDRA      orion_etl.py                          AI Database 26ai      Importar
                   orion_cluster.py
```

### Camada Oracle

Instância `orion` no Oracle Autonomous AI Database, plano Always Free, região Brazil
Southeast (Vinhedo), versão 26ai, workload Lakehouse.

| Objeto | Conteúdo |
|---|---|
| `FATO_MENSAL_UF` | 486 linhas · 30 colunas |
| `INDICADORES_UF_2025` | 27 linhas · 21 colunas |
| `CLUSTERS_UF` | 27 linhas · 10 colunas |
| `MART_INDICADORES_UF` | view com nomes legíveis e join dos clusters |

Consulta de validação executada no banco:

```sql
SELECT
    ROUND(SUM(AIH_APROVADAS))                                   AS aih_aprovadas,
    ROUND(SUM(DIAS_PERMANENCIA) /
          SUM(LEITOS_SUS_TOTAL * DIAS_NO_MES) * 100, 2)         AS ocupacao_pct,
    ROUND(SUM(DIAS_PERMANENCIA) / SUM(AIH_APROVADAS), 2)        AS permanencia_media,
    ROUND(SUM(VALOR_TOTAL)      / SUM(AIH_APROVADAS), 2)        AS custo_medio_aih
FROM FATO_MENSAL_UF
WHERE ANO = 2025;
```

O Power BI conecta ao banco via wallet, no modo Importar.

---

## Estrutura do repositório

```
orion/
├── README.md
├── requirements.txt        pandas, scikit-learn
├── .gitignore
├── src/
│   ├── orion_etl.py        pipeline de extração e indicadores
│   └── orion_cluster.py    clusterização KMeans
├── data/
│   ├── raw/                11 CSVs originais do TabNet e SIDRA
│   └── processed/          saídas do pipeline e da clusterização
├── dashboard/
│   └── orion.pbix          painel Power BI
└── docs/
    ├── dicionario_dados.md
    ├── dashboard_powerbi.md
    └── capturas/           evidências do banco e do painel
```

---

## Como reproduzir

```bash
git clone https://github.com/Chofss99/orion.git
cd orion
pip install -r requirements.txt

python src/orion_etl.py       # gera os indicadores em data/processed/
python src/orion_cluster.py   # gera a clusterização
```

O pipeline roda sobre os CSVs em `data/raw/` e não depende do Oracle — a camada de banco
é o destino da carga, não a origem do cálculo.

Para abrir o painel sobre os dados locais, use `dashboard/orion.pbix` apontando para o
CSV processado. Para conectá-lo ao Oracle é preciso a wallet da instância, que **não está
versionada** por ser credencial de acesso.

---

## Próximos passos

**Consulta em linguagem natural** sobre a view MART, via Select AI. A camada semântica já
existe — a view tem nomes legíveis, que é o pré-requisito. Falta o provedor de LLM: o OCI
Generative AI não está disponível na região do banco para o plano atual. Limitação de
infraestrutura, não de modelagem.

**Atualização mensal automática** conforme o DATASUS publica novas competências.

**Ampliação para nível municipal**, já suportada pela granularidade da fonte.

---

## Equipe

FIAPIANOS · Turma A · Data Science

<!-- preencher com os cinco integrantes conforme a ficha oficial -->

Agradecimentos à Oracle e à FIAP pelo desafio e pela infraestrutura, e aos professores e
orientadores pelo acompanhamento.

