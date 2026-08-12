"""Controles qualite sur les soumissions des deux questionnaires."""
import pandas as pd
from . import config


def _ajoute(anomalies, gravite, controle, sous_ensemble, cle, detail):
    for _, r in sous_ensemble.iterrows():
        anomalies.append({
            "gravité": gravite,
            "questionnaire": controle[0],
            "contrôle": controle[1],
            "identifiant": r.get(cle, ""),
            "commune": r.get("commune", ""),
            "détail": detail(r) if callable(detail) else detail,
        })


def controler_socio(df):
    a = []
    if df is None or df.empty:
        return pd.DataFrame(a)

    if "menage_id" in df:
        dup = df[df.duplicated("menage_id", keep=False) & df["menage_id"].notna()]
        _ajoute(a, "Bloquant", ("Socio-démographique", "Identifiant de ménage en doublon"),
                dup, "menage_id", "Le même numéro de sac apparaît plusieurs fois")

    if {"a1_total", "a2_present"} <= set(df.columns):
        inc = df[df["a2_present"] > df["a1_total"]]
        _ajoute(a, "Bloquant", ("Socio-démographique", "Présents supérieurs à l'effectif"),
                inc, "menage_id",
                lambda r: f"{r['a2_present']:.0f} présents pour {r['a1_total']:.0f} résidents")

        gros = df[df["a1_total"] > 40]
        _ajoute(a, "À vérifier", ("Socio-démographique", "Ménage de taille inhabituelle"),
                gros, "menage_id", lambda r: f"{r['a1_total']:.0f} personnes déclarées")

    if "consentement" in df:
        refus = df[df["consentement"].astype(str).str.lower().str.startswith("non")]
        _ajoute(a, "Information", ("Socio-démographique", "Refus de participation"),
                refus, "menage_id", "Le ménage a refusé, le sac ne doit pas être compté")

    if "commune" in df:
        hors = df[~df["commune"].isin(config.COMMUNES)]
        _ajoute(a, "Bloquant", ("Socio-démographique", "Commune hors périmètre"),
                hors, "menage_id", lambda r: f"Commune non reconnue : {r['commune']}")

        site = df[df["commune"].isin(config.COMMUNES_SITE)]
        _ajoute(a, "À vérifier", ("Socio-démographique", "Commune sans dépôt de sacs"),
                site, "menage_id",
                lambda r: f"{r['commune']} est en prélèvement sur points de collecte")

    return pd.DataFrame(a)


def controler_carac(df, pesees=None):
    a = []
    if df is None or df.empty:
        return pd.DataFrame(a)

    if {"masse_brute", "masse_quartage"} <= set(df.columns):
        inc = df[df["masse_quartage"] > df["masse_brute"]]
        _ajoute(a, "Bloquant", ("Caractérisation", "Masse après quartage supérieure à la brute"),
                inc, "code_echantillon",
                lambda r: f"{r['masse_quartage']:.1f} kg contre {r['masse_brute']:.1f} kg")

    if {"masse_nette", "masse_quartage"} <= set(df.columns):
        inc = df[df["masse_nette"] > df["masse_quartage"] * 1.001]
        _ajoute(a, "Bloquant", ("Caractérisation", "Masse nette supérieure au quartage"),
                inc, "code_echantillon",
                lambda r: f"{r['masse_nette']:.1f} kg contre {r['masse_quartage']:.1f} kg")

    if pesees is not None and "masse_nette" in df:
        cols = [c for c in pesees[~pesees["globale"]]["name"] if c in df.columns]
        if cols:
            somme = df[cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
            ecart = (somme - df["masse_nette"]) / df["masse_nette"].replace(0, pd.NA)
            hors = df[ecart.abs() > 0.05].assign(_ecart=ecart)
            _ajoute(a, "Bloquant", ("Caractérisation", "Somme des fractions hors tolérance"),
                    hors, "code_echantillon",
                    lambda r: f"écart de {r['_ecart'] * 100:+.1f} % avec la masse nette")

    if "masse_brute" in df:
        faible = df[df["masse_brute"] < 100]
        _ajoute(a, "À vérifier", ("Caractérisation", "Échantillon de faible masse"),
                faible, "code_echantillon",
                lambda r: f"{r['masse_brute']:.1f} kg, en dessous du seuil de 100 kg")

    if "commune" in df:
        hors = df[~df["commune"].isin(config.COMMUNES)]
        _ajoute(a, "Bloquant", ("Caractérisation", "Commune hors périmètre"),
                hors, "code_echantillon", lambda r: f"Commune non reconnue : {r['commune']}")

    if "code_echantillon" in df:
        dup = df[df.duplicated("code_echantillon", keep=False) & df["code_echantillon"].notna()]
        _ajoute(a, "Bloquant", ("Caractérisation", "Code d'échantillon en doublon"),
                dup, "code_echantillon", "Le même code apparaît plusieurs fois")

    return pd.DataFrame(a)


def controler_appariement(socio, carac):
    """Verifie si les deux questionnaires peuvent etre rapproches."""
    if socio is None or socio.empty or carac is None or carac.empty:
        return None
    cle_commune = "menage_id" in socio.columns and "menage_id" in carac.columns
    return {
        "appariable": cle_commune,
        "message": (
            "Les deux questionnaires partagent un identifiant de ménage, "
            "le croisement composition / profil est possible."
            if cle_commune else
            "Le questionnaire de caractérisation ne porte aucun identifiant de ménage. "
            "Le croisement avec le profil du ménage est impossible en l'état : "
            "l'analyse restera au niveau de la commune."
        ),
    }
