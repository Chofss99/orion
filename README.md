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

Consolidado de jan–dez/2025 — ano fechado, 12 competências válidas nas 27 UFs:

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
Taxa de ocupação     Σ dias_permanência ÷ (leitos_sus × dias_no_período) × 100
Permanência média    Σ dias_permanência ÷ Σ aih_aprovadas
Custo médio por AIH  Σ valor_total ÷ Σ aih_aprovadas
```

O denominador da ocupação soma **leitos de internação SUS e leitos complementares
(UTI)** — no CNES eles ficam em menus separados.

Ocupação e permanência são **razões de somas, não médias de médias**. Calculá-las como
média simples entre estados desloca o resultado em vários pontos percentuais.

### A dispersão entre estados

A média nacional esconde realidades opostas. Apenas 5 das 27 UFs passam de 60% de
ocupação.

| Indicador | Mínimo | Máximo |
|---|---|---|
| Taxa de ocupação | 41,7% (RO e RN) | 69,8% (DF) |
| Custo médio por AIH | R$ 941,86 | R$ 2.223,47 |
| Leitos SUS por 1.000 hab | 1,34 | 2,59 |

---

## Fontes

Quatro fontes públicas, onze arquivos CSV, extração manual em 12/08/2026.

| Fonte | Conteúdo | Período |
|---|---|---|
| SIH/SUS · DATASUS | AIHs aprovadas, internações, dias de permanência, permanência média, valor total, óbitos | jan/2025 – jun/2026 |
| CNES · Leitos de internação | Quantidade SUS e quantidade existente | jan/2025 – jun/2026 |
| CNES · Leitos complementares (UTI) | Quantidade SUS e quantidade existente | jan/2025 – jun/2026 |
| IBGE · SIDRA, tabela 6579 | População residente estimada | 2024 e 2025 |

Granularidade: UF × mês no DATASUS, UF × ano no IBGE. Os arquivos originais estão em
[`data/raw/`](data/raw/).

### Controle de qualidade

O pipeline compara cada UF-mês com a mediana da própria UF. Competência abaixo de 60%
da mediana, ou sem dado, é marcada como **suspeita** e registrada em arquivo próprio.

Quatro ocorrências em 486 linhas, todas em 2026 — o próprio DATASUS registra que os
últimos seis meses estão sujeitos a atualização. Por isso o consolidado usa apenas
jan–dez/2025, ano fechado.

### Limitações

Dado público do DATASUS é publicado em lote mensal, com defasagem de cerca de dois
meses. **Este painel não opera em tempo real** — seu valor está na comparação entre
estados e na série do ano fechado.

A base é administrativa, de faturamento: uma AIH aprovada não equivale exatamente a uma
internação, e reinternações no período contam separadamente. Leitos do CNES refletem
cadastro na competência de referência, não ocupação instantânea.

---

## Modelo analítico

**KMeans com k=3**, sobre quatro features padronizadas com `StandardScaler`. Testado com
k de 2 a 6, `n_init=50`, `random_state=42`, validação por silhouette.

**Features:** pressão (AIHs por leito), permanência média, leitos SUS por 1.000
habitantes e % de leitos de UTI.

A **taxa de ocupação ficou de fora** do modelo: correlaciona +0,70 com pressão e +0,71
com % de UTI, e entraria como informação repetida.

### Por que k=3 e não k=2

k=2 tem silhouette maior — 0,399 contra 0,347 — mas separa apenas em "mais pressionado"
e "menos pressionado". k=3 isola um terceiro grupo que ocupa leito por permanência
longa, não por volume, que é o mecanismo que o projeto precisa distinguir. É uma escolha
de interpretabilidade, declarada.

### Os três perfis

Nomeados pela média das features, não pelo número do algoritmo.

| Cluster | UFs | AIHs/leito | Permanência | Leitos/mil | % UTI |
|---|---|---|---|---|---|
| Alta pressão | 12 | 44,4 | 4,8 | 1,60 | 13,5% |
| Baixa rotatividade | 5 | 31,0 | 5,9 | 1,97 | 11,3% |
| Rede folgada | 10 | 35,2 | 4,8 | 1,97 | 9,7% |

**Alta pressão** — SP · RJ · MG · PR · SC · DF · ES · PA · AM · AC · MS · SE
**Baixa rotatividade** — AL · CE · PB · RS · RR
**Rede folgada** — AP · BA · GO · MA · MT · PE · PI · RN · RO · TO

O achado central: Baixa rotatividade e Rede folgada têm **exatamente os mesmos 1,97
leitos por 1.000 habitantes**, e ocupações de 50,0% e 46,2%. A diferença não é
quantidade de leito — é permanência de 5,9 contra 4,8 dias. Nenhuma média nacional
mostra isso.

Como o cluster usa quatro dimensões, um estado pode ter ocupação menor que outro e ainda
assim pertencer ao grupo de maior pressão — o Acre, com 48,05%, é "Alta pressão"
enquanto Pernambuco, com 50,97%, é "Rede folgada".

---

## Arquitetura

```
CSVs públicos  →  pipeline Python  →  CSV validado  →  Oracle Autonomous  →  Power BI
 TabNet/SIDRA      orion_etl.py                        AI Database 26ai      Importar
                   orion_cluster.py
```

### Camada Oracle

Instância `orion` no Oracle Autonomous AI Database, plano Always Free, região Brazil
Southeast (Vinhedo), versão 26ai, workload Lakehouse.

| Objeto | Conteúdo |
|---|---|
| `FATO_MENSAL_UF` | 486 linhas (27 UFs × 18 competências) · 30 colunas |
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

python src/orion_etl.py Dados_orion saida   # gera a tabela fato e os indicadores
python src/orion_cluster.py                 # gera a clusterização
```

O pipeline identifica cada arquivo pelo **cabeçalho interno, não pelo nome** — continua
funcionando com os CSVs renomeados ou com a acentuação quebrada.

Ele roda sobre os CSVs em `data/raw/` e não depende do Oracle: a camada de banco é o
destino da carga, não a origem do cálculo.

Para conectar o painel ao Oracle é preciso a wallet da instância, que **não está
versionada** por ser credencial de acesso.

---

## Próximos passos

**Reprocessar por Região de Saúde (CIR).** O mesmo pipeline sobre as ~450 regiões, em
vez das 27 UFs. É a evolução que dá granularidade real à clusterização.

**Consulta em linguagem natural** sobre a view MART, via Select AI. A camada semântica já
existe — a view tem nomes legíveis, que é o pré-requisito. Falta o provedor de LLM: o OCI
Generative AI não está disponível na região do banco para o plano atual. Limitação de
infraestrutura, não de modelagem.

**Atualização mensal automática** conforme o DATASUS publica novas competências.

---

## Equipe

FIAPIANOS · Turma A · Data Science

Agradecimentos à Oracle e à FIAP pelo desafio e pela infraestrutura, e aos professores e
orientadores pelo acompanhamento.
