"""Controles qualite sur les soumissions."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modecom import qualite  # noqa: E402
from app import entete  # noqa: E402

st.set_page_config(page_title="Qualité", page_icon="✅", layout="wide")
entete("Qualité des données", "Anomalies détectées sur les deux questionnaires")

socio = st.session_state.get("socio", pd.DataFrame())
carac = st.session_state.get("carac", pd.DataFrame())
pesees = st.session_state.get("pesees")

if socio.empty and carac.empty:
    st.info("Aucune soumission chargée. Revenir à l'accueil pour choisir une source.")
    st.stop()

a1 = qualite.controler_socio(socio)
a2 = qualite.controler_carac(carac, pesees)
anomalies = pd.concat([a1, a2], ignore_index=True) if len(a1) or len(a2) else pd.DataFrame()

n_soumissions = len(socio) + len(carac)
n_bloquant = int((anomalies["gravité"] == "Bloquant").sum()) if not anomalies.empty else 0
n_verifier = int((anomalies["gravité"] == "À vérifier").sum()) if not anomalies.empty else 0
n_info = int((anomalies["gravité"] == "Information").sum()) if not anomalies.empty else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Soumissions contrôlées", n_soumissions)
c2.metric("Bloquantes", n_bloquant)
c3.metric("À vérifier", n_verifier)
c4.metric("Informations", n_info)

if n_bloquant:
    st.error(f"{n_bloquant} anomalies bloquantes doivent être corrigées avant analyse.")
elif not anomalies.empty:
    st.warning("Aucune anomalie bloquante. Des points restent à vérifier.")
else:
    st.success("Aucune anomalie détectée.")

app = qualite.controler_appariement(socio, carac)
if app:
    (st.success if app["appariable"] else st.warning)(app["message"])

st.divider()

if anomalies.empty:
    st.stop()

g, d = st.columns([2, 3])
with g:
    st.subheader("Par contrôle")
    st.dataframe(
        anomalies.groupby(["gravité", "contrôle"]).size()
        .reset_index(name="Nombre").sort_values("Nombre", ascending=False),
        hide_index=True, width="stretch",
    )
with d:
    st.subheader("Par commune")
    st.dataframe(
        anomalies.groupby(["commune", "gravité"]).size().unstack(fill_value=0),
        width="stretch",
    )

st.divider()
st.subheader("Détail des anomalies")
f1, f2 = st.columns(2)
grav = f1.multiselect("Gravité", sorted(anomalies["gravité"].unique()),
                      default=sorted(anomalies["gravité"].unique()))
quest = f2.multiselect("Questionnaire", sorted(anomalies["questionnaire"].unique()),
                       default=sorted(anomalies["questionnaire"].unique()))
vue = anomalies[anomalies["gravité"].isin(grav) & anomalies["questionnaire"].isin(quest)]
st.dataframe(vue, hide_index=True, width="stretch", height=420)

st.download_button("Télécharger les anomalies",
                   vue.to_csv(index=False).encode("utf-8"),
                   "anomalies_modecom.csv", "text/csv")

with st.expander("Contrôles appliqués"):
    st.markdown("""
**Questionnaire socio-démographique**

- identifiant de ménage en doublon, un même numéro de sac ne peut pas revenir deux fois
- nombre de personnes présentes supérieur à l'effectif total du ménage
- ménage de plus de 40 personnes, à confirmer sur le terrain
- refus de participation, le sac ne doit pas être compté dans la cible atteinte
- commune hors périmètre, ou commune en prélèvement sur points de collecte où aucun
  sac n'est censé être déposé

**Questionnaire de caractérisation**

- masse après quartage supérieure à la masse brute
- masse nette supérieure à la masse après quartage
- somme des fractions triées s'écartant de plus de 5 % de la masse nette
- échantillon de moins de 100 kg
- code d'échantillon en doublon, commune hors périmètre
""")
