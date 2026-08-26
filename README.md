# Órion — Ecossistema Inteligente de Gestão Hospitalar

Integra fontes públicas de saúde (SIH/SUS, CNES e IBGE) em uma base analítica única,
calcula indicadores de ocupação de leitos, permanência média e custo por internação
para cada estado brasileiro, e agrupa as UFs por padrão de pressão hospitalar.

**Challenge Oracle + FIAP · Data Science · Equipe FIAPIANOS**

---

## O que o projeto faz

O ponto de partida é uma constatação: **a média nacional esconde realidades opostas.**
A taxa de ocupação de leitos SUS no Brasil foi de 55,0% em 2025 — mas varia de 41,7%
em Rondônia a 69,8% no Distrito Federal, e apenas 5 das 27 UFs passam de 60%.

O pipeline extrai o dado bruto das fontes oficiais, valida, calcula os indicadores por
UF e competência, e aplica clusterização para identificar perfis de pressão hospitalar
que uma média nacional não revela.

### Indicadores nacionais — jan a dez/2025

| Indicador | Valor |
|---|---|
| AIHs aprovadas | 14.645.121 |
| Taxa de ocupação de leitos SUS | 55,0% |
| Permanência média | 4,9 dias |
| Custo médio por internação | R$ 1.759,72 |
| Taxa de mortalidade hospitalar | 4,30% |
| Leitos SUS por 1.000 habitantes | 1,68 |

### Perfis identificados

| Perfil | UFs | Característica |
|---|---|---|
| Alta pressão | 12 | menos leitos por habitante, mais UTI, mais giro |
| Baixa rotatividade | 5 | permanência longa (5,9 dias); ocupam por demora, não por volume |
| Rede folgada | 10 | rede ampla, menor complexidade, custo menor |

Baixa rotatividade e Rede folgada têm **exatamente os mesmos 1,97 leitos por 1.000
habitantes** e ocupações de 50,0% e 46,2%. A diferença não é quantidade de leito —
é permanência.

---

## Estrutura

```
orion/
├── src/
│   ├── orion_etl.py         extração, limpeza, validação e indicadores
│   └── orion_cluster.py     clusterização KMeans dos perfis de pressão
├── data/
│   ├── raw/                 11 CSVs originais do TabNet e SIDRA
│   └── processed/           saídas do pipeline
├── docs/
│   ├── guia_extracao.md     como baixar os dados das fontes oficiais
│   ├── dicionario_dados.md  o que é cada coluna e como é calculada
│   └── dashboard_powerbi.md como montar o painel
└── dashboard/
    └── orion.pbix           painel do Power BI
```

---

## Como reproduzir

Requer Python 3.10 ou superior.

```bash
git clone https://github.com/<usuario>/orion.git
cd orion
pip install -r requirements.txt
```

### 1. Pipeline de ETL

```bash
python src/orion_etl.py data/raw data/processed
```

Lê os 11 CSVs e gera quatro arquivos:

| Arquivo | Conteúdo |
|---|---|
| `fato_mensal_uf.csv` | 486 linhas — 27 UFs × 18 competências, todas as métricas e indicadores |
| `indicadores_uf_2025.csv` | consolidado do ano fechado por UF |
| `kpis_brasil_2025.csv` | resumo nacional |
| `competencias_suspeitas.csv` | competências incompletas detectadas |

### 2. Clusterização

```bash
python src/orion_cluster.py data/processed/indicadores_uf_2025.csv data/processed
```

Gera `clusters_uf.csv`, `perfis_cluster.csv` e `silhouette_por_k.csv`.

---

## Decisões metodológicas

### Identificação de arquivo pelo cabeçalho interno

O ETL não confia no nome do arquivo. Compactadores corrompem acentos, e os CSVs do
TabNet saem com nomes como `Média de permanência.csv` e `óbitos.csv`. O pipeline lê
as duas primeiras linhas de cada arquivo e identifica o conteúdo por ali — continua
funcionando com os arquivos renomeados.

### Detecção de competências incompletas

O SIH publica competências recentes ainda em consolidação, e o próprio DATASUS
registra que os últimos seis meses estão sujeitos a atualização. Um mês parcial
aparece como queda abrupta de AIHs.

