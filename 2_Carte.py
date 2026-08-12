"""Carte de l'avancement, appuyee sur le GeoPackage du projet."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modecom import config  # noqa: E402
from app import entete  # noqa: E402

st.set_page_config(page_title="Carte", page_icon="🗺️", layout="wide")
entete("Carte de l'avancement", "Communes, sites de tri et taux de couverture")

socio = st.session_state.get("socio", pd.DataFrame())


@st.cache_data(show_spinner=False)
def charger_couches():
    import geopandas as gpd
    p = config.chemin(config.FICHIER_GPKG)
    communes = gpd.read_file(p, layer="communes")
    try:
        sites = gpd.read_file(p, layer="sites")
    except Exception:
        sites = None
    return communes, sites


try:
    communes, sites = charger_couches()
except Exception as e:
    st.error(f"Le fond de carte est introuvable ou illisible : {e}")
    st.caption(f"Fichier attendu : {config.chemin(config.FICHIER_GPKG)}")
    st.stop()

recus = (socio.groupby("commune").size() if not socio.empty
         else pd.Series(dtype=int))
communes["recus"] = communes["commune"].map(recus).fillna(0).astype(int)
communes["cible"] = communes["commune"].apply(
    lambda c: config.CIBLE_MENAGES if c in config.COMMUNES_SOURCE else 0)
communes["avancement"] = [
    (r / c * 100) if c else float("nan")
    for r, c in zip(communes["recus"], communes["cible"])
]

variable = st.radio("Variable cartographiée", ["Avancement", "Méthode", "Population 2023"],
                    horizontal=True)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe

    com = communes.to_crs(3857)
    fig, ax = plt.subplots(figsize=(13, 7.2), dpi=140)
    ax.set_facecolor("#F7F7F4")

    if variable == "Méthode":
        for m, c in config.COULEURS.items():
            s = com[com["methode"] == m]
            if len(s):
                s.plot(ax=ax, facecolor=c, edgecolor="white", lw=1.0)
    elif variable == "Population 2023":
        com.plot(ax=ax, column="pop_2023", cmap="YlGn", edgecolor="white", lw=0.8,
                 legend=True, legend_kwds={"label": "Habitants (RGPH-5, 2023)",
                                           "shrink": 0.6})
    else:
        av = com.copy()
        av["avancement"] = av["avancement"].fillna(-1)
        hors = av[av["avancement"] < 0]
        dans = av[av["avancement"] >= 0]
        if len(hors):
            hors.plot(ax=ax, facecolor="#E4E4DC", edgecolor="white", lw=0.8,
                      hatch="///")
        if len(dans):
            dans.plot(ax=ax, column="avancement", cmap="RdYlGn", vmin=0, vmax=100,
                      edgecolor="white", lw=0.8, legend=True,
                      legend_kwds={"label": "Avancement (%)", "shrink": 0.6})

    if sites is not None:
        s3 = sites.to_crs(3857)
        for _, r in s3.iterrows():
            source = str(r["methode"]).startswith("MODECOM")
            ax.plot(r.geometry.x, r.geometry.y,
                    marker="*" if source else "o",
                    ms=18 if source else 9,
                    mfc=config.COULEURS.get(r["methode"], "#888"),
                    mec="#1a1a1a", mew=1.0, zorder=6)

    for _, r in com.iterrows():
        p = r.geometry.representative_point()
        etiq = r["commune"]
        if variable == "Avancement" and r["cible"]:
            etiq += f"\n{r['recus']}/{r['cible']}"
        ax.annotate(etiq, (p.x, p.y), ha="center", va="center", fontsize=7.5,
                    fontweight="bold", color="#1a1a1a", zorder=8,
                    path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])

    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor("#1a1a1a")
    fig.tight_layout()
    st.pyplot(fig, width="stretch")
except Exception as e:
    st.error(f"Rendu de la carte impossible : {e}")

if variable == "Avancement":
    st.caption("Les communes hachurées sont en prélèvement sur points de collecte : "
               "elles n'ont pas de cible en sacs, donc pas de taux d'avancement.")

st.divider()
st.subheader("Détail par commune")
cols = ["commune", "region", "departement", "methode", "logist_cat",
        "pop_2023", "menages", "recus", "cible", "avancement"]
cols = [c for c in cols if c in communes.columns]
st.dataframe(
    communes[cols].sort_values("commune"),
    hide_index=True, width="stretch",
    column_config={"avancement": st.column_config.NumberColumn("avancement", format="%.0f %%")},
)
