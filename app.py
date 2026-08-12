"""Suivi de la campagne MODECOM Pole Nord - accueil et choix de la source de donnees."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modecom import auth, config, sources, xlsform  # noqa: E402

CSS = """
<style>
  .bandeau {background:#1B5E36;color:#fff;padding:14px 20px;border-radius:6px;margin-bottom:18px}
  .bandeau h1 {margin:0;font-size:26px;font-weight:700}
  .bandeau p  {margin:4px 0 0 0;font-size:14px;opacity:.9}
  div[data-testid="stMetricValue"] {font-size:26px}
  section[data-testid="stSidebar"] img {margin-bottom:8px}
</style>
"""


def marque():
    """Affiche le logo SGP dans la barre laterale, s'il est present."""
    p = config.logo()
    if p:
        st.sidebar.image(str(p), width="stretch")
    else:
        st.sidebar.markdown(
            f"<div style='background:{config.VERT};color:#fff;padding:10px 12px;"
            "border-radius:6px;font-weight:700;letter-spacing:1px;text-align:center'>"
            "SGP</div>", unsafe_allow_html=True)
    st.sidebar.caption("Caractérisation des déchets ménagers, Pôle Nord")
    st.sidebar.divider()


def entete(titre, sous_titre):
    st.markdown(CSS, unsafe_allow_html=True)
    auth.exiger_mot_de_passe()
    marque()
    auth.bouton_deconnexion()
    p = config.logo()
    if p:
        g, d = st.columns([1, 7])
        g.image(str(p), width=110)
        with d:
            st.markdown(
                f'<div class="bandeau"><h1>{titre}</h1><p>{sous_titre}</p></div>',
                unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="bandeau"><h1>{titre}</h1><p>{sous_titre}</p></div>',
            unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def charger_formulaires():
    socio = xlsform.charger_form(config.chemin(config.FORM_SOCIO))
    carac = xlsform.charger_form(config.chemin(config.FORM_CARAC))
    return socio, carac


@st.cache_data(show_spinner=False)
def charger_communes():
    for nom in (config.FICHIER_COMMUNES, config.FICHIER_COMMUNES_SECOURS):
        p = config.chemin(nom)
        if p.exists():
            df = pd.read_excel(p, sheet_name="Communes à caractériser")
            df = df[df["Commune"].notna() & (df["Commune"] != "TOTAL / MOYENNE")]
            return df
    return pd.DataFrame()


def charge_donnees():
    """Barre laterale : choix de la source, renvoie (socio, carac) normalises."""
    st.sidebar.header("Source des données")
    mode = st.sidebar.radio(
        "Origine des soumissions",
        ["Fichiers exportés", "KoboToolbox"],
        help="La collecte se fait sur ODK/Kobo, qui fonctionne hors ligne. "
             "Cette application ne fait que lire les soumissions.",
    )

    socio_brut = carac_brut = None
    if mode == "Fichiers exportés":
        f1 = st.sidebar.file_uploader("Premier export", type=["csv", "xlsx"])
        f2 = st.sidebar.file_uploader("Second export", type=["csv", "xlsx"])
        jeux = [sources.charger_fichier(f) for f in (f1, f2) if f]
        socio_brut, carac_brut = sources.repartir(jeux)
        st.sidebar.caption("L'ordre n'a pas d'importance, chaque export est reconnu "
                           "à son contenu.")

    else:
        secrets = st.secrets.get("kobo", {}) if hasattr(st, "secrets") else {}
        url = st.sidebar.text_input("Serveur Kobo", secrets.get("url", config.KOBO_URL))
        token = st.sidebar.text_input(
            "Jeton d'API", secrets.get("token", ""), type="password",
            help="Dans Kobo : Compte, Sécurité, Jeton d'API.")
        uid1 = st.sidebar.text_input("Identifiant du premier formulaire",
                                     secrets.get("uid_1", config.KOBO_UID_1))
        uid2 = st.sidebar.text_input("Identifiant du second formulaire",
                                     secrets.get("uid_2", config.KOBO_UID_2))
        if st.sidebar.button("Récupérer les soumissions", width="stretch"):
            if not token:
                st.sidebar.error("Le jeton d'API est nécessaire.")
            else:
                try:
                    jeux = [sources.charger_kobo(url, token, u) for u in (uid1, uid2) if u]
                    socio_brut, carac_brut = sources.repartir(jeux)
                    st.session_state["socio_brut"] = socio_brut
                    st.session_state["carac_brut"] = carac_brut
                    n1 = 0 if socio_brut is None else len(socio_brut)
                    n2 = 0 if carac_brut is None else len(carac_brut)
                    st.sidebar.success(f"{n1} fiches ménage et {n2} fiches de tri récupérées.")
                except Exception as e:
                    st.sidebar.error(f"Échec de la récupération : {e}")
        socio_brut = socio_brut if socio_brut is not None else st.session_state.get("socio_brut")
        carac_brut = carac_brut if carac_brut is not None else st.session_state.get("carac_brut")

    socio = sources.normalise_socio(socio_brut)
    carac = sources.normalise_carac(carac_brut)
    st.session_state["socio"] = socio
    st.session_state["carac"] = carac
    st.session_state["mode"] = mode
    if socio.empty and carac.empty:
        st.sidebar.info("Aucune soumission chargée pour l'instant.")
    return socio, carac


def main():
    st.set_page_config(page_title="Suivi MODECOM Pôle Nord",
                       page_icon="♻️", layout="wide")
    entete("Suivi de la campagne MODECOM Pôle Nord",
           "12 communes des régions de Saint-Louis et de Matam - "
           "avancement, qualité des données et composition des déchets")

    try:
        f_socio, f_carac = charger_formulaires()
    except Exception as e:
        st.error(f"Impossible de lire les questionnaires dans {config.DATA_DIR} : {e}")
        st.stop()

    st.session_state["form_socio"] = f_socio
    st.session_state["form_carac"] = f_carac
    st.session_state["pesees"] = xlsform.table_pesees(f_carac)

    socio, carac = charge_donnees()
    pesees = st.session_state["pesees"]

    cible_totale = config.CIBLE_MENAGES * len(config.COMMUNES_SOURCE)
    recus = len(socio) if not socio.empty else 0
    tries = len(carac) if not carac.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ménages à équiper en sacs", f"{cible_totale}",
              help=f"{config.CIBLE_MENAGES} par commune sur "
                   f"{len(config.COMMUNES_SOURCE)} communes à la source")
    c2.metric("Fiches ménage reçues", f"{recus}",
              f"{recus / cible_totale * 100:.0f} % de la cible" if cible_totale else None)
    c3.metric("Échantillons triés", f"{tries}")
    c4.metric("Communes couvertes",
              f"{socio['commune'].nunique() if not socio.empty else 0} / {len(config.COMMUNES)}")

    st.divider()
    g, d = st.columns([3, 2])

    with g:
        st.subheader("Les deux questionnaires")
        r1 = xlsform.resume(f_socio)
        r2 = xlsform.resume(f_carac)
        st.dataframe(
            pd.DataFrame({
                "Questionnaire": ["Enquête socio-démographique", "Caractérisation des déchets"],
                "Questions": [r1["questions"], r2["questions"]],
                "Sections": [r1["groupes"], r2["groupes"]],
                "Listes de choix": [r1["listes"], r2["listes"]],
                "Pesées": [0, int((~pesees["globale"]).sum())],
            }),
            hide_index=True, width="stretch",
        )
        st.caption(
            "Les deux fiches sont des XLSForm. La saisie se fait dans ODK Collect ou "
            "KoboCollect, qui fonctionnent hors connexion. Cette application lit les "
            "soumissions une fois synchronisées."
        )

    with d:
        st.subheader("Point de vigilance")
        if "menage_id" in set(f_carac["questions"]["name"]):
            st.success("La fiche de caractérisation porte un identifiant de ménage : "
                       "le croisement avec le profil du ménage est possible.")
        else:
            st.warning(
                "La fiche de caractérisation ne porte aucun identifiant de ménage ni de sac. "
                "Elle s'articule autour du camion et du circuit de collecte. "
                "Le croisement entre composition des déchets et profil du ménage est donc "
                "impossible en l'état, et l'analyse restera au niveau de la commune."
            )
        saisons = xlsform.options(f_carac, "saison")
        if len(saisons) < 2:
            st.info(
                f"Le champ saison n'offre qu'une modalité : {', '.join(saisons)}. "
                "Ajouter la saison sèche avant de dupliquer le formulaire pour une "
                "seconde campagne, sinon les deux jeux seront indistinguables."
            )

    st.divider()
    st.caption(
        "Pages disponibles dans le menu de gauche : avancement par commune, carte, "
        "qualité des données, composition des déchets, structure des questionnaires."
    )


if __name__ == "__main__":
    main()
