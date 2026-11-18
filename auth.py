"""
Authentification (email / mot de passe) — chaque utilisateur a son propre espace : ses données sont filtrées par user_id.

Sécurité :
- blocage après 5 échecs de connexion (15 min, puis durées croissantes), identique que le compte existe ou non ;
- mots de passe chiffrés (bcrypt), politique de mot de passe (8 caractères min., pas de mots de passe courants) ;
- réinitialisation par email : jeton aléatoire stocké HACHÉ, valable 1 h, essais limités, demandes limitées (3 / heure) ;
- inscription : réponse identique que l'email soit déjà inscrit ou non (pas d'énumération de comptes) ;
- consentement à la politique de confidentialité enregistré à l'inscription ;
- déconnexion automatique après 60 minutes d'inactivité.
"""
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from urllib.parse import quote

import streamlit as st
from sqlalchemy import text

from db import get_engine
from theme import brand_header
from legal import POLICY_VERSION, SESSION_TIMEOUT_MIN, render_policy
from security import (
    hash_password, verify_password, DUMMY_HASH, valider_mot_de_passe,
    verifier_blocage, enregistrer_echec, reinitialiser, limiter_debit,
    TropDeTentatives, ConnexionRefusee, MAX_ECHECS, DUREES_BLOCAGE_MIN,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_secret(key: str):
    """Lit un secret dans st.secrets puis, à défaut, dans les variables d'environnement."""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except FileNotFoundError:
        pass
    return os.environ.get(key)


def _hash_jeton(jeton: str) -> str:
    return hashlib.sha256(jeton.encode()).hexdigest()


# ----------------------------------------------------------------------
# Comptes
# ----------------------------------------------------------------------
def create_user(email: str, password: str, nom_boutique: str) -> bool:
    """Crée le compte avec le consentement à la version courante de la politique. Retourne False si l'email existe déjà."""
    ph = hash_password(password)  # toujours calculé : le temps de réponse ne révèle pas si l'email existe
    with get_engine().begin() as conn:
        row = conn.execute(
            text("INSERT INTO users (email, password_hash, nom_boutique, consent_version, consent_at) "
                 "VALUES (:email, :ph, :nb, :cv, timezone('utc', now())) "
                 "ON CONFLICT (email) DO NOTHING RETURNING id"),
            {"email": email, "ph": ph, "nb": nom_boutique, "cv": POLICY_VERSION},
        ).fetchone()
    return row is not None


def authenticate(email: str, password: str):
    """Retourne le dict utilisateur si les identifiants sont corrects.
    Lève TropDeTentatives (compte bloqué) ou ConnexionRefusee (identifiants faux, avec le nombre d'essais restants)."""
    verifier_blocage("login", email)  # pendant un blocage, le mot de passe n'est même pas vérifié

    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT id, password_hash, nom_boutique, is_admin, consent_version FROM users WHERE email = :email"),
            {"email": email},
        ).fetchone()

    # Vérification toujours effectuée (hash factice si l'email est inconnu) pour égaliser le temps de réponse
    mot_de_passe_ok = verify_password(password, row.password_hash if row else DUMMY_HASH)
    if row and mot_de_passe_ok:
        reinitialiser("login", email)
        return {"id": row.id, "email": email, "nom_boutique": row.nom_boutique,
                "is_admin": bool(row.is_admin), "consent_version": row.consent_version}

    restantes, bloque = enregistrer_echec("login", email)
    raise ConnexionRefusee(restantes, bloque)


def send_email(to_email: str, subject: str, body: str, quiet: bool = False) -> bool:
    """Envoie un email via SMTP. Nécessite SMTP_HOST, SMTP_USER, SMTP_PASSWORD
    (et optionnellement SMTP_PORT, SMTP_FROM) dans secrets.toml ou les variables d'env.
    Fonctionne avec Gmail (mot de passe d'application), Outlook, ou tout fournisseur SMTP."""
    host = _get_secret("SMTP_HOST")
    port = int(_get_secret("SMTP_PORT") or 587)
    user = _get_secret("SMTP_USER")
    password = _get_secret("SMTP_PASSWORD")
    sender = _get_secret("SMTP_FROM") or user

    if not all([host, user, password, sender]):
        if quiet:
            print("[auth] Envoi d'email non configuré (SMTP_HOST / SMTP_USER / SMTP_PASSWORD).")
            return False
        st.error(
            "Envoi d'email non configuré. Ajoute SMTP_HOST, SMTP_USER et SMTP_PASSWORD "
            "dans les secrets de l'application."
        )
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(sender, [to_email], msg.as_string())
        return True
    except Exception as e:
        if quiet:
            print(f"[auth] Échec de l'envoi de l'email : {e}")
            return False
        st.error(f"Échec de l'envoi de l'email : {e}")
        return False


def generate_reset_token(email: str):
    """Génère un token de réinitialisation valable 1h. Retourne None si l'email n'existe pas."""
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()
        if not row:
            return None
        token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(hours=1)
        conn.execute(
            text("UPDATE users SET reset_token = :t, reset_token_expires = :e WHERE email = :email"),
            {"t": token, "e": expires, "email": email},
        )
    return token


