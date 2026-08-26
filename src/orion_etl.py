#!/usr/bin/env python3
"""
ÓRION — ETL Bloco 1
Lê os CSVs do TabNet (SIH/SUS e CNES) e do SIDRA/IBGE, normaliza e calcula
os indicadores que substituem os números fictícios do deck.

Uso:  python orion_etl.py <pasta_raw> <pasta_saida>
"""

import sys
import re
import unicodedata
from pathlib import Path
from calendar import monthrange

import pandas as pd

MESES = {"Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6,
         "Jul": 7, "Ago": 8, "Set": 9, "Out": 10, "Nov": 11, "Dez": 12}


# ----------------------------------------------------------------------
# Leitura
# ----------------------------------------------------------------------
def slug(texto: str) -> str:
    """Remove acentos e normaliza para comparação de nomes de arquivo."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def ler_tabnet(caminho: Path, metrica: str) -> pd.DataFrame:
    """
    CSV do TabNet: 3 linhas de título, cabeçalho na 4ª, corpo, linha 'Total',
    rodapé com fonte e notas. Encoding latin-1, separador ';', decimal ',',
    ausência marcada por '-'.
    Retorna formato longo: uf_cod | uf_nome | competencia | <metrica>
    """
    df = pd.read_csv(
        caminho, sep=";", encoding="latin-1", skiprows=3,
        decimal=",", thousands=None, na_values=["-", ""],
        engine="python", on_bad_lines="skip",
    )
    df = df.rename(columns={df.columns[0]: "uf_raw"})
    df["uf_raw"] = df["uf_raw"].astype(str).str.strip()

    # corta o rodapé: só interessam linhas que começam com o código de 2 dígitos
    df = df[df["uf_raw"].str.match(r"^\d{2}\s")]

    # descarta pseudo-UFs
    df = df[~df["uf_raw"].str.startswith("00")]          # Ignorado/exterior
    df = df.drop(columns=[c for c in df.columns if c.strip() == "Total"],
                 errors="ignore")

    df["uf_cod"] = df["uf_raw"].str[:2].astype(int)
    df["uf_nome"] = df["uf_raw"].str[3:].str.strip()
    df = df.drop(columns=["uf_raw"])

    cols_mes = [c for c in df.columns if re.match(r"^\d{4}/\w{3}$", str(c).strip())]
    longo = df.melt(id_vars=["uf_cod", "uf_nome"], value_vars=cols_mes,
                    var_name="competencia", value_name=metrica)
    longo[metrica] = pd.to_numeric(longo[metrica], errors="coerce")

    ano_mes = longo["competencia"].str.strip().str.split("/", expand=True)
    longo["ano"] = ano_mes[0].astype(int)
    longo["mes"] = ano_mes[1].map(MESES)
    longo["competencia"] = (longo["ano"].astype(str) + "-"
                            + longo["mes"].astype(str).str.zfill(2))
    return longo[["uf_cod", "uf_nome", "ano", "mes", "competencia", metrica]]


def ler_ibge(caminho: Path) -> pd.DataFrame:
    """SIDRA tabela 6579: UTF-8 com BOM, 4 linhas de cabeçalho, anos em colunas."""
    df = pd.read_csv(caminho, sep=";", encoding="utf-8-sig", skiprows=3,
                     dtype=str, engine="python", on_bad_lines="skip")
    df = df.rename(columns={df.columns[0]: "uf_cod", df.columns[1]: "uf_nome"})
    df = df[df["uf_cod"].astype(str).str.match(r"^\d{2}$")]      # tira Brasil (cód 1)

    anos = [c for c in df.columns if re.match(r"^\d{4}$", str(c).strip())]
    longo = df.melt(id_vars=["uf_cod"], value_vars=anos,
                    var_name="ano", value_name="populacao")
    longo["uf_cod"] = longo["uf_cod"].astype(int)
    longo["ano"] = longo["ano"].astype(int)
    longo["populacao"] = pd.to_numeric(
        longo["populacao"].astype(str).str.replace(r"[^\d]", "", regex=True),
        errors="coerce")
    return longo.dropna(subset=["populacao"])


# ----------------------------------------------------------------------
# Montagem
# ----------------------------------------------------------------------
MAPA = {
    "aih_aprovadas": ["aih_aprovadas"],
    "internacoes": ["internacoes"],
    "dias_permanencia": ["dias_de_permanencia"],
    "media_permanencia": ["media_de_permanencia"],
    "valor_total": ["valor_total"],
    "obitos": ["obitos"],
    "leitos_int_sus": ["cnes_uf_leitos_internacao_sus"],
    "leitos_int_exist": ["cnes_uf_leitos_internacao_exist"],
    "leitos_comp_sus": ["cnes_uf_leitos_complementares_sus"],
    "leitos_comp_exist": ["cnes_uf_leitos_complementares_exist"],
}


def sniff(caminho: Path) -> tuple:
    """Lê as duas primeiras linhas do arquivo para identificar o conteúdo."""
    for enc in ("latin-1", "utf-8-sig"):
        try:
            with open(caminho, encoding=enc) as fh:
                l1 = fh.readline().strip()
                l2 = fh.readline().strip()
            return l1, l2
        except UnicodeDecodeError:
            continue
    return "", ""


def localizar(raw: Path):
    """
    Identifica cada CSV pelo cabeçalho interno, não pelo nome do arquivo
    (compactadores costumam corromper acentos no nome).
    Linha 1 = dataset, linha 2 = métrica.
    """
    achados, ibge = {}, None

    metricas_sih = [
        ("aih aprovadas", "aih_aprovadas"),
        ("internações", "internacoes"),
        ("dias permanência", "dias_permanencia"),
        ("média permanência", "media_permanencia"),
        ("valor total", "valor_total"),
        ("óbitos", "obitos"),
    ]

    for arq in sorted(raw.rglob("*.csv")):
        l1, l2 = sniff(arq)
        t1, t2 = l1.lower(), l2.lower()

        if "tabela 6579" in t1 or "população residente" in t1:
            ibge = arq
            continue

        if "morbidade hospitalar" in t1:
            for chave, metrica in metricas_sih:
                if t2.startswith(chave):
                    achados[metrica] = arq
                    break

        elif "leitos" in t1:
            tipo = "comp" if "complementares" in t1 else "int"
            if t2.startswith("quantidade sus"):
                achados[f"leitos_{tipo}_sus"] = arq
            elif t2.startswith("quantidade existente"):
                achados[f"leitos_{tipo}_exist"] = arq

    return achados, ibge


def construir(raw: Path) -> pd.DataFrame:
    achados, arq_ibge = localizar(raw)

    faltando = set(MAPA) - set(achados)
    if faltando:
        print(f"  [aviso] métricas não encontradas: {', '.join(sorted(faltando))}")

    base = None
    for metrica, arq in achados.items():
        parte = ler_tabnet(arq, metrica)
        print(f"  ✓ {metrica:<22} {len(parte):>4} linhas   ({arq.name})")
        chaves = ["uf_cod", "uf_nome", "ano", "mes", "competencia"]
        base = parte if base is None else base.merge(parte, on=chaves, how="outer")

    if arq_ibge is not None:
        pop = ler_ibge(arq_ibge)
        ano_pop = pop["ano"].max()
        pop_ref = pop[pop["ano"] == ano_pop][["uf_cod", "populacao"]]
        base = base.merge(pop_ref, on="uf_cod", how="left")
        print(f"  ✓ populacao (IBGE {ano_pop}) aplicada a todas as competências")

    base["dias_no_mes"] = [monthrange(a, m)[1] for a, m in zip(base["ano"], base["mes"])]
    return base.sort_values(["uf_cod", "competencia"]).reset_index(drop=True)


# ----------------------------------------------------------------------
# Qualidade: detectar competências incompletas
# ----------------------------------------------------------------------
def marcar_incompletas(df: pd.DataFrame, limiar: float = 0.60) -> pd.DataFrame:
    """
    O SIH publica competências recentes ainda em consolidação. Um mês parcial
    aparece como queda abrupta de AIHs. Compara cada UF-mês com a mediana da
    própria UF e marca como suspeito o que ficar abaixo do limiar.
    """
    mediana = df.groupby("uf_cod")["aih_aprovadas"].transform("median")
    df["razao_mediana"] = df["aih_aprovadas"] / mediana
    df["competencia_suspeita"] = (df["razao_mediana"] < limiar) | df["aih_aprovadas"].isna()
    return df


# ----------------------------------------------------------------------
# Indicadores
# ----------------------------------------------------------------------
def indicadores(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["leitos_sus_total"] = d["leitos_int_sus"].fillna(0) + d["leitos_comp_sus"].fillna(0)
    d["leitos_exist_total"] = d["leitos_int_exist"].fillna(0) + d["leitos_comp_exist"].fillna(0)

    d["taxa_ocupacao_pct"] = (d["dias_permanencia"]
                              / (d["leitos_sus_total"] * d["dias_no_mes"]) * 100)
    d["media_permanencia_calc"] = d["dias_permanencia"] / d["aih_aprovadas"]
    d["custo_medio_aih"] = d["valor_total"] / d["aih_aprovadas"]
    d["taxa_mortalidade_pct"] = d["obitos"] / d["aih_aprovadas"] * 100
    d["leitos_sus_por_mil_hab"] = d["leitos_sus_total"] / (d["populacao"] / 1000)
    d["aih_por_mil_hab"] = d["aih_aprovadas"] / (d["populacao"] / 1000)
    d["pressao_aih_por_leito"] = d["aih_aprovadas"] / d["leitos_sus_total"]
    d["pct_rede_sus"] = d["leitos_sus_total"] / d["leitos_exist_total"] * 100
    d["pct_leitos_uti"] = d["leitos_comp_sus"] / d["leitos_sus_total"] * 100
    return d


def consolidar_ano(d: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Agrega o ano fechado por UF (soma fluxos, média de estoques)."""
    j = d[(d["ano"] == ano) & (~d["competencia_suspeita"])]
    g = j.groupby(["uf_cod", "uf_nome"]).agg(
        meses_validos=("competencia", "nunique"),
        aih_aprovadas=("aih_aprovadas", "sum"),
        dias_permanencia=("dias_permanencia", "sum"),
        valor_total=("valor_total", "sum"),
        obitos=("obitos", "sum"),
        leitos_sus_total=("leitos_sus_total", "mean"),
        leitos_comp_sus=("leitos_comp_sus", "mean"),
        leitos_exist_total=("leitos_exist_total", "mean"),
        dias_no_periodo=("dias_no_mes", "sum"),
        populacao=("populacao", "max"),
    ).reset_index()

    g["taxa_ocupacao_pct"] = g["dias_permanencia"] / (g["leitos_sus_total"] * g["dias_no_periodo"]) * 100
    g["media_permanencia"] = g["dias_permanencia"] / g["aih_aprovadas"]
    g["custo_medio_aih"] = g["valor_total"] / g["aih_aprovadas"]
    g["taxa_mortalidade_pct"] = g["obitos"] / g["aih_aprovadas"] * 100
    g["leitos_sus_por_mil_hab"] = g["leitos_sus_total"] / (g["populacao"] / 1000)
    g["aih_por_mil_hab"] = g["aih_aprovadas"] / (g["populacao"] / 1000)
    g["pressao_aih_por_leito"] = g["aih_aprovadas"] / g["leitos_sus_total"]
    g["pct_rede_sus"] = g["leitos_sus_total"] / g["leitos_exist_total"] * 100
    g["pct_leitos_uti"] = g["leitos_comp_sus"] / g["leitos_sus_total"] * 100
    return g.sort_values("aih_aprovadas", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------
def main():
    raw = Path(sys.argv[1] if len(sys.argv) > 1 else "raw")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "out")
    out.mkdir(parents=True, exist_ok=True)

    print("Lendo arquivos...")
    base = construir(raw)
    base = marcar_incompletas(base)
    fato = indicadores(base)

    ano_fechado = 2025
    anual = consolidar_ano(fato, ano_fechado)

    fato.to_csv(out / "fato_mensal_uf.csv", index=False, sep=";", decimal=",")
    anual.to_csv(out / f"indicadores_uf_{ano_fechado}.csv", index=False, sep=";", decimal=",")

    # --- resumo Brasil ---
    br = {
        "aih_aprovadas": anual["aih_aprovadas"].sum(),
        "dias_permanencia": anual["dias_permanencia"].sum(),
        "valor_total": anual["valor_total"].sum(),
        "obitos": anual["obitos"].sum(),
        "leitos_sus_total": anual["leitos_sus_total"].sum(),
        "leitos_exist_total": anual["leitos_exist_total"].sum(),
        "populacao": anual["populacao"].sum(),
        "dias_no_periodo": anual["dias_no_periodo"].max(),
    }
    br["taxa_ocupacao_pct"] = br["dias_permanencia"] / (br["leitos_sus_total"] * br["dias_no_periodo"]) * 100
    br["media_permanencia"] = br["dias_permanencia"] / br["aih_aprovadas"]
    br["custo_medio_aih"] = br["valor_total"] / br["aih_aprovadas"]
    br["taxa_mortalidade_pct"] = br["obitos"] / br["aih_aprovadas"] * 100
    br["leitos_sus_por_mil_hab"] = br["leitos_sus_total"] / (br["populacao"] / 1000)
    pd.DataFrame([br]).to_csv(out / f"kpis_brasil_{ano_fechado}.csv",
                              index=False, sep=";", decimal=",")

    suspeitas = fato[fato["competencia_suspeita"]][
        ["uf_nome", "competencia", "aih_aprovadas", "razao_mediana"]]
    suspeitas.to_csv(out / "competencias_suspeitas.csv", index=False, sep=";", decimal=",")

    print(f"\nArquivos gerados em {out}/")
    print(f"  fato_mensal_uf.csv            {len(fato)} linhas")
    print(f"  indicadores_uf_{ano_fechado}.csv       {len(anual)} UFs")
    print(f"  kpis_brasil_{ano_fechado}.csv")
    print(f"  competencias_suspeitas.csv    {len(suspeitas)} ocorrências")
    return fato, anual, br


if __name__ == "__main__":
    main()
