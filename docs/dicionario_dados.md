# Dicionário de dados

## `fato_mensal_uf.csv`

Granularidade: **uma linha por UF e competência**. 486 linhas — 27 UFs × 18 competências
(jan/2025 a jun/2026).

Formato: separador `;`, decimal `,`, codificação UTF-8.

### Chaves

| Coluna | Tipo | Descrição |
|---|---|---|
| `uf_cod` | inteiro | Código IBGE da UF, 2 dígitos. O primeiro dígito indica a região (1 Norte, 2 Nordeste, 3 Sudeste, 4 Sul, 5 Centro-Oeste) |
| `uf_nome` | texto | Nome da unidade federativa |
| `ano` | inteiro | Ano da competência |
| `mes` | inteiro | Mês da competência, 1 a 12 |
| `competencia` | texto | Ano e mês no formato `AAAA-MM` |

### Métricas do SIH/SUS

Valores de fluxo — referem-se ao que aconteceu **durante** a competência.

| Coluna | Tipo | Descrição |
|---|---|---|
| `aih_aprovadas` | decimal | Autorizações de Internação Hospitalar aprovadas no período |
| `internacoes` | decimal | Internações registradas. Difere ligeiramente de `aih_aprovadas` porque uma internação pode gerar mais de uma AIH |
| `dias_permanencia` | decimal | Soma dos dias de permanência de todas as internações |
| `media_permanencia` | decimal | Média de permanência publicada pelo SIH |
| `valor_total` | decimal | Valor total pago pelas internações, em reais |
| `obitos` | decimal | Óbitos hospitalares registrados |

### Métricas do CNES

Valores de estoque — referem-se à situação **no momento** da competência. Por isso são
agregados por média ao longo do ano, nunca por soma.

| Coluna | Tipo | Descrição |
|---|---|---|
| `leitos_int_sus` | decimal | Leitos de internação disponíveis ao SUS: cirúrgico, clínico, obstétrico, pediátrico e hospital-dia |
| `leitos_int_exist` | decimal | Leitos de internação existentes, SUS e não SUS |
| `leitos_comp_sus` | decimal | Leitos complementares disponíveis ao SUS — é onde ficam as UTIs |
| `leitos_comp_exist` | decimal | Leitos complementares existentes, SUS e não SUS |

### Demografia

| Coluna | Tipo | Descrição |
|---|---|---|
| `populacao` | inteiro | População residente estimada pelo IBGE. O pipeline aplica o ano mais recente disponível a todas as competências |

### Calendário

| Coluna | Tipo | Descrição |
|---|---|---|
| `dias_no_mes` | inteiro | Dias do mês da competência. Entra no denominador da taxa de ocupação |

### Controle de qualidade

| Coluna | Tipo | Descrição |
|---|---|---|
| `razao_mediana` | decimal | `aih_aprovadas` dividido pela mediana de AIHs da própria UF em toda a série |
| `competencia_suspeita` | booleano | `True` quando `razao_mediana < 0,60` ou quando não há dado. Indica competência provavelmente incompleta |

### Derivadas

| Coluna | Cálculo | Descrição |
|---|---|---|
| `leitos_sus_total` | `leitos_int_sus + leitos_comp_sus` | Total de leitos disponíveis ao SUS. É o denominador correto da ocupação |
| `leitos_exist_total` | `leitos_int_exist + leitos_comp_exist` | Total de leitos da rede, SUS e não SUS |
| `taxa_ocupacao_pct` | `dias_permanencia ÷ (leitos_sus_total × dias_no_mes) × 100` | Percentual de ocupação dos leitos SUS |
| `media_permanencia_calc` | `dias_permanencia ÷ aih_aprovadas` | Permanência média recalculada. Serve de conferência contra a `media_permanencia` publicada |
| `custo_medio_aih` | `valor_total ÷ aih_aprovadas` | Valor médio pago por internação, em reais |
| `taxa_mortalidade_pct` | `obitos ÷ aih_aprovadas × 100` | Mortalidade hospitalar |
| `leitos_sus_por_mil_hab` | `leitos_sus_total ÷ (populacao ÷ 1000)` | Oferta de leitos por habitante |
| `aih_por_mil_hab` | `aih_aprovadas ÷ (populacao ÷ 1000)` | Volume de internações por habitante |
| `pressao_aih_por_leito` | `aih_aprovadas ÷ leitos_sus_total` | Giro da rede: quantas internações cada leito absorveu |
| `pct_rede_sus` | `leitos_sus_total ÷ leitos_exist_total × 100` | Fatia da rede hospitalar disponível ao SUS |
| `pct_leitos_uti` | `leitos_comp_sus ÷ leitos_sus_total × 100` | Participação de leitos complementares — proxy de complexidade |

---

## Como agregar corretamente

**Fluxos somam.** `aih_aprovadas`, `dias_permanencia`, `valor_total` e `obitos` podem
ser somados entre competências e entre UFs.

**Estoques não somam ao longo do tempo.** As colunas de leito representam a situação em
cada competência. Somar doze meses daria doze vezes a rede real. Agregue por média.

**Razões nunca são médias de razões.** `taxa_ocupacao_pct`, `media_permanencia`,
`custo_medio_aih`, `taxa_mortalidade_pct`, `pct_rede_sus` e `pct_leitos_uti` precisam
ser recalculadas a partir dos numeradores e denominadores agregados.

Exemplo — taxa de ocupação nacional em 2025:

```python
oc = df.dias_permanencia.sum() / (df.leitos_sus_total * df.dias_no_mes).sum() * 100
# 54,99 — correto

oc_errado = df.taxa_ocupacao_pct.mean()
# ~52 — média das taxas de UFs de portes diferentes, sem significado
```

---

## `indicadores_uf_2025.csv`

Uma linha por UF, consolidando as 12 competências de 2025. Colunas equivalentes às da
tabela fato, mais:

| Coluna | Descrição |
|---|---|
| `meses_validos` | Competências consideradas. Deve ser 12 para todas as UFs; valor menor indica que alguma competência foi excluída pelo controle de qualidade |
| `dias_no_periodo` | Soma dos dias das competências agregadas — 365 para o ano fechado |

---

## `clusters_uf.csv`

Saída do `orion_cluster.py`. Uma linha por UF.

| Coluna | Descrição |
|---|---|
| `cluster` | Rótulo numérico atribuído pelo KMeans. **Não tem significado** — muda entre execuções |
| `cluster_nome` | Nome atribuído pelas características das médias: Alta pressão, Baixa rotatividade ou Rede folgada |

As demais colunas são as quatro features usadas no agrupamento, mais taxa de ocupação e
custo médio para interpretação.

---

## `competencias_suspeitas.csv`

Registro das competências marcadas pelo controle de qualidade. Serve de evidência do
que foi excluído do consolidado e por quê.

| Coluna | Descrição |
|---|---|
| `uf_nome` | Unidade federativa |
| `competencia` | Ano e mês |
| `aih_aprovadas` | Valor observado — vazio quando não há dado |
| `razao_mediana` | Proporção em relação à mediana da UF |
