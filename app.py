"""Suivi de la campagne MODECOM Pole Nord - version en un seul fichier.

Tout est regroupe ici : configuration, lecture des XLSForm, sources de donnees,
controles qualite et les cinq vues, presentees en onglets.

Aucun dossier n'est necessaire pour demarrer. Les fichiers de donnees sont
cherches dans `donnees/` puis a la racine ; s'ils manquent, l'application
s'ouvre quand meme et signale ce qui est indisponible.
"""
import hashlib
import io
import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Suivi MODECOM Pôle Nord", page_icon="♻️", layout="wide")

# =====================================================================
# CONFIGURATION
# =====================================================================
RACINE = Path(__file__).resolve().parent
DOSSIERS_DONNEES = [RACINE / "donnees", RACINE]

FORM_SOCIO = "Enquête socio-démographique  MODECOM Pôle Nord.xlsx"
FORM_CARAC = "Caractérisation des déchets MODECOM_v2.xlsx"
FICHIER_GPKG = "Caracterisation_communes.gpkg"

KOBO_URL = "https://kf.kobotoolbox.org"
KOBO_UID_1 = "a6g6VnmqYqVBf33QhXUVe3"
KOBO_UID_2 = "aG2BGSMEib9xWfRzoeXcXm"

CV_HYPOTHESE = 0.40
MARGE_CIBLE = 0.10
CIBLE_MENAGES = 62

COMMUNES = {
    "Dagana":       {"infra": "CTT Dagana",  "region": "Saint-Louis", "methode": "Sur sites de collecte"},
    "Richard Toll": {"infra": "CTT Dagana",  "region": "Saint-Louis", "methode": "MODECOM à la source"},
    "Bokhol":       {"infra": "CIVD Bokhol", "region": "Saint-Louis", "methode": "Sur sites de collecte"},
    "Fanaye":       {"infra": "CIVD Bokhol", "region": "Saint-Louis", "methode": "MODECOM à la source"},
    "Ndioum":       {"infra": "CIVD Ndioum", "region": "Saint-Louis", "methode": "Sur sites de collecte"},
    "Podor":        {"infra": "CIVD Ndioum", "region": "Saint-Louis", "methode": "MODECOM à la source"},
    "Golléré":      {"infra": "CIVD Ndioum", "region": "Saint-Louis", "methode": "MODECOM à la source"},
    "Ogo":          {"infra": "CIVD Ogo",    "region": "Matam",       "methode": "MODECOM adapté agro-pastoral"},
    "Matam":        {"infra": "CIVD Ogo",    "region": "Matam",       "methode": "MODECOM à la source"},
    "Ourossogui":   {"infra": "CIVD Ogo",    "region": "Matam",       "methode": "MODECOM à la source"},
    "Bokidiawé":    {"infra": "CIVD Ogo",    "region": "Matam",       "methode": "MODECOM adapté agro-pastoral"},
    "Ranérou":      {"infra": "CET Ranérou", "region": "Matam",       "methode": "Sur sites régime allégé"},
}
COMMUNES_SOURCE = [c for c, v in COMMUNES.items() if v["methode"].startswith("MODECOM")]
COMMUNES_SITE = [c for c, v in COMMUNES.items() if not v["methode"].startswith("MODECOM")]

COULEURS = {
    "MODECOM à la source": "#1B7F4B",
    "MODECOM adapté agro-pastoral": "#8DC63F",
    "Sur sites de collecte": "#F4A93B",
    "Sur sites régime allégé": "#B01B2E",
}
VERT = "#1B5E36"
ENCRE = "#1a1a1a"

NOMS_LOGO = ["logo_sgp.png", "logo_sgp.jpg", "logo_sgp.jpeg", "logo_SGP.png",
             "logo_SGP.jpg", "logo_SGP.jpeg"]


def chemin(nom):
    for d in DOSSIERS_DONNEES:
        p = d / nom
        if p.exists():
            return p
    return None


def logo():
    for d in [RACINE / "assets", RACINE]:
        for n in NOMS_LOGO:
            p = d / n
            if p.exists():
                return p
    return None


# =====================================================================
# ACCES PAR MOT DE PASSE
# =====================================================================
CLE_AUTH = "authentifie"


def _empreinte(t):
    return hashlib.sha256(str(t).encode("utf-8")).hexdigest()


def _attendue():
    try:
        app = st.secrets.get("app", {})
    except Exception:
        return None
    if app.get("empreinte_mot_de_passe"):
        return str(app["empreinte_mot_de_passe"]).strip().lower()
    if app.get("mot_de_passe"):
        return _empreinte(app["mot_de_passe"])
    return None


