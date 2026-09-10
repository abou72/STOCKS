"""
Authentification simple (email / mot de passe) — chaque utilisateur a son propre
espace : ses produits et mouvements sont filtrés par user_id.
Inclut la réinitialisation de mot de passe par email (lien valable 1 heure).
"""
import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from urllib.parse import quote

import bcrypt
import streamlit as st
from sqlalchemy import text
from db import get_engine


def _get_secret(key: str):
    """Lit un secret dans st.secrets puis, à défaut, dans les variables d'environnement."""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except FileNotFoundError:
        pass
    return os.environ.get(key)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_user(email: str, password: str, nom_boutique: str) -> bool:
    """Retourne False si l'email existe déjà."""
    engine = get_engine()
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": email}
        ).fetchone()
        if exists:
            return False
        conn.execute(
            text("INSERT INTO users (email, password_hash, nom_boutique) VALUES (:email, :ph, :nb)"),
            {"email": email, "ph": hash_password(password), "nb": nom_boutique},
        )
    return True


def authenticate(email: str, password: str):
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, password_hash, nom_boutique, is_admin FROM users WHERE email = :email"),
            {"email": email},
        ).fetchone()
    if row and verify_password(password, row.password_hash):
        return {"id": row.id, "email": email, "nom_boutique": row.nom_boutique, "is_admin": bool(row.is_admin)}
    return None


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Envoie un email via SMTP. Nécessite SMTP_HOST, SMTP_USER, SMTP_PASSWORD
    (et optionnellement SMTP_PORT, SMTP_FROM) dans secrets.toml ou les variables d'env.
    Fonctionne avec Gmail (mot de passe d'application), Outlook, ou tout fournisseur SMTP."""
    host = _get_secret("SMTP_HOST")
    port = int(_get_secret("SMTP_PORT") or 587)
    user = _get_secret("SMTP_USER")
    password = _get_secret("SMTP_PASSWORD")
    sender = _get_secret("SMTP_FROM") or user

    if not all([host, user, password, sender]):
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


def demande_reset_form():
    """Formulaire 'Mot de passe oublié ?' — envoie un lien de réinitialisation par email."""
    with st.expander("Mot de passe oublié ?"):
        with st.form("form_reset_demande"):
            email_r = st.text_input("Ton email", key="email_reset_demande")
            envoyer = st.form_submit_button("Envoyer le lien de réinitialisation")
            if envoyer:
                email_r = email_r.strip().lower()
                token = generate_reset_token(email_r)
                if token:
                    app_url = _get_secret("https://bizstock.streamlit.app/") or "http://localhost:8501"
                    lien = f"{app_url}?reset_email={quote(email_r)}&reset_token={token}"
                    corps = (
                        "Bonjour,\n\n"
                        "Clique sur ce lien pour réinitialiser ton mot de passe (valable 1 heure) :\n"
                        f"{lien}\n\n"
                        "Si tu n'es pas à l'origine de cette demande, ignore cet email."
                    )
                    send_email(email_r, "Réinitialisation de ton mot de passe", corps)
                # Message générique volontaire, pour ne pas révéler si l'email existe ou non
                st.success("Si un compte existe avec cet email, un lien de réinitialisation vient d'être envoyé.")


def handle_password_reset_page() -> bool:
    """Affiche la page de réinitialisation si l'URL contient reset_email et reset_token.
    Retourne True si cette page a été affichée (l'appelant doit alors stopper l'exécution)."""
    params = st.query_params
    if "reset_email" not in params or "reset_token" not in params:
        return False

    email = params["reset_email"]
    token = params["reset_token"]

    st.title("📦 Réinitialiser ton mot de passe")
    with st.form("form_new_password"):
        pw1 = st.text_input("Nouveau mot de passe", type="password")
        pw2 = st.text_input("Confirmer le mot de passe", type="password")
        valider = st.form_submit_button("Réinitialiser le mot de passe")
        if valider:
            if len(pw1) < 6:
                st.error("Le mot de passe doit contenir au moins 6 caractères.")
            elif pw1 != pw2:
                st.error("Les mots de passe ne correspondent pas.")
            else:
                ok = reset_password_with_token(email, token, pw1)
                if ok:
                    st.success("Mot de passe mis à jour avec succès.")
                    st.query_params.clear()
                    st.info("Retourne sur la page d'accueil de l'app pour te connecter.")
                else:
                    st.error("Ce lien est invalide ou a expiré. Refais une demande de réinitialisation.")
    return True


def login_form() -> bool:
    """Affiche connexion / inscription. Retourne True si un utilisateur est connecté."""
    if "user" in st.session_state:
        return True

    st.title("📦 Gestion de Stock — Connexion")
    onglet_connexion, onglet_inscription = st.tabs(["Connexion", "Créer un compte"])

    with onglet_connexion:
        with st.form("form_login"):
            email = st.text_input("Email")
            password = st.text_input("Mot de passe", type="password")
            valider = st.form_submit_button("Se connecter")
            if valider:
                user = authenticate(email.strip().lower(), password)
                if user:
                    st.session_state["user"] = user
                    st.rerun()
                else:
                    st.error("Email ou mot de passe incorrect.")

        demande_reset_form()

    with onglet_inscription:
        with st.form("form_inscription"):
            nom_boutique = st.text_input("Nom de la boutique")
            email_i = st.text_input("Email", key="email_inscription")
            password_i = st.text_input("Mot de passe", type="password", key="pw_inscription")
            password_i2 = st.text_input("Confirmer le mot de passe", type="password")
            valider_i = st.form_submit_button("Créer mon compte")
            if valider_i:
                if not email_i.strip() or not password_i:
                    st.error("Email et mot de passe obligatoires.")
                elif password_i != password_i2:
                    st.error("Les mots de passe ne correspondent pas.")
                elif len(password_i) < 6:
                    st.error("Le mot de passe doit contenir au moins 6 caractères.")
                else:
                    ok = create_user(email_i.strip().lower(), password_i, nom_boutique.strip())
                    if ok:
                        st.success("Compte créé. Tu peux te connecter maintenant depuis l'onglet Connexion.")
                    else:
                        st.error("Un compte existe déjà avec cet email.")

    return False


def logout_button():
    with st.sidebar:
        user = st.session_state.get("user")
        if user:
            label = f"Connecté : {user['email']}"
            if user.get("is_admin"):
                label += " 👑 (admin)"
            st.caption(label)
            if st.button("Se déconnecter"):
                del st.session_state["user"]
                st.rerun()