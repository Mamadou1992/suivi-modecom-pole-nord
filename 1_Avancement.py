"""Avancement de la collecte, commune par commune."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modecom import config  # noqa: E402
from app import entete  # noqa: E402

st.set_page_config(page_title="Avancement", page_icon="📈", layout="wide")
entete("Avancement de la collecte",
       "Fiches ménage reçues et échantillons triés, par commune")

socio = st.session_state.get("socio", pd.DataFrame())
carac = st.session_state.get("carac", pd.DataFrame())

if socio.empty and carac.empty:
    st.info("Aucune soumission chargée. Revenir à l'accueil pour choisir une source.")
    st.stop()

lignes = []
for commune, info in config.COMMUNES.items():
    a_la_source = commune in config.COMMUNES_SOURCE
    recu = int((socio["commune"] == commune).sum()) if not socio.empty else 0
    trie = int((carac["commune"] == commune).sum()) if not carac.empty else 0
    cible = config.CIBLE_MENAGES if a_la_source else 0
    lignes.append({
        "Commune": commune,
        "Région": info["region"],
        "Infrastructure": info["infra"],
        "Méthode": info["methode"],
        "Cible sacs": cible,
        "Fiches reçues": recu,
        "Reste à faire": max(cible - recu, 0),
        "Avancement": (recu / cible) if cible else None,
        "Échantillons triés": trie,
    })
suivi = pd.DataFrame(lignes)

tot_cible = suivi["Cible sacs"].sum()
tot_recu = suivi.loc[suivi["Cible sacs"] > 0, "Fiches reçues"].sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Cible totale", f"{tot_cible} sacs")
c2.metric("Reçu", f"{tot_recu}", f"{tot_recu / tot_cible * 100:.0f} %" if tot_cible else None)
c3.metric("Reste à faire", f"{max(tot_cible - tot_recu, 0)}")
c4.metric("Communes à 100 %", f"{int((suivi['Avancement'] >= 1).sum())} / {len(config.COMMUNES_SOURCE)}")

st.divider()
g, d = st.columns([3, 2])

with g:
    st.subheader("Avancement par commune")
    src = suivi[suivi["Cible sacs"] > 0].sort_values("Avancement")
    fig = go.Figure()
    fig.add_bar(y=src["Commune"], x=src["Cible sacs"], orientation="h",
                marker_color="#DCDCD4", name="Cible", hoverinfo="skip")
    fig.add_bar(y=src["Commune"], x=src["Fiches reçues"], orientation="h",
                marker_color=[config.COULEURS[m] for m in src["Méthode"]],
                name="Reçu",
                hovertemplate="%{y} : %{x} fiches<extra></extra>")
    fig.add_vline(x=config.CIBLE_MENAGES, line_dash="dot", line_color="#B01B2E",
                  annotation_text=f"cible {config.CIBLE_MENAGES}",
                  annotation_position="top")
    fig.update_layout(barmode="overlay", height=420, margin=dict(l=0, r=0, t=10, b=0),
                      showlegend=False, xaxis_title="Ménages",
                      plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")

with d:
    st.subheader("Rythme de collecte")
    if not socio.empty and "date" in socio.columns and socio["date"].notna().any():
        par_jour = (socio.dropna(subset=["date"])
                    .groupby(socio["date"].dt.date).size().reset_index(name="Fiches"))
        par_jour["Cumul"] = par_jour["Fiches"].cumsum()
        f2 = px.area(par_jour, x="date", y="Cumul", markers=True)
        f2.update_traces(line_color=config.VERT, fillcolor="rgba(27,94,54,.15)")
        f2.add_hline(y=tot_cible, line_dash="dot", line_color="#B01B2E",
                     annotation_text="cible totale")
        f2.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0),
                         xaxis_title="", yaxis_title="Fiches cumulées",
                         plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(f2, width="stretch")
    else:
        st.info("Pas de date exploitable dans les soumissions.")

st.divider()
st.subheader("Tableau de suivi")
st.dataframe(
    suivi,
    hide_index=True, width="stretch",
    column_config={
        "Avancement": st.column_config.ProgressColumn(
            "Avancement", format="%.0f %%", min_value=0, max_value=1),
        "Cible sacs": st.column_config.NumberColumn(
            "Cible sacs", help="0 pour les communes en prélèvement sur points de collecte"),
    },
)
st.caption(
    "Les quatre communes en prélèvement sur points de collecte, Dagana, Bokhol, Ndioum "
    "et Ranérou, n'ont pas de cible en sacs : l'échantillon y est prélevé directement "
    "sur les bennes et les points de dépôt."
)

st.download_button("Télécharger le tableau de suivi",
                   suivi.to_csv(index=False).encode("utf-8"),
                   "suivi_avancement.csv", "text/csv")
