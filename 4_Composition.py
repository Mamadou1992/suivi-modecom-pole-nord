"""Composition des dechets a partir des pesees du questionnaire de caracterisation."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modecom import config  # noqa: E402
from app import entete  # noqa: E402

st.set_page_config(page_title="Composition", page_icon="♻️", layout="wide")
entete("Composition des déchets",
       "Fractions triées, en part de la masse nette de l'échantillon")

carac = st.session_state.get("carac", pd.DataFrame())
socio = st.session_state.get("socio", pd.DataFrame())
pesees = st.session_state.get("pesees")

if carac.empty or pesees is None:
    st.info("Aucune soumission de caractérisation chargée. "
            "Revenir à l'accueil pour choisir une source.")
    st.stop()

cats = pesees[~pesees["globale"]]
cols = [c for c in cats["name"] if c in carac.columns]
if not cols:
    st.warning(
        "Les colonnes de pesée du formulaire ne se retrouvent pas dans les soumissions. "
        "Vérifier que l'export provient bien du questionnaire « Caractérisation des "
        "déchets MODECOM » et qu'il n'a pas été renommé."
    )
    st.stop()

f1, f2 = st.columns(2)
communes_dispo = sorted(carac["commune"].dropna().unique())
choix = f1.multiselect("Communes", communes_dispo, default=communes_dispo)
granulos = sorted(cats["granulometrie"].unique())
gr = f2.multiselect("Granulométrie", granulos, default=granulos)

sel = carac[carac["commune"].isin(choix)]
noms = cats[cats["granulometrie"].isin(gr)]["name"]
cols_sel = [c for c in noms if c in sel.columns]

if sel.empty or not cols_sel:
    st.info("Aucune donnée pour cette sélection.")
    st.stop()

masses = sel[cols_sel].apply(pd.to_numeric, errors="coerce")
total = float(masses.sum().sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Échantillons", len(sel))
c2.metric("Masse brute cumulée", f"{sel['masse_brute'].sum():,.0f} kg".replace(",", " "))
c3.metric("Masse triée", f"{total:,.0f} kg".replace(",", " "))
if not socio.empty and "a2_present" in socio.columns:
    hab = socio[socio["commune"].isin(choix)]["a2_present"].sum()
    c4.metric("Personnes couvertes", f"{hab:,.0f}".replace(",", " "))

st.divider()

par_cat = (masses.sum().rename("kg").reset_index()
           .rename(columns={"index": "name"})
           .merge(cats[["name", "categorie", "granulometrie"]], on="name"))
agrege = (par_cat.groupby("categorie")["kg"].sum().reset_index()
          .sort_values("kg", ascending=False))
agrege["part"] = agrege["kg"] / total * 100

g, d = st.columns([3, 2])
with g:
    st.subheader("Les 15 fractions principales")
    top = agrege.head(15).sort_values("part")
    fig = px.bar(top, x="part", y="categorie", orientation="h",
                 labels={"part": "Part de la masse triée (%)", "categorie": ""},
                 text=top["part"].map(lambda v: f"{v:.1f} %"))
    fig.update_traces(marker_color=config.VERT, textposition="outside", cliponaxis=False)
    fig.update_layout(height=520, margin=dict(l=0, r=40, t=10, b=0),
                      plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")

with d:
    st.subheader("Répartition par granulométrie")
    par_gr = par_cat.groupby("granulometrie")["kg"].sum().reset_index()
    f2b = px.pie(par_gr, names="granulometrie", values="kg", hole=0.45,
                 color_discrete_sequence=["#1B7F4B", "#8DC63F", "#DCDCD4", "#F4A93B"])
    f2b.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(f2b, width="stretch")

    st.subheader("Ratio de production")
    if not socio.empty and "a2_present" in socio.columns:
        hab = socio[socio["commune"].isin(choix)]["a2_present"].sum()
        if hab > 0:
            st.metric("Masse triée par personne couverte", f"{total / hab:.2f} kg")
            st.caption(
                "Ce ratio ne vaut que si les échantillons proviennent bien des ménages "
                "enquêtés. Sans identifiant de ménage dans la fiche de caractérisation, "
                "il reste indicatif."
            )
    else:
        st.caption("Charger les fiches ménage pour obtenir un ratio par habitant.")

st.divider()
st.subheader("Comparaison entre communes")
lignes = []
for com in choix:
    s = sel[sel["commune"] == com]
    if s.empty:
        continue
    m = s[cols_sel].apply(pd.to_numeric, errors="coerce").sum()
    t = float(m.sum())
    if t <= 0:
        continue
    tmp = (m.rename("kg").reset_index().rename(columns={"index": "name"})
           .merge(cats[["name", "categorie"]], on="name")
           .groupby("categorie")["kg"].sum())
    for cat in agrege.head(8)["categorie"]:
        lignes.append({"Commune": com, "Fraction": cat,
                       "Part (%)": tmp.get(cat, 0) / t * 100})
if lignes:
    comp = pd.DataFrame(lignes)
    f3 = px.bar(comp, x="Commune", y="Part (%)", color="Fraction", barmode="stack",
                color_discrete_sequence=px.colors.sequential.Greens_r)
    f3.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0),
                     plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(f3, width="stretch")

st.divider()
st.subheader("Tableau des fractions")
tab = agrege.copy()
tab["part"] = tab["part"].round(2)
tab["kg"] = tab["kg"].round(1)
st.dataframe(tab.rename(columns={"categorie": "Fraction", "kg": "Masse (kg)",
                                 "part": "Part (%)"}),
             hide_index=True, width="stretch", height=380)
st.download_button("Télécharger la composition",
                   tab.to_csv(index=False).encode("utf-8"),
                   "composition_modecom.csv", "text/csv")
