"""Lecture des questionnaires XLSForm (ODK / KoboToolbox)."""
import re
import pandas as pd
from . import config

LABEL = "label::Français (fr)"
META = {"start", "end", "today", "deviceid", "note", "begin_group", "end_group",
        "begin_repeat", "end_repeat", "nan"}


def _norm(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df


def charger_form(chemin):
    """Retourne le dictionnaire d'un XLSForm : survey, choices, groupes, questions."""
    survey = _norm(pd.read_excel(chemin, sheet_name="survey"))
    choices = _norm(pd.read_excel(chemin, sheet_name="choices"))
    survey["type"] = survey["type"].astype(str).str.strip()
    survey["name"] = survey["name"].astype(str).str.strip()
    if LABEL not in survey.columns:
        cand = [c for c in survey.columns if c.startswith("label")]
        survey[LABEL] = survey[cand[0]] if cand else ""

    groupes, courant = [], None
    lignes = []
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
        lignes.append({
            "groupe": courant or "(hors groupe)",
            "type": t,
            "type_base": base,
            "name": r["name"],
            "label": str(r[LABEL]),
            "liste": t.split()[1] if len(t.split()) > 1 else None,
        })
    questions = pd.DataFrame(lignes)

    col_liste = choices.columns[0]
    return {"survey": survey, "choices": choices, "groupes": groupes,
            "questions": questions, "col_liste": col_liste}


def options(form, liste):
    """Modalites d'une liste de choix, sous forme de liste de libelles."""
    ch = form["choices"]
    col = form["col_liste"]
    lab = LABEL if LABEL in ch.columns else ch.columns[2]
    sub = ch[ch[col].astype(str).str.strip() == str(liste)]
    return [str(x).strip() for x in sub[lab].dropna().tolist()]


GRANULOS = ["hétéroclites", "grossiers", "moyens"]
MASSES_GLOBALES = ["masse totale brute", "masse après quartage", "masse nette totale"]


def decoupe_categorie(label):
    """Separe le libelle d'une pesee en (categorie, granulometrie)."""
    txt = re.sub(r"^\s*Masse\s*\(\s*Kg\s*\)?\s*", "", str(label)).strip()
    txt = re.sub(r"^\s*Masse\s*\(\s*Kg\s*", "", txt).strip()
    bas = txt.lower()
    for g in GRANULOS:
        if bas.endswith(g):
            return txt[: -len(g)].strip(), g
    return txt, "global"


def table_pesees(form):
    """Table des 119 champs de pesee du questionnaire de caracterisation."""
    q = form["questions"]
    d = q[q["type_base"] == "decimal"].copy()
    decoupe = d["label"].apply(decoupe_categorie)
    d["categorie"] = [x[0] for x in decoupe]
    d["granulometrie"] = [x[1] for x in decoupe]
    d["globale"] = d["categorie"].str.lower().isin(MASSES_GLOBALES)
    return d.reset_index(drop=True)


def resume(form):
    q = form["questions"]
    return {
        "questions": len(q),
        "groupes": len(form["groupes"]),
        "listes": form["choices"][form["col_liste"]].nunique(),
        "types": q["type_base"].value_counts().to_dict(),
    }


def charger_les_deux():
    socio = charger_form(config.chemin(config.FORM_SOCIO))
    carac = charger_form(config.chemin(config.FORM_CARAC))
    return socio, carac
