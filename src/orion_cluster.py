#!/usr/bin/env python3
"""
ÓRION — Clusterização de perfis de pressão hospitalar

Agrupa as UFs por padrão de pressão hospitalar a partir do consolidado anual
gerado pelo orion_etl.py. Usa KMeans sobre features padronizadas e valida a
escolha de k por silhouette.

Uso:  python orion_cluster.py <indicadores_uf_2025.csv> <pasta_saida> [k]

Saídas:
  clusters_uf.csv        UFs com cluster atribuído e as features usadas
  perfis_cluster.csv     média de cada feature por cluster
  silhouette_por_k.csv   score para k de 2 a 6, evidência da escolha
"""

import sys
from pathlib import Path

import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Features do agrupamento.
#
# A taxa de ocupação foi deliberadamente deixada de fora: ela correlaciona
# +0,70 com pressao_aih_por_leito e +0,71 com pct_leitos_uti, e entraria como
# informação repetida, dando peso duplo à mesma dimensão. Ela é tratada como
# resultado que os clusters explicam, não como insumo do modelo.
FEATURES = [
    "pressao_aih_por_leito",    # AIHs por leito no ano — giro da rede
    "media_permanencia",        # dias por internação — velocidade de saída
    "leitos_sus_por_mil_hab",   # oferta de leitos por habitante
    "pct_leitos_uti",           # participação da UTI — proxy de complexidade
]

K_TESTADOS = range(2, 7)
RANDOM_STATE = 42
N_INIT = 50


def carregar(caminho: Path) -> pd.DataFrame:
    """
    Lê o consolidado do ETL. O arquivo sai com separador ';' e decimal ','.
    Algumas leituras trazem os números como texto — a conversão explícita
    abaixo cobre os dois casos.
    """
    df = pd.read_csv(caminho, sep=";", decimal=",")
    for col in FEATURES + ["taxa_ocupacao_pct", "custo_medio_aih"]:
        if df[col].dtype == object:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "."), errors="coerce")
    return df


def avaliar_k(X) -> pd.DataFrame:
    """Silhouette para cada k testado. É a evidência da escolha do número de grupos."""
    linhas = []
    for k in K_TESTADOS:
        rotulos = KMeans(n_clusters=k, n_init=N_INIT,
                         random_state=RANDOM_STATE).fit_predict(X)
        linhas.append({"k": k, "silhouette": silhouette_score(X, rotulos)})
    return pd.DataFrame(linhas)


def nomear(medias: pd.DataFrame) -> dict:
    """
    Nomeia os clusters pelas características das features, não pelo número que
    o sklearn atribuiu — os rótulos do KMeans mudam entre execuções e não
    significam nada por si.

    A regra: o de maior pressão é 'Alta pressão'; entre os restantes, o de
    maior permanência é 'Baixa rotatividade'; o último é 'Rede folgada'.
    """
    c_pressao = medias["pressao_aih_por_leito"].idxmax()
    restantes = [c for c in medias.index if c != c_pressao]
    c_permanencia = medias.loc[restantes, "media_permanencia"].idxmax()
    c_folga = [c for c in restantes if c != c_permanencia][0]
    return {c_pressao: "Alta pressão",
            c_permanencia: "Baixa rotatividade",
            c_folga: "Rede folgada"}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    entrada = Path(sys.argv[1])
    saida = Path(sys.argv[2] if len(sys.argv) > 2 else "out")
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    saida.mkdir(parents=True, exist_ok=True)

    df = carregar(entrada)
    print(f"Lidas {len(df)} UFs de {entrada.name}")

    X = StandardScaler().fit_transform(df[FEATURES])

    scores = avaliar_k(X)
    print("\nSilhouette por k:")
    for _, r in scores.iterrows():
        marca = "  <- escolhido" if int(r["k"]) == k else ""
        print(f"  k={int(r['k'])}   {r['silhouette']:.3f}{marca}")

    modelo = KMeans(n_clusters=k, n_init=N_INIT, random_state=RANDOM_STATE).fit(X)
    df["cluster"] = modelo.labels_

    medias = df.groupby("cluster")[FEATURES].mean()
    nomes = nomear(medias) if k == 3 else {c: f"Cluster {c}" for c in medias.index}
    df["cluster_nome"] = df["cluster"].map(nomes)

    perfis = df.groupby("cluster_nome").agg(
        ufs=("uf_nome", "count"),
        pressao_aih_por_leito=("pressao_aih_por_leito", "mean"),
        media_permanencia=("media_permanencia", "mean"),
        leitos_sus_por_mil_hab=("leitos_sus_por_mil_hab", "mean"),
        pct_leitos_uti=("pct_leitos_uti", "mean"),
        taxa_ocupacao_pct=("taxa_ocupacao_pct", "mean"),
        custo_medio_aih=("custo_medio_aih", "mean"),
    ).round(2).reset_index()

    print("\nPerfis encontrados:")
    for _, r in perfis.iterrows():
        ufs = sorted(df[df.cluster_nome == r["cluster_nome"]]["uf_nome"])
        print(f"  {r['cluster_nome']} ({int(r['ufs'])} UFs): {', '.join(ufs)}")

    cols = ["uf_cod", "uf_nome", "cluster", "cluster_nome"] + FEATURES + \
           ["taxa_ocupacao_pct", "custo_medio_aih"]
    df[cols].sort_values(["cluster_nome", "uf_nome"]).to_csv(
        saida / "clusters_uf.csv", index=False, sep=";", decimal=",")
    perfis.to_csv(saida / "perfis_cluster.csv", index=False, sep=";", decimal=",")
    scores.to_csv(saida / "silhouette_por_k.csv", index=False, sep=";", decimal=",")

    print(f"\nArquivos gerados em {saida}/")
    print(f"  clusters_uf.csv        {len(df)} UFs")
    print(f"  perfis_cluster.csv     {len(perfis)} clusters")
    print(f"  silhouette_por_k.csv   k de {min(K_TESTADOS)} a {max(K_TESTADOS)}")


if __name__ == "__main__":
    main()