def reset_password_with_token(email: str, token: str, new_password: str) -> bool:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT reset_token, reset_token_expires FROM users WHERE email = :email"),
            {"email": email},
        ).fetchone()
        if not row or not row.reset_token or row.reset_token != token:
            return False
        if row.reset_token_expires is None or row.reset_token_expires < datetime.now():
            return False
        conn.execute(
            text("UPDATE users SET password_hash = :ph, reset_token = NULL, reset_token_expires = NULL "
                 "WHERE email = :email"),
            {"ph": hash_password(new_password), "email": email},
        )
    return True


# ----------------------------------------------------------------------
# Réinitialisation du mot de passe (jeton haché, essais et demandes limités)
# ----------------------------------------------------------------------
def generate_reset_token(email: str):
    """Génère un jeton valable 1 h (stocké haché). Retourne None si l'email n'existe pas ou si la limite de demandes est atteinte."""
    if not limiter_debit("resetreq", email, 3, 60):
        return None
    with get_engine().begin() as conn:
        row = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()
        if not row:
            return None
        jeton = secrets.token_urlsafe(32)
        conn.execute(
            text("UPDATE users SET reset_token = :t, reset_token_expires = :e WHERE email = :email"),
            {"t": _hash_jeton(jeton), "e": datetime.now() + timedelta(hours=1), "email": email},
        )
    return jeton


def reset_password_with_token(email: str, token: str, new_password: str) -> bool:
    """Lève TropDeTentatives si trop de jetons faux ont été essayés pour cet email."""
    verifier_blocage("resettoken", email)
    with get_engine().begin() as conn:
        row = conn.execute(
            text("SELECT reset_token, reset_token_expires FROM users WHERE email = :email"), {"email": email}
        ).fetchone()
        valide = bool(
            row and row.reset_token and hmac.compare_digest(row.reset_token, _hash_jeton(token))
            and row.reset_token_expires is not None and row.reset_token_expires >= datetime.now()
        )
        if not valide:
            enregistrer_echec("resettoken", email)
            return False
        conn.execute(
            text("UPDATE users SET password_hash = :ph, reset_token = NULL, reset_token_expires = NULL WHERE email = :email"),
            {"ph": hash_password(new_password), "email": email},
        )
    reinitialiser("resettoken", email)
    reinitialiser("login", email)  # le propriétaire de l'email retrouve l'accès
    return True


def demande_reset_form():
    """Formulaire 'Mot de passe oublié ?' — envoie un lien de réinitialisation par email."""
    with st.expander("Mot de passe oublié ?"):
        with st.form("form_reset_demande"):
            email_r = st.text_input("Ton email", key="email_reset_demande")
            envoyer = st.form_submit_button("Envoyer le lien de réinitialisation", type="primary")
            if envoyer:
                email_r = email_r.strip().lower()
                token = generate_reset_token(email_r) if email_r else None
                if token:
                    app_url = _get_secret("APP_URL") or "http://localhost:8501"
                    lien = f"{app_url}?reset_email={quote(email_r)}&reset_token={token}"
                    corps = (
                        "Bonjour,\n\n"
                        "Clique sur ce lien pour réinitialiser ton mot de passe (valable 1 heure) :\n"
                        f"{lien}\n\n"
                        "Si tu n'es pas à l'origine de cette demande, ignore cet email."
                    )
                    send_email(email_r, "Réinitialisation de ton mot de passe", corps, quiet=True)
                # Message identique dans tous les cas : on ne révèle pas si l'email existe
                st.success("Si un compte existe avec cet email, un lien de réinitialisation vient d'être envoyé "
                           "(3 demandes maximum par heure).")


def handle_password_reset_page() -> bool:
    """Affiche la page de réinitialisation si l'URL contient reset_email et reset_token.
    Retourne True si cette page a été affichée (l'appelant doit alors stopper l'exécution)."""
    params = st.query_params
    if "reset_email" not in params or "reset_token" not in params:
        return False

    email = params["reset_email"].strip().lower()
    token = params["reset_token"]

    brand_header("Réinitialise ton mot de passe en quelques secondes.")
    with st.form("form_new_password"):
        pw1 = st.text_input("Nouveau mot de passe", type="password")
        pw2 = st.text_input("Confirmer le mot de passe", type="password")
        valider = st.form_submit_button("Réinitialiser le mot de passe", type="primary")
        if valider:
            erreur = valider_mot_de_passe(pw1, email)
            if erreur:
                st.error(erreur)
            elif pw1 != pw2:
                st.error("Les mots de passe ne correspondent pas.")
            else:
                try:
                    ok = reset_password_with_token(email, token, pw1)
                except TropDeTentatives as e:
                    st.error(f"Trop de tentatives. Réessaie dans {e.minutes} minute(s).")
                else:
                    if ok:
                        st.success("Mot de passe mis à jour avec succès.")
                        st.query_params.clear()
                        st.info("Retourne sur la page d'accueil de l'app pour te connecter.")
                    else:
                        st.error("Ce lien est invalide ou a expiré. Refais une demande de réinitialisation.")
    return True