def bandeau(titre, sous_titre):
    st.markdown(
        f"<div style='background:{VERT};color:#fff;padding:14px 20px;border-radius:6px;"
        f"margin-bottom:18px'><h1 style='margin:0;font-size:26px'>{titre}</h1>"
        f"<p style='margin:4px 0 0 0;font-size:14px;opacity:.9'>{sous_titre}</p></div>",
        unsafe_allow_html=True)


def exiger_mot_de_passe():
    if st.session_state.get(CLE_AUTH):
        return True
    attendue = _attendue()
    if attendue is None:
        bandeau("Suivi MODECOM Pôle Nord", "Accès réservé à l'équipe du projet")
        st.error("Aucun mot de passe n'est configuré. Ajouter dans les secrets :\n\n"
                 "```toml\n[app]\nmot_de_passe = \"votre_mot_de_passe\"\n```")
        st.stop()
    bandeau("Suivi MODECOM Pôle Nord", "Accès réservé à l'équipe du projet")
    with st.form("connexion"):
        saisi = st.text_input("Mot de passe", type="password")
        valider = st.form_submit_button("Entrer")
    if valider:
        if _empreinte(saisi) == attendue:
            st.session_state[CLE_AUTH] = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")
    st.caption("Les données d'enquête portent sur des ménages identifiés. "
               "Ne pas diffuser le mot de passe hors de l'équipe.")
    st.stop()


# =====================================================================
# LECTURE DES XLSFORM
# =====================================================================
LABEL = "label::Français (fr)"
META = {"start", "end", "today", "deviceid", "note", "begin_group", "end_group",
        "begin_repeat", "end_repeat", "nan"}
GRANULOS = ["hétéroclites", "grossiers", "moyens"]
MASSES_GLOBALES = ["masse totale brute", "masse après quartage", "masse nette totale"]


@st.cache_data(show_spinner=False)
def charger_form(chemin_fichier):
    survey = pd.read_excel(chemin_fichier, sheet_name="survey")
    choices = pd.read_excel(chemin_fichier, sheet_name="choices")
    survey.columns = [str(c).strip() for c in survey.columns]
    choices.columns = [str(c).strip() for c in choices.columns]
    survey["type"] = survey["type"].astype(str).str.strip()
    survey["name"] = survey["name"].astype(str).str.strip()
    if LABEL not in survey.columns:
        cand = [c for c in survey.columns if c.startswith("label")]
        survey[LABEL] = survey[cand[0]] if cand else ""
    groupes, courant, lignes = [], None, []
    for _, r in survey.iterrows():
        t = r["type"]
        if t == "begin_group":
            courant = str(r[LABEL])
            groupes.append({"name": r["name"], "label": courant})
            continue
        if t == "end_group":
            courant = None
            continue
        base = t.split()[0] if t and t != "nan" else t
        if base in META:
            continue
        lignes.append({"groupe": courant or "(hors groupe)", "type": t, "type_base": base,
                       "name": r["name"], "label": str(r[LABEL])})
    return {"survey": survey, "choices": choices, "groupes": groupes,
            "questions": pd.DataFrame(lignes), "col_liste": choices.columns[0]}


def options(form, liste):
    ch = form["choices"]
    col = form["col_liste"]
    lab = LABEL if LABEL in ch.columns else ch.columns[2]
    sub = ch[ch[col].astype(str).str.strip() == str(liste)]
    return [str(x).strip() for x in sub[lab].dropna().tolist()]


def decoupe_categorie(label):
    txt = re.sub(r"^\s*Masse\s*\(\s*Kg\s*\)?\s*", "", str(label)).strip()
    txt = re.sub(r"^\s*Masse\s*\(\s*Kg\s*", "", txt).strip()
    bas = txt.lower()
    for g in GRANULOS:
        if bas.endswith(g):
            return txt[: -len(g)].strip(), g
    return txt, "global"


def table_pesees(form):
    q = form["questions"]
    d = q[q["type_base"] == "decimal"].copy()
    dec = d["label"].apply(decoupe_categorie)
    d["categorie"] = [x[0] for x in dec]
    d["granulometrie"] = [x[1] for x in dec]
    d["globale"] = d["categorie"].str.lower().isin(MASSES_GLOBALES)
    return d.reset_index(drop=True)


def resume(form):
    q = form["questions"]
    return {"questions": len(q), "groupes": len(form["groupes"]),
            "listes": form["choices"][form["col_liste"]].nunique(),
            "types": q["type_base"].value_counts().to_dict()}