O pipeline compara cada UF-mês com a mediana da própria UF e marca como suspeito o
que ficar abaixo de 60% — ou vier sem dado. Foram detectadas **4 ocorrências**, todas
em 2026:

| UF | Competência | AIHs | % da mediana |
|---|---|---|---|
| Roraima | mai/2026 | 352 | 12% |
| Tocantins | jun/2026 | 845 | 9% |
| Acre | jun/2026 | — | sem dado |
| Roraima | jun/2026 | — | sem dado |

Por isso o consolidado usa **apenas jan–dez/2025**: ano fechado, 12 competências
válidas nas 27 UFs.

### Taxa de ocupação

```
Taxa de ocupação (%) =        Σ dias de permanência (SIH)
                       ──────────────────────────────────────────────── × 100
                       (leitos internação SUS + leitos complementares SUS)
                                    × dias do período
```

O denominador precisa dos dois grupos de leito somados. No CNES, "Leitos Internação"
traz apenas cirúrgico, clínico, obstétrico, pediátrico e hospital-dia — a UTI fica em
"Leitos Complementares", num menu separado.

**Taxa de ocupação e permanência média são razões, não médias.** Somar percentuais de
UFs diferentes dá resultado errado; o cálculo sempre parte dos numeradores e
denominadores.

### Escolha do k na clusterização

O silhouette de k=2 é maior (0,399) que o de k=3 (0,347). A escolha de k=3 é de
interpretabilidade: k=2 separa apenas em "mais pressionado" e "menos pressionado",
enquanto k=3 isola um terceiro grupo que ocupa leito por permanência longa, não por
volume — o mecanismo que o projeto precisa distinguir.

Silhouette entre 0,3 e 0,4 indica **estrutura moderada**, coerente com 27 observações.

A taxa de ocupação foi deixada fora das features por correlacionar +0,70 com pressão e
+0,71 com % de UTI. Ela é tratada como resultado que os clusters explicam.

---

## Fontes

| Fonte | Extrações | Período |
|---|---|---|
| SIH/SUS — Morbidade Hospitalar por local de internação | AIH aprovadas, internações, dias de permanência, média de permanência, valor total, óbitos | jan/2025 – jun/2026 |
| CNES — Leitos de Internação | quantidade SUS e existente | jan/2025 – jun/2026 |
| CNES — Leitos Complementares (UTI) | quantidade SUS e existente | jan/2025 – jun/2026 |
| IBGE — SIDRA tabela 6579 | população residente estimada | 2024 e 2025 |

Todas as extrações foram feitas por download manual na interface web do
TabNet/DATASUS e do SIDRA/IBGE em 12/08/2026. O passo a passo, com caminhos de clique
e as armadilhas de cada fonte, está em `docs/guia_extracao.md`.

Última competência disponível no SIH: jun/2026 — defasagem de aproximadamente
dois meses.

---

## Estado do projeto

| Camada | Status |
|---|---|
| Origem — extração das fontes públicas | completo |
| Ingestão e processamento — ETL em Python | completo |
| Armazenamento — tabela fato validada em CSV | parcial |
| Modelagem — indicadores, controle de qualidade e clusterização | completo |
| Consumo — painel Power BI | completo |
| Consumo — consulta em linguagem natural (Select AI) | não iniciado |

### Próximas etapas

1. **Extração por Região de Saúde (CIR)** — reprocessar nas ~450 regiões com o mesmo
   pipeline, para granularidade abaixo da UF
2. **Carga no Oracle Autonomous Database** — Object Storage → `DBMS_CLOUD.COPY_DATA` →
   camadas RAW, STG e MART
3. **Select AI** sobre o schema MART
4. **Integração com ERPs hospitalares** por API, para leitura da operação em tempo real

A arquitetura prevê duas velocidades de dado: o público entra em batch mensal e calibra
o modelo; o ERP hospitalar entra em streaming e alimenta a operação.

---

## Licença dos dados

Os dados de SIH/SUS e CNES são publicados pelo DATASUS/Ministério da Saúde e os de
população pelo IBGE, ambos de acesso público. Este repositório redistribui os arquivos
originais em `data/raw/` para garantir a reprodutibilidade da análise.
