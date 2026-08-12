"""Acces protege par mot de passe partage.

Le mot de passe est lu dans .streamlit/secrets.toml, sous la cle [app] mot_de_passe.
Ce fichier est exclu du depot par .gitignore : aucun mot de passe ne circule sur GitHub.
Sur Streamlit Cloud, le meme contenu se colle dans Settings puis Secrets.

Variante possible, si l'on prefere ne pas ecrire le mot en clair meme en local :
    [app]
    empreinte_mot_de_passe = "sha256 du mot de passe"
obtenue par :
    python -c "import hashlib;print(hashlib.sha256('votre_mot'.encode()).hexdigest())"
"""
import hashlib

import streamlit as st

CLE = "authentifie"


def _empreinte(texte):
    return hashlib.sha256(str(texte).encode("utf-8")).hexdigest()


def _attendue():
    """Empreinte attendue, lue dans les secrets. None si rien n'est configure."""
    try:
        app = st.secrets.get("app", {})
    except Exception:
        return None
    if app.get("empreinte_mot_de_passe"):
        return str(app["empreinte_mot_de_passe"]).strip().lower()
    if app.get("mot_de_passe"):
        return _empreinte(app["mot_de_passe"])
    return None


def _bandeau():
    st.markdown(
        "<div style='background:#1B5E36;color:#fff;padding:14px 20px;border-radius:6px;"
        "margin-bottom:18px'><h1 style='margin:0;font-size:24px'>Suivi MODECOM Pôle Nord"
        "</h1><p style='margin:4px 0 0 0;font-size:14px;opacity:.9'>Accès réservé à "
        "l'équipe du projet</p></div>", unsafe_allow_html=True)


def exiger_mot_de_passe():
    """Bloque la page tant que le mot de passe n'a pas ete saisi."""
    if st.session_state.get(CLE):
        return True

    attendue = _attendue()
    if attendue is None:
        _bandeau()
        st.error(
            "Aucun mot de passe n'est configuré. Créer le fichier "
            "`.streamlit/secrets.toml` avec :\n\n"
            "```toml\n[app]\nmot_de_passe = \"votre_mot_de_passe\"\n```\n\n"
            "Sur Streamlit Cloud, coller ces deux lignes dans Settings puis Secrets."
        )
        st.stop()

    _bandeau()
    with st.form("connexion"):
        saisi = st.text_input("Mot de passe", type="password")
        valider = st.form_submit_button("Entrer")

    if valider:
        if _empreinte(saisi) == attendue:
            st.session_state[CLE] = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")

    st.caption("Les données d'enquête portent sur des ménages identifiés. "
               "Ne pas diffuser le mot de passe hors de l'équipe.")
    st.stop()
    return False


def bouton_deconnexion():
    """Bouton de deconnexion, a placer dans la barre laterale."""
    if st.session_state.get(CLE) and st.sidebar.button("Se déconnecter",
                                                       width="stretch"):
        st.session_state[CLE] = False
        st.rerun()
