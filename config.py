"""Configuration centrale de l'application de suivi MODECOM Pole Nord."""
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent

# Les donnees sont cherchees d'abord dans le dossier `donnees` embarque avec
# l'application, ce qui rend le depot autonome pour un deploiement sur
# Streamlit Community Cloud, puis dans le dossier parent en developpement local.
_CANDIDATS = [APP_DIR / "donnees", APP_DIR.parent]
DATA_DIR = next((d for d in _CANDIDATS if d.exists()), APP_DIR)

FICHIER_COMMUNES = "Communes_caracterisation_ANSD2023_v3.xlsx"
FICHIER_COMMUNES_SECOURS = "Communes_caracterisation_ANSD2023.xlsx"
FICHIER_GPKG = "Caracterisation_communes.gpkg"
FORM_SOCIO = "Enquête socio-démographique  MODECOM Pôle Nord.xlsx"
FORM_CARAC = "Caractérisation des déchets MODECOM_v2.xlsx"

# Logo institutionnel, facultatif : depose dans assets/ sous l'un de ces noms
ASSETS_DIR = APP_DIR / "assets"
NOMS_LOGO = ["logo_sgp.png", "logo_sgp.jpg", "logo_sgp.jpeg", "logo_sgp.svg",
             "logo_SGP.png", "logo_SGP.jpg", "logo_SGP.jpeg"]

# KoboToolbox : identifiants des deux formulaires du projet.
# L'ordre n'a pas d'importance, l'application reconnait chaque jeu a son contenu.
KOBO_URL = "https://kf.kobotoolbox.org"
KOBO_UID_1 = "a6g6VnmqYqVBf33QhXUVe3"
KOBO_UID_2 = "aG2BGSMEib9xWfRzoeXcXm"

# Dimensionnement de l'echantillon : effectif egal par commune
# n = (1,96 x CV / marge)^2 avec CV = 40 % et marge = 10 %
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


def chemin(nom: str) -> Path:
    """Chemin d'un fichier de donnees, avec repli sur le dossier parent."""
    p = DATA_DIR / nom
    if p.exists():
        return p
    for d in _CANDIDATS:
        q = d / nom
        if q.exists():
            return q
    return p


def logo():
    """Chemin du logo SGP, cherche dans assets/ puis a la racine de l'application."""
    for dossier in (ASSETS_DIR, APP_DIR):
        for nom in NOMS_LOGO:
            p = dossier / nom
            if p.exists():
                return p
    return None
