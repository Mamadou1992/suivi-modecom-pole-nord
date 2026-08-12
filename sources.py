"""Sources de donnees : KoboToolbox, fichiers CSV exportes, ou jeu de demonstration."""
import io
import unicodedata
import pandas as pd
from . import config


# ---------------------------------------------------------------- utilitaires
def sans_accent(s):
    s = str(s)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def rapproche_commune(valeur):
    """Ramene une valeur de commune saisie vers le libelle officiel."""
    if pd.isna(valeur):
        return None
    v = sans_accent(valeur).strip().lower().replace("_", " ").replace("-", " ")
    for officiel in config.COMMUNES:
        if sans_accent(officiel).lower().replace("-", " ") == v:
            return officiel
    return str(valeur).strip()


def _renomme(df, correspondances):
    ren = {}
    for cible, candidats in correspondances.items():
        for c in candidats:
            if c in df.columns:
                ren[c] = cible
                break
    return df.rename(columns=ren)


# ------------------------------------------------------------------- Kobo API
def charger_kobo(base_url, token, uid, timeout=60):
    """Lit les soumissions d'un formulaire KoboToolbox. Necessite `requests`."""
    import requests

    base_url = base_url.rstrip("/")
    url = f"{base_url}/api/v2/assets/{uid}/data.json"
    entetes = {"Authorization": f"Token {token}"}
    lignes, page = [], url
    while page:
        r = requests.get(page, headers=entetes, timeout=timeout)
        r.raise_for_status()
        js = r.json()
        lignes.extend(js.get("results", []))
        page = js.get("next")
    return pd.json_normalize(lignes)


# ------------------------------------------------------------------ fichiers
def charger_fichier(fichier):
    """Lit un CSV ou un XLSX exporte depuis Kobo ou ODK."""
    nom = getattr(fichier, "name", str(fichier)).lower()
    if nom.endswith((".xlsx", ".xls")):
        return pd.read_excel(fichier)
    donnees = fichier.read() if hasattr(fichier, "read") else open(fichier, "rb").read()
    for sep in (";", ",", "\t"):
        try:
            df = pd.read_csv(io.BytesIO(donnees), sep=sep)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    return pd.read_csv(io.BytesIO(donnees))


# ------------------------------------------------------------- normalisation
COLS_SOCIO = {
    "menage_id": ["menage_id", "s0/menage_id", "N° ménage / sac"],
    "commune": ["commune", "s0/commune", "Commune"],
    "region": ["region", "s0/region", "Région"],
    "quartier": ["quartier", "s0/quartier", "Quartier / village"],
    "strate": ["strate", "s0/strate"],
    "milieu": ["milieu", "s0/milieu"],
    "enqueteur": ["enqueteur", "s0/enqueteur"],
    "superviseur": ["superviseur", "s0/superviseur"],
    "consentement": ["consentement", "Le ménage accepte-t-il de participer"],
    "a1_total": ["a1_total", "sa/a1_total"],
    "a2_present": ["a2_present", "sa/a2_present"],
    "date": ["today", "date", "_submission_time", "end"],
    "gps": ["gps", "s0/gps"],
}

COLS_CARAC = {
    "code_echantillon": ["code_echantillon", "m2/code_echantillon"],
    "date": ["date_collecte", "m0/date_collecte", "_submission_time"],
    "superviseur": ["superviseur", "m0/superviseur"],
    "region": ["region", "m1/region"],
    "infrastructure": ["Infrastructure_concern_e", "m1/Infrastructure_concern_e"],
    "type_site": ["type_site", "m1/type_site"],
    "nom_site": ["Nom_du_site", "m1/Nom_du_site"],
    "niveau_vie": ["niveau_vie", "m1/niveau_vie"],
    "type_dechet": ["type_dechet", "m1/type_dechet"],
    "methode": ["methode", "m2/methode"],
    "saison": ["saison", "m2/saison"],
    "masse_brute": ["masse_totale_brute", "m2/masse_totale_brute"],
    "masse_quartage": ["masse_apres_quartage", "m2/masse_apres_quartage"],
    "masse_nette": ["masse_nette_totale", "m2/masse_nette_totale"],
}

# Le formulaire de caracterisation eclate la commune en 5 champs, un par infrastructure
CHAMPS_COMMUNE_CARAC = ["Commune_Dagana", "Commune_Bokhol", "Commune_Ndioum",
                        "Commune_OGO", "Commune_Ran_rou"]


SIGNES_SOCIO = {"menage_id", "a1_total", "a2_present", "consentement", "strate"}
SIGNES_CARAC = {"masse_totale_brute", "masse_apres_quartage", "masse_nette_totale",
                "code_echantillon", "Infrastructure_concern_e"}


def identifier_formulaire(df):
    """Devine si un jeu de soumissions vient du socio-demographique ou de la caracterisation.

    Renvoie "socio", "carac" ou None. Permet de saisir les deux identifiants Kobo
    dans n'importe quel ordre.
    """
    if df is None or getattr(df, "empty", True):
        return None
    colonnes = {str(c).split("/")[-1] for c in df.columns}
    n_socio = len(colonnes & SIGNES_SOCIO)
    n_carac = len(colonnes & SIGNES_CARAC)
    if n_carac > n_socio:
        return "carac"
    if n_socio > n_carac:
        return "socio"
    return None


def repartir(jeux):
    """Range une liste de jeux bruts en (socio, carac), quel que soit l'ordre de saisie."""
    socio = carac = None
    restants = []
    for df in jeux:
        genre = identifier_formulaire(df)
        if genre == "socio" and socio is None:
            socio = df
        elif genre == "carac" and carac is None:
            carac = df
        elif df is not None:
            restants.append(df)
    for df in restants:                      # repli si la detection est restee muette
        if socio is None:
            socio = df
        elif carac is None:
            carac = df
    return socio, carac


def normalise_socio(df):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [str(c).split("/")[-1] if "/" in str(c) else str(c) for c in df.columns]
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
    df.columns = [str(c).split("/")[-1] if "/" in str(c) else str(c) for c in df.columns]
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