# =====================================================================
# SOURCES DE DONNEES
# =====================================================================
def sans_accent(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))


def rapproche_commune(v):
    if pd.isna(v):
        return None
    x = sans_accent(v).strip().lower().replace("_", " ").replace("-", " ")
    for off in COMMUNES:
        if sans_accent(off).lower().replace("-", " ") == x:
            return off
    return str(v).strip()


def charger_kobo(base_url, token, uid, timeout=60):
    import requests
    url = f"{base_url.rstrip('/')}/api/v2/assets/{uid}/data.json"
    entetes = {"Authorization": f"Token {token}"}
    lignes, page = [], url
    while page:
        r = requests.get(page, headers=entetes, timeout=timeout)
        r.raise_for_status()
        js = r.json()
        lignes.extend(js.get("results", []))
        page = js.get("next")
    return pd.json_normalize(lignes)


def charger_fichier(f):
    nom = getattr(f, "name", str(f)).lower()
    if nom.endswith((".xlsx", ".xls")):
        return pd.read_excel(f)
    donnees = f.read() if hasattr(f, "read") else open(f, "rb").read()
    for sep in (";", ",", "\t"):
        try:
            df = pd.read_csv(io.BytesIO(donnees), sep=sep)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    return pd.read_csv(io.BytesIO(donnees))


SIGNES_SOCIO = {"menage_id", "a1_total", "a2_present", "consentement", "strate"}
SIGNES_CARAC = {"masse_totale_brute", "masse_apres_quartage", "masse_nette_totale",
                "code_echantillon", "Infrastructure_concern_e"}


def identifier_formulaire(df):
    if df is None or getattr(df, "empty", True):
        return None
    cols = {str(c).split("/")[-1] for c in df.columns}
    ns, nc = len(cols & SIGNES_SOCIO), len(cols & SIGNES_CARAC)
    return "carac" if nc > ns else ("socio" if ns > nc else None)


def repartir(jeux):
    socio = carac = None
    restants = []
    for df in jeux:
        g = identifier_formulaire(df)
        if g == "socio" and socio is None:
            socio = df
        elif g == "carac" and carac is None:
            carac = df
        elif df is not None:
            restants.append(df)
    for df in restants:
        if socio is None:
            socio = df
        elif carac is None:
            carac = df
    return socio, carac


COLS_SOCIO = {
    "menage_id": ["menage_id"], "commune": ["commune"], "region": ["region"],
    "quartier": ["quartier"], "strate": ["strate"], "milieu": ["milieu"],
    "enqueteur": ["enqueteur"], "superviseur": ["superviseur"],
    "consentement": ["consentement"], "a1_total": ["a1_total"],
    "a2_present": ["a2_present"], "gps": ["gps"],
    "date": ["today", "date", "_submission_time", "end"],
}
COLS_CARAC = {
    "code_echantillon": ["code_echantillon"], "superviseur": ["superviseur"],
    "region": ["region"], "infrastructure": ["Infrastructure_concern_e"],
    "type_site": ["type_site"], "nom_site": ["Nom_du_site"],
    "niveau_vie": ["niveau_vie"], "type_dechet": ["type_dechet"],
    "methode": ["methode"], "saison": ["saison"],
    "masse_brute": ["masse_totale_brute"], "masse_quartage": ["masse_apres_quartage"],
    "masse_nette": ["masse_nette_totale"],
    "date": ["date_collecte", "_submission_time"],
}
CHAMPS_COMMUNE_CARAC = ["Commune_Dagana", "Commune_Bokhol", "Commune_Ndioum",
                        "Commune_OGO", "Commune_Ran_rou"]


def _renomme(df, corr):
    ren = {}
    for cible, cands in corr.items():
        for c in cands:
            if c in df.columns:
                ren[c] = cible
                break
    return df.rename(columns=ren)


