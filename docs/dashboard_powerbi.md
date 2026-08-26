# Painel Órion — especificação para Power BI

Base: `orion_powerbi.csv` · 486 linhas · 27 UFs × 18 competências
Fonte: SIH/SUS e CNES (DATASUS) e IBGE/SIDRA · extração em 12/08/2026

---

## 1. Importar

**Obter dados → Texto/CSV** → selecione `orion_powerbi.csv`.

Na janela de visualização, confira antes de carregar:

| Configuração | Valor |
|---|---|
| Origem do arquivo | 65001: Unicode (UTF-8) |
| Delimitador | Ponto e vírgula |
| Detecção de tipo de dados | Com base nos 200 primeiros |

Depois clique em **Transformar Dados** e verifique os tipos:

- `data_competencia` → **Data**
- `competencia_suspeita` e `ano_fechado_2025` → **Verdadeiro/Falso**
- todas as colunas numéricas → **Número decimal** (ou Número inteiro para contagens)
- `uf_cod`, `uf_sigla`, `uf_nome`, `regiao`, `cluster_nome`, `competencia` → **Texto**

Se algum decimal vier como texto, é a configuração regional. Em **Página Inicial → Tipo de Dados → Usando Localidade**, escolha Número Decimal / Português (Brasil).

---

## 2. Medidas DAX

Crie uma tabela de medidas (Inserir → Inserir Dados → nomear `_Medidas`) e adicione:

```dax
AIHs aprovadas = SUM('orion_powerbi'[aih_aprovadas])

Dias de permanência = SUM('orion_powerbi'[dias_permanencia])

Leitos SUS = AVERAGE('orion_powerbi'[leitos_sus_total])

Valor total = SUM('orion_powerbi'[valor_total])

Óbitos = SUM('orion_powerbi'[obitos])

Taxa de ocupação % =
DIVIDE(
    SUM('orion_powerbi'[dias_permanencia]),
    SUMX('orion_powerbi', 'orion_powerbi'[leitos_sus_total] * 'orion_powerbi'[dias_no_mes])
) * 100

Permanência média =
DIVIDE(
    SUM('orion_powerbi'[dias_permanencia]),
    SUM('orion_powerbi'[aih_aprovadas])
)

Custo médio por AIH =
DIVIDE(
    SUM('orion_powerbi'[valor_total]),
    SUM('orion_powerbi'[aih_aprovadas])
)

Taxa de mortalidade % =
DIVIDE(
    SUM('orion_powerbi'[obitos]),
    SUM('orion_powerbi'[aih_aprovadas])
) * 100

Leitos SUS por mil hab =
DIVIDE(
    AVERAGE('orion_powerbi'[leitos_sus_total]),
    AVERAGE('orion_powerbi'[populacao])
) * 1000

UFs acima de 60% =
CALCULATE(
    DISTINCTCOUNT('orion_powerbi'[uf_nome]),
    FILTER(
        SUMMARIZE('orion_powerbi', 'orion_powerbi'[uf_nome], "oc", [Taxa de ocupação %]),
        [oc] > 60
    )
)
```

**Importante:** a taxa de ocupação e a permanência média são razões, não médias. Somar percentuais de UFs diferentes dá resultado errado — por isso as medidas recalculam a partir dos numeradores e denominadores.

Formatação: taxa de ocupação com 1 casa decimal, custo em R$ com 2 casas, permanência com 1 casa.

---

## 3. Filtros da página

Coloque na barra superior, como segmentações de dados:

| Campo | Tipo | Padrão |
|---|---|---|
| `ano_fechado_2025` | Botão / lista | **Verdadeiro** |
| `regiao` | Lista suspensa | Todas |
| `cluster_nome` | Lista de botões | Todos |
| `uf_nome` | Lista suspensa com busca | Todas |

O filtro `ano_fechado_2025 = Verdadeiro` restringe a jan–dez/2025, que é o consolidado válido. Deixe-o ativo por padrão e visível — é a mesma decisão metodológica dos outros slides.

---

## 4. Visuais

### Linha superior — quatro cartões

| Cartão | Medida | Valor esperado (2025) |
|---|---|---|
| AIHs aprovadas | `[AIHs aprovadas]` | 14,6 mi |
| Taxa de ocupação | `[Taxa de ocupação %]` | 55,0% |
| Permanência média | `[Permanência média]` | 4,9 dias |
| Custo médio por AIH | `[Custo médio por AIH]` | R$ 1.759,72 |

Confira contra esses números depois de montar. Se não baterem, o filtro de ano ou o tipo de dado está errado.

### Gráfico de linhas — sazonalidade

- Eixo X: `data_competencia`
- Eixo Y: `[AIHs aprovadas]`
- Título: *AIHs aprovadas por competência*

Deve mostrar pico em jul/2025 (1,27 mi) e vale em fev/2025 (1,13 mi).

### Gráfico de dispersão — os três perfis

- Eixo X: `leitos_sus_por_mil_hab`
- Eixo Y: `[Taxa de ocupação %]`
- Legenda: `cluster_nome`
- Detalhes: `uf_sigla`
- Linha constante em Y = 60

É o gráfico que sustenta o argumento da clusterização. Se couber apenas um visual analítico, que seja este.

### Barras horizontais — ranking

- Eixo Y: `uf_sigla`
- Eixo X: `[Taxa de ocupação %]`
- Cor por `cluster_nome`
- Ordenar decrescente

Distrito Federal no topo com 69,8%; Rondônia e Rio Grande do Norte na base com 41,7%.

### Tabela — detalhe por UF

Colunas: `uf_nome`, `cluster_nome`, `[Taxa de ocupação %]`, `[Permanência média]`, `[Custo médio por AIH]`, `[Leitos SUS por mil hab]`.

Aplique formatação condicional por barras de dados na coluna de ocupação.

### Mapa (opcional)

O Power BI reconhece `uf_nome` como localização se você definir a categoria de dados como **Estado ou Província**. Use `[Taxa de ocupação %]` como saturação de cor. Confirme que os 27 estados apareceram — se algum sumir, o nome não foi reconhecido.

---

## 5. Cuidados

**Não escreva "tempo real" em lugar nenhum do painel.** A base é batch mensal com cerca de dois meses de defasagem. Um rótulo *"Competências jan–dez/2025 · atualização mensal"* no rodapé resolve e mantém a coerência com o resto do deck.

**As competências de 2026 estão na base mas fora do consolidado.** Quatro delas são parciais (`competencia_suspeita = Verdadeiro`). Se você desligar o filtro de ano, os indicadores mudam — e é bom saber disso antes que alguém pergunte ao vivo.

**Rodapé de fonte em toda página:** *Fonte: SIH/SUS e CNES (DATASUS) e IBGE/SIDRA · competências jan–dez/2025 · extração em 12/08/2026.*

---

## 6. Para o slide

Depois de montar, capture:

1. A visão geral completa, com os filtros visíveis
2. Um recorte do gráfico de dispersão com a legenda dos clusters
3. Um recorte do ranking de UFs

Três capturas bastam. Cada uma ganha uma legenda explicando o que ela mostra — o template pede explicação do significado de cada entrega, não só a imagem.
