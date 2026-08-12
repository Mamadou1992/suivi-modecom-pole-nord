"""Exploration de la structure des deux XLSForm."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modecom import xlsform  # noqa: E402
from app import entete  # noqa: E402

st.set_page_config(page_title="Questionnaires", page_icon="📋", layout="wide")
entete("Structure des questionnaires",
       "Sections, questions et listes de choix des deux fiches XLSForm")

f_socio = st.session_state.get("form_socio")
f_carac = st.session_state.get("form_carac")
if f_socio is None or f_carac is None:
    st.info("Revenir à l'accueil pour charger les questionnaires.")
    st.stop()

onglet = st.radio("Questionnaire",
                  ["Enquête socio-démographique", "Caractérisation des déchets"],
                  horizontal=True)
form = f_socio if onglet.startswith("Enquête") else f_carac
r = xlsform.resume(form)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Questions", r["questions"])
c2.metric("Sections", r["groupes"])
c3.metric("Listes de choix", r["listes"])
c4.metric("Champs numériques",
          r["types"].get("decimal", 0) + r["types"].get("integer", 0))

st.divider()
g, d = st.columns([3, 2])

with g:
    st.subheader("Questions par section")
    q = form["questions"]
    par_sec = q.groupby("groupe").size().reset_index(name="Questions")
    st.dataframe(par_sec, hide_index=True, width="stretch")

    st.subheader("Détail")
    sections = ["Toutes"] + list(par_sec["groupe"])
    sec = st.selectbox("Section", sections)
    vue = q if sec == "Toutes" else q[q["groupe"] == sec]
    st.dataframe(vue[["groupe", "type", "name", "label"]],
                 hide_index=True, width="stretch", height=420)

with d:
    st.subheader("Types de questions")
    st.dataframe(
        pd.Series(r["types"]).rename("Nombre").reset_index()
        .rename(columns={"index": "Type"}).sort_values("Nombre", ascending=False),
        hide_index=True, width="stretch",
    )

    st.subheader("Listes de choix")
    lc = form["col_liste"]
    listes = sorted(form["choices"][lc].dropna().astype(str).unique())
    liste = st.selectbox("Liste", listes)
    opts = xlsform.options(form, liste)
    st.write(f"{len(opts)} modalités")
    st.dataframe(pd.DataFrame({"Modalité": opts}), hide_index=True,
                 width="stretch", height=260)

if not onglet.startswith("Enquête"):
    st.divider()
    st.subheader("Grille de pesée")
    p = st.session_state.get("pesees")
    if p is not None:
        cats = p[~p["globale"]]
        st.write(f"{cats['categorie'].nunique()} sous-catégories déclinées en "
                 f"{cats['granulometrie'].nunique()} granulométries, "
                 f"soit {len(cats)} pesées, plus {int(p['globale'].sum())} masses globales.")
        st.dataframe(
            cats.pivot_table(index="categorie", columns="granulometrie",
                             values="name", aggfunc="first").notna()
            .replace({True: "oui", False: ""}),
            width="stretch", height=420,
        )

st.divider()
with st.expander("Rappel sur le rôle de cette application"):
    st.markdown("""
La collecte se fait dans **ODK Collect** ou **KoboCollect**, sur le terrain, hors connexion.
C'est indispensable en zone rurale à Fanaye, Ogo ou Bokidiawé, où le réseau n'est pas garanti.

Cette application ne saisit rien. Elle lit les soumissions une fois synchronisées, par
l'API KoboToolbox ou par import d'un export CSV, et sert au suivi, au contrôle qualité
et à l'analyse.
""")