def _session_expiree() -> bool:
    """Gère l'inactivité : met à jour l'horodatage, ou vide la session si elle a expiré."""
    if "user" not in st.session_state:
        return False
    maintenant = time.time()
    derniere = st.session_state.get("last_activity")
    if derniere is not None and maintenant - derniere > SESSION_TIMEOUT_MIN * 60:
        st.session_state.clear()
        return True
    st.session_state["last_activity"] = maintenant
    return False


def login_form() -> bool:
    """Affiche connexion / inscription. Retourne True si un utilisateur est connecté."""
    expiree = _session_expiree()
    if "user" in st.session_state:
        return True

    brand_header()
    if expiree:
        st.info("Ta session a expiré après une période d'inactivité. Reconnecte-toi.")
    if st.session_state.pop("compte_supprime", False):
        st.success("Ton compte et tes données ont été supprimés. Merci d'avoir utilisé BizStock.")

    onglet_connexion, onglet_inscription = st.tabs(["Connexion", "Créer un compte"])

    with onglet_connexion:
        with st.form("form_login"):
            email = st.text_input("Email")
            password = st.text_input("Mot de passe", type="password")
            valider = st.form_submit_button("Se connecter", type="primary")
            if valider:
                email_n = email.strip().lower()
                if not email_n or not password:
                    st.error("Renseigne ton email et ton mot de passe.")
                else:
                    try:
                        user = authenticate(email_n, password)
                    except TropDeTentatives as e:
                        st.error(f"Trop de tentatives. Réessaie dans {e.minutes} minute(s).")
                    except ConnexionRefusee as e:
                        if e.bloque_minutes:
                            st.error(f"Trop de tentatives. Accès bloqué pendant {e.bloque_minutes} minutes.")
                        else:
                            message = "Email ou mot de passe incorrect."
                            if e.restantes <= 2:
                                message += (f" Il te reste {e.restantes} tentative(s) avant un blocage temporaire "
                                            f"de {DUREES_BLOCAGE_MIN[0]} minutes.")
                            st.error(message)
                    else:
                        st.session_state["user"] = user
                        st.session_state["last_activity"] = time.time()
                        st.rerun()

        demande_reset_form()

    with onglet_inscription:
        with st.form("form_inscription"):
            nom_boutique = st.text_input("Nom de la boutique")
            email_i = st.text_input("Email", key="email_inscription")
            password_i = st.text_input("Mot de passe (8 caractères minimum)", type="password", key="pw_inscription")
            password_i2 = st.text_input("Confirmer le mot de passe", type="password")
            consent = st.checkbox("J'ai lu et j'accepte la Politique de confidentialité et les conditions d'utilisation "
                                  "des données (lisible ci-dessous).", key="consent_inscription")
            valider_i = st.form_submit_button("Créer mon compte", type="primary")
            if valider_i:
                email_n = email_i.strip().lower()
                erreur_mdp = valider_mot_de_passe(password_i, email_n) if password_i else None
                if not nom_boutique.strip() or not email_n or not password_i:
                    st.error("Nom de la boutique, email et mot de passe sont obligatoires.")
                elif not EMAIL_RE.match(email_n):
                    st.error("Adresse email invalide.")
                elif password_i != password_i2:
                    st.error("Les mots de passe ne correspondent pas.")
                elif erreur_mdp:
                    st.error(erreur_mdp)
                elif not consent:
                    st.error("Tu dois accepter la politique de confidentialité pour créer un compte.")
                elif not (limiter_debit("signup", email_n, 5, 60) and limiter_debit("signup_global", "tous", 100, 60)):
                    st.error("Trop de demandes d'inscription. Réessaie plus tard.")
                else:
                    create_user(email_n, password_i, nom_boutique.strip())
                    # Réponse identique que l'email soit nouveau ou déjà inscrit : on ne révèle pas quels emails ont un compte
                    st.success("Demande enregistrée. Si cet email n'était pas déjà inscrit, ton compte est créé : "
                               "connecte-toi depuis l'onglet « Connexion ». S'il l'était déjà, utilise « Mot de passe oublié ? ».")

    with st.expander("📄 Politique de confidentialité et d'utilisation des données"):
        render_policy()

    return False


def logout_button():
    """Zone de déconnexion de la barre latérale. Une CSS (clé « sidebar_logout ») la place tout en bas."""
    user = st.session_state.get("user")
    if not user:
        return
    with st.sidebar:
        try:
            zone = st.container(key="sidebar_logout")
        except TypeError:  # anciennes versions de Streamlit sans paramètre key
            zone = st.container()
        with zone:
            label = f"Connecté : {user['email']}"
            if user.get("is_admin"):
                label += " 👑 (admin)"
            st.caption(label)
            if st.button("Se déconnecter", key="btn_logout"):
                st.session_state.clear()
                st.rerun()