def normalise_socio(df):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [str(c).split("/")[-1] for c in df.columns]
    df = _renomme(df, COLS_SOCIO)
    if "commune" in df:
        df["commune"] = df["commune"].map(rapproche_commune)
    for c in ("a1_total", "a2_present"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "date" in df:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def normalise_carac(df):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [str(c).split("/")[-1] for c in df.columns]
    df = _renomme(df, COLS_CARAC)
    presents = [c for c in CHAMPS_COMMUNE_CARAC if c in df.columns]
    if presents:
        df["commune"] = df[presents].bfill(axis=1).iloc[:, 0]
    if "commune" in df:
        df["commune"] = df["commune"].map(rapproche_commune)
    for c in ("masse_brute", "masse_quartage", "masse_nette"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "date" in df:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


# =====================================================================
# CONTROLES QUALITE
# =====================================================================
def _ajoute(a, gravite, quest, controle, sous, cle, detail):
    for _, r in sous.iterrows():
        a.append({"gravité": gravite, "questionnaire": quest, "contrôle": controle,
                  "identifiant": r.get(cle, ""), "commune": r.get("commune", ""),
                  "détail": detail(r) if callable(detail) else detail})


def controler_socio(df):
    a = []
    if df is None or df.empty:
        return pd.DataFrame(a)
    Q = "Socio-démographique"
    if "menage_id" in df:
        dup = df[df.duplicated("menage_id", keep=False) & df["menage_id"].notna()]
        _ajoute(a, "Bloquant", Q, "Identifiant de ménage en doublon", dup, "menage_id",
                "Le même numéro de sac apparaît plusieurs fois")
    if {"a1_total", "a2_present"} <= set(df.columns):
        _ajoute(a, "Bloquant", Q, "Présents supérieurs à l'effectif",
                df[df["a2_present"] > df["a1_total"]], "menage_id",
                lambda r: f"{r['a2_present']:.0f} présents pour {r['a1_total']:.0f} résidents")
        _ajoute(a, "À vérifier", Q, "Ménage de taille inhabituelle",
                df[df["a1_total"] > 40], "menage_id",
                lambda r: f"{r['a1_total']:.0f} personnes déclarées")
    if "consentement" in df:
        _ajoute(a, "Information", Q, "Refus de participation",
                df[df["consentement"].astype(str).str.lower().str.startswith("non")],
                "menage_id", "Le ménage a refusé, le sac ne doit pas être compté")
    if "commune" in df:
        _ajoute(a, "Bloquant", Q, "Commune hors périmètre",
                df[~df["commune"].isin(COMMUNES)], "menage_id",
                lambda r: f"Commune non reconnue : {r['commune']}")
        _ajoute(a, "À vérifier", Q, "Commune sans dépôt de sacs",
                df[df["commune"].isin(COMMUNES_SITE)], "menage_id",
                lambda r: f"{r['commune']} est en prélèvement sur points de collecte")
    return pd.DataFrame(a)


def controler_carac(df, pesees=None):
    a = []
    if df is None or df.empty:
        return pd.DataFrame(a)
    Q = "Caractérisation"
    if {"masse_brute", "masse_quartage"} <= set(df.columns):
        _ajoute(a, "Bloquant", Q, "Masse après quartage supérieure à la brute",
                df[df["masse_quartage"] > df["masse_brute"]], "code_echantillon",
                lambda r: f"{r['masse_quartage']:.1f} kg contre {r['masse_brute']:.1f} kg")
    if {"masse_nette", "masse_quartage"} <= set(df.columns):
        _ajoute(a, "Bloquant", Q, "Masse nette supérieure au quartage",
                df[df["masse_nette"] > df["masse_quartage"] * 1.001], "code_echantillon",
                lambda r: f"{r['masse_nette']:.1f} kg contre {r['masse_quartage']:.1f} kg")
    if pesees is not None and "masse_nette" in df:
        cols = [c for c in pesees[~pesees["globale"]]["name"] if c in df.columns]
        if cols:
            somme = df[cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
            ecart = (somme - df["masse_nette"]) / df["masse_nette"].replace(0, pd.NA)
            _ajoute(a, "Bloquant", Q, "Somme des fractions hors tolérance",
                    df[ecart.abs() > 0.05].assign(_ecart=ecart), "code_echantillon",
                    lambda r: f"écart de {r['_ecart'] * 100:+.1f} % avec la masse nette")
    if "masse_brute" in df:
        _ajoute(a, "À vérifier", Q, "Échantillon de faible masse",
                df[df["masse_brute"] < 100], "code_echantillon",
                lambda r: f"{r['masse_brute']:.1f} kg, en dessous du seuil de 100 kg")
    if "commune" in df:
        _ajoute(a, "Bloquant", Q, "Commune hors périmètre",
                df[~df["commune"].isin(COMMUNES)], "code_echantillon",
                lambda r: f"Commune non reconnue : {r['commune']}")
    if "code_echantillon" in df:
        dup = df[df.duplicated("code_echantillon", keep=False) & df["code_echantillon"].notna()]
        _ajoute(a, "Bloquant", Q, "Code d'échantillon en doublon", dup,
                "code_echantillon", "Le même code apparaît plusieurs fois")
    return pd.DataFrame(a)


# =====================================================================
# INTERFACE
# =====================================================================
exiger_mot_de_passe()

p_logo = logo()
if p_logo:
    st.sidebar.image(str(p_logo), width="stretch")
else:
    st.sidebar.markdown(
        f"<div style='background:{VERT};color:#fff;padding:10px 12px;border-radius:6px;"
        "font-weight:700;letter-spacing:1px;text-align:center'>SGP</div>",
        unsafe_allow_html=True)
st.sidebar.caption("Caractérisation des déchets ménagers, Pôle Nord")
if st.sidebar.button("Se déconnecter", width="stretch"):
    st.session_state[CLE_AUTH] = False
    st.rerun()
st.sidebar.divider()

bandeau("Suivi de la campagne MODECOM Pôle Nord",
        "12 communes des régions de Saint-Louis et de Matam - avancement, "
        "qualité des données et composition des déchets")

# --- questionnaires, facultatifs au demarrage
f_socio = f_carac = pesees = None
p1, p2 = chemin(FORM_SOCIO), chemin(FORM_CARAC)
manquants = [n for n, p in [(FORM_SOCIO, p1), (FORM_CARAC, p2)] if p is None]
if p1:
    try:
        f_socio = charger_form(p1)
    except Exception as e:
        st.warning(f"Lecture du questionnaire socio-démographique impossible : {e}")
if p2:
    try:
        f_carac = charger_form(p2)
        pesees = table_pesees(f_carac)
    except Exception as e:
        st.warning(f"Lecture du questionnaire de caractérisation impossible : {e}")
if manquants:
    st.info("Fichiers absents du dépôt : " + ", ".join(f"`{m}`" for m in manquants) +
            ". Les déposer dans un dossier `donnees` pour activer les pesées et la "
            "structure des questionnaires. Le reste fonctionne sans eux.")

# --- source des donnees
st.sidebar.header("Source des données")
mode = st.sidebar.radio("Origine des soumissions", ["Fichiers exportés", "KoboToolbox"])
socio_brut = carac_brut = None

if mode == "Fichiers exportés":
    f1 = st.sidebar.file_uploader("Premier export", type=["csv", "xlsx"])
    f2 = st.sidebar.file_uploader("Second export", type=["csv", "xlsx"])
    socio_brut, carac_brut = repartir([charger_fichier(f) for f in (f1, f2) if f])
    st.sidebar.caption("L'ordre n'a pas d'importance, chaque export est reconnu "
                       "à son contenu.")
else:
    try:
        sec = st.secrets.get("kobo", {})
    except Exception:
        sec = {}
    url = st.sidebar.text_input("Serveur Kobo", sec.get("url", KOBO_URL))
    token = st.sidebar.text_input("Jeton d'API", sec.get("token", ""), type="password")
    uid1 = st.sidebar.text_input("Identifiant du premier formulaire",
                                 sec.get("uid_1", KOBO_UID_1))
    uid2 = st.sidebar.text_input("Identifiant du second formulaire",
                                 sec.get("uid_2", KOBO_UID_2))
    if st.sidebar.button("Récupérer les soumissions", width="stretch"):
        if not token:
            st.sidebar.error("Le jeton d'API est nécessaire.")
        else:
            try:
                jeux = [charger_kobo(url, token, u) for u in (uid1, uid2) if u]
                socio_brut, carac_brut = repartir(jeux)
                st.session_state["socio_brut"] = socio_brut
                st.session_state["carac_brut"] = carac_brut
                st.sidebar.success(
                    f"{0 if socio_brut is None else len(socio_brut)} fiches ménage et "
                    f"{0 if carac_brut is None else len(carac_brut)} fiches de tri récupérées.")
            except Exception as e:
                st.sidebar.error(f"Échec de la récupération : {e}")
    socio_brut = socio_brut if socio_brut is not None else st.session_state.get("socio_brut")
    carac_brut = carac_brut if carac_brut is not None else st.session_state.get("carac_brut")

socio = normalise_socio(socio_brut)
carac = normalise_carac(carac_brut)
if socio.empty and carac.empty:
    st.sidebar.info("Aucune soumission chargée pour l'instant.")

# --- indicateurs generaux
cible_totale = CIBLE_MENAGES * len(COMMUNES_SOURCE)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ménages à équiper en sacs", f"{cible_totale}",
          help=f"{CIBLE_MENAGES} par commune sur {len(COMMUNES_SOURCE)} communes à la source")
c2.metric("Fiches ménage reçues", f"{len(socio)}",
          f"{len(socio) / cible_totale * 100:.0f} % de la cible")
c3.metric("Échantillons triés", f"{len(carac)}")
c4.metric("Communes couvertes",
          f"{socio['commune'].nunique() if not socio.empty else 0} / {len(COMMUNES)}")
st.divider()

onglets = st.tabs(["Avancement", "Carte", "Qualité", "Composition", "Questionnaires"])

# ---------------------------------------------------------------- AVANCEMENT
with onglets[0]:
    lignes = []
    for commune, info in COMMUNES.items():
        recu = int((socio["commune"] == commune).sum()) if not socio.empty else 0
        trie = int((carac["commune"] == commune).sum()) if not carac.empty else 0
        cible = CIBLE_MENAGES if commune in COMMUNES_SOURCE else 0
        lignes.append({"Commune": commune, "Région": info["region"],
                       "Infrastructure": info["infra"], "Méthode": info["methode"],
                       "Cible sacs": cible, "Fiches reçues": recu,
                       "Reste à faire": max(cible - recu, 0),
                       "Avancement": (recu / cible) if cible else None,
                       "Échantillons triés": trie})
    suivi = pd.DataFrame(lignes)
    tot_cible = suivi["Cible sacs"].sum()
    tot_recu = suivi.loc[suivi["Cible sacs"] > 0, "Fiches reçues"].sum()

    a, b, c, d = st.columns(4)
    a.metric("Cible totale", f"{tot_cible} sacs")
    b.metric("Reçu", f"{tot_recu}", f"{tot_recu / tot_cible * 100:.0f} %")
    c.metric("Reste à faire", f"{max(tot_cible - tot_recu, 0)}")
    d.metric("Communes à 100 %",
             f"{int((suivi['Avancement'] >= 1).sum())} / {len(COMMUNES_SOURCE)}")

    try:
        import plotly.graph_objects as go
        src = suivi[suivi["Cible sacs"] > 0].sort_values("Avancement")
        fig = go.Figure()
        fig.add_bar(y=src["Commune"], x=src["Cible sacs"], orientation="h",
                    marker_color="#DCDCD4", hoverinfo="skip")
        fig.add_bar(y=src["Commune"], x=src["Fiches reçues"], orientation="h",
                    marker_color=[COULEURS[m] for m in src["Méthode"]],
                    hovertemplate="%{y} : %{x} fiches<extra></extra>")
        fig.add_vline(x=CIBLE_MENAGES, line_dash="dot", line_color="#B01B2E",
                      annotation_text=f"cible {CIBLE_MENAGES}")
        fig.update_layout(barmode="overlay", height=420, showlegend=False,
                          margin=dict(l=0, r=0, t=10, b=0), xaxis_title="Ménages",
                          plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
    except Exception:
        st.bar_chart(suivi.set_index("Commune")["Fiches reçues"])

    st.dataframe(suivi, hide_index=True, width="stretch",
                 column_config={"Avancement": st.column_config.ProgressColumn(
                     "Avancement", format="%.0f %%", min_value=0, max_value=1)})
    st.caption("Les quatre communes en prélèvement sur points de collecte, Dagana, "
               "Bokhol, Ndioum et Ranérou, n'ont pas de cible en sacs.")
    st.download_button("Télécharger le tableau de suivi",
                       suivi.to_csv(index=False).encode("utf-8"),
                       "suivi_avancement.csv", "text/csv")

# ---------------------------------------------------------------- CARTE
with onglets[1]:
    p_gpkg = chemin(FICHIER_GPKG)
    if p_gpkg is None:
        st.info(f"Le fond de carte `{FICHIER_GPKG}` n'est pas dans le dépôt. "
                "Le déposer dans un dossier `donnees` pour activer cette vue.")
    else:
        try:
            import geopandas as gpd
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.patheffects as pe

            @st.cache_data(show_spinner=False)
            def charger_couches(p):
                com = gpd.read_file(p, layer="communes")
                try:
                    sit = gpd.read_file(p, layer="sites")
                except Exception:
                    sit = None
                return com, sit

            communes_geo, sites = charger_couches(str(p_gpkg))
            recus = socio.groupby("commune").size() if not socio.empty else pd.Series(dtype=int)
            communes_geo["recus"] = communes_geo["commune"].map(recus).fillna(0).astype(int)
            communes_geo["cible"] = communes_geo["commune"].apply(
                lambda c: CIBLE_MENAGES if c in COMMUNES_SOURCE else 0)
            communes_geo["avancement"] = [
                (r / c * 100) if c else float("nan")
                for r, c in zip(communes_geo["recus"], communes_geo["cible"])]

            variable = st.radio("Variable cartographiée",
                                ["Avancement", "Méthode", "Population 2023"], horizontal=True)
            com = communes_geo.to_crs(3857)
            fig, ax = plt.subplots(figsize=(13, 7.2), dpi=140)
            ax.set_facecolor("#F7F7F4")
            if variable == "Méthode":
                for m, coul in COULEURS.items():
                    s = com[com["methode"] == m]
                    if len(s):
                        s.plot(ax=ax, facecolor=coul, edgecolor="white", lw=1.0)
            elif variable == "Population 2023":
                com.plot(ax=ax, column="pop_2023", cmap="YlGn", edgecolor="white", lw=0.8,
                         legend=True, legend_kwds={"label": "Habitants (RGPH-5, 2023)",
                                                   "shrink": 0.6})
            else:
                av = com.copy()
                av["avancement"] = av["avancement"].fillna(-1)
                hors, dans = av[av["avancement"] < 0], av[av["avancement"] >= 0]
                if len(hors):
                    hors.plot(ax=ax, facecolor="#E4E4DC", edgecolor="white", lw=0.8, hatch="///")
                if len(dans):
                    dans.plot(ax=ax, column="avancement", cmap="RdYlGn", vmin=0, vmax=100,
                              edgecolor="white", lw=0.8, legend=True,
                              legend_kwds={"label": "Avancement (%)", "shrink": 0.6})
            if sites is not None:
                for _, r in sites.to_crs(3857).iterrows():
                    est_source = str(r["methode"]).startswith("MODECOM")
                    ax.plot(r.geometry.x, r.geometry.y, marker="*" if est_source else "o",
                            ms=18 if est_source else 9,
                            mfc=COULEURS.get(r["methode"], "#888"), mec=ENCRE, mew=1.0, zorder=6)
            for _, r in com.iterrows():
                pt = r.geometry.representative_point()
                etiq = r["commune"]
                if variable == "Avancement" and r["cible"]:
                    etiq += f"\n{r['recus']}/{r['cible']}"
                ax.annotate(etiq, (pt.x, pt.y), ha="center", va="center", fontsize=7.5,
                            fontweight="bold", color=ENCRE, zorder=8,
                            path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])
            ax.set_xticks([])
            ax.set_yticks([])
            fig.tight_layout()
            st.pyplot(fig, width="stretch")
            if variable == "Avancement":
                st.caption("Les communes hachurées sont en prélèvement sur points de "
                           "collecte : pas de cible en sacs, donc pas de taux d'avancement.")
            cols = [c for c in ["commune", "region", "departement", "methode", "logist_cat",
                                "pop_2023", "menages", "recus", "cible", "avancement"]
                    if c in communes_geo.columns]
            st.dataframe(communes_geo[cols].sort_values("commune"),
                         hide_index=True, width="stretch")
        except Exception as e:
            st.error(f"Rendu de la carte impossible : {e}")

# ---------------------------------------------------------------- QUALITE
with onglets[2]:
    if socio.empty and carac.empty:
        st.info("Aucune soumission chargée. Choisir une source dans la barre latérale.")
    else:
        a1 = controler_socio(socio)
        a2 = controler_carac(carac, pesees)
        anomalies = pd.concat([a1, a2], ignore_index=True) if len(a1) or len(a2) else pd.DataFrame()
        nb = lambda g: int((anomalies["gravité"] == g).sum()) if not anomalies.empty else 0  # noqa: E731
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Soumissions contrôlées", len(socio) + len(carac))
        q2.metric("Bloquantes", nb("Bloquant"))
        q3.metric("À vérifier", nb("À vérifier"))
        q4.metric("Informations", nb("Information"))

        if nb("Bloquant"):
            st.error(f"{nb('Bloquant')} anomalies bloquantes à corriger avant analyse.")
        elif not anomalies.empty:
            st.warning("Aucune anomalie bloquante. Des points restent à vérifier.")
        else:
            st.success("Aucune anomalie détectée.")

        if not socio.empty and not carac.empty:
            if "menage_id" in socio.columns and "menage_id" in carac.columns:
                st.success("Les deux questionnaires partagent un identifiant de ménage, "
                           "le croisement composition et profil est possible.")
            else:
                st.warning("Le questionnaire de caractérisation ne porte aucun identifiant "
                           "de ménage. L'analyse restera au niveau de la commune.")

        if not anomalies.empty:
            g, d = st.columns([2, 3])
            with g:
                st.subheader("Par contrôle")
                st.dataframe(anomalies.groupby(["gravité", "contrôle"]).size()
                             .reset_index(name="Nombre").sort_values("Nombre", ascending=False),
                             hide_index=True, width="stretch")
            with d:
                st.subheader("Par commune")
                st.dataframe(anomalies.groupby(["commune", "gravité"]).size()
                             .unstack(fill_value=0), width="stretch")
            st.subheader("Détail")
            st.dataframe(anomalies, hide_index=True, width="stretch", height=380)
            st.download_button("Télécharger les anomalies",
                               anomalies.to_csv(index=False).encode("utf-8"),
                               "anomalies_modecom.csv", "text/csv")

# ---------------------------------------------------------------- COMPOSITION
with onglets[3]:
    if carac.empty or pesees is None:
        st.info("Cette vue demande les soumissions de caractérisation et le questionnaire "
                "correspondant.")
    else:
        cats = pesees[~pesees["globale"]]
        cols = [c for c in cats["name"] if c in carac.columns]
        if not cols:
            st.warning("Les colonnes de pesée ne se retrouvent pas dans les soumissions. "
                       "Vérifier l'origine de l'export.")
        else:
            dispo = sorted(carac["commune"].dropna().unique())
            choix = st.multiselect("Communes", dispo, default=dispo)
            sel = carac[carac["commune"].isin(choix)]
            masses = sel[cols].apply(pd.to_numeric, errors="coerce")
            total = float(masses.sum().sum())
            m1, m2, m3 = st.columns(3)
            m1.metric("Échantillons", len(sel))
            m2.metric("Masse brute cumulée",
                      f"{sel['masse_brute'].sum():,.0f} kg".replace(",", " "))
            m3.metric("Masse triée", f"{total:,.0f} kg".replace(",", " "))

            par_cat = (masses.sum().rename("kg").reset_index()
                       .rename(columns={"index": "name"})
                       .merge(cats[["name", "categorie", "granulometrie"]], on="name"))
            agrege = (par_cat.groupby("categorie")["kg"].sum().reset_index()
                      .sort_values("kg", ascending=False))
            agrege["part"] = agrege["kg"] / total * 100 if total else 0
            try:
                import plotly.express as px
                top = agrege.head(15).sort_values("part")
                fig = px.bar(top, x="part", y="categorie", orientation="h",
                             labels={"part": "Part de la masse triée (%)", "categorie": ""},
                             text=top["part"].map(lambda v: f"{v:.1f} %"))
                fig.update_traces(marker_color=VERT, textposition="outside", cliponaxis=False)
                fig.update_layout(height=520, margin=dict(l=0, r=40, t=10, b=0),
                                  plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, width="stretch")
            except Exception:
                st.bar_chart(agrege.set_index("categorie")["part"].head(15))
            st.dataframe(agrege.round(2).rename(columns={"categorie": "Fraction",
                                                         "kg": "Masse (kg)",
                                                         "part": "Part (%)"}),
                         hide_index=True, width="stretch", height=340)
            st.download_button("Télécharger la composition",
                               agrege.to_csv(index=False).encode("utf-8"),
                               "composition_modecom.csv", "text/csv")

# ---------------------------------------------------------------- QUESTIONNAIRES
with onglets[4]:
    if f_socio is None and f_carac is None:
        st.info("Les deux questionnaires XLSForm ne sont pas dans le dépôt.")
    else:
        dispo = [n for n, f in [("Enquête socio-démographique", f_socio),
                                ("Caractérisation des déchets", f_carac)] if f is not None]
        choix = st.radio("Questionnaire", dispo, horizontal=True)
        form = f_socio if choix.startswith("Enquête") else f_carac
        r = resume(form)
        k1, k2, k3 = st.columns(3)
        k1.metric("Questions", r["questions"])
        k2.metric("Sections", r["groupes"])
        k3.metric("Listes de choix", r["listes"])
        q = form["questions"]
        st.dataframe(q.groupby("groupe").size().reset_index(name="Questions"),
                     hide_index=True, width="stretch")
        st.dataframe(q[["groupe", "type", "name", "label"]], hide_index=True,
                     width="stretch", height=380)
        if not choix.startswith("Enquête") and pesees is not None:
            cats = pesees[~pesees["globale"]]
            st.write(f"{cats['categorie'].nunique()} sous-catégories déclinées en "
                     f"{cats['granulometrie'].nunique()} granulométries, "
                     f"soit {len(cats)} pesées, plus {int(pesees['globale'].sum())} "
                     "masses globales.")

st.divider()
st.caption("La collecte se fait dans ODK Collect ou KoboCollect, hors connexion. "
           "Cette application lit les soumissions une fois synchronisées.")
