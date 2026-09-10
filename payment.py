"""
Intégration Wave (Checkout API) pour débloquer l'accès à l'application après paiement.

Flux :
1. L'utilisateur connecté mais non payé voit un écran "Payer avec Wave".
2. On crée une Checkout Session Wave et on redirige vers wave_launch_url.
3. Wave redirige l'utilisateur vers success_url ou error_url (avec son id dans l'URL).
4. On vérifie le statut réel du paiement auprès de Wave (jamais on ne fait confiance
   uniquement à la redirection) avant de débloquer l'accès.

Nécessite WAVE_API_KEY et APP_URL dans les secrets de l'application.
"""
import os
import requests
import streamlit as st
from sqlalchemy import text
from db import get_engine

WAVE_API_BASE = "https://api.wave.com/v1"


def _get_secret(key: str):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except FileNotFoundError:
        pass
    return os.environ.get(key)


def _headers() -> dict:
    api_key = _get_secret("WAVE_API_KEY")
    if not api_key:
        st.error("Clé API Wave manquante. Ajoute WAVE_API_KEY dans les secrets de l'application.")
        st.stop()
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def create_checkout_session(user_id: int, amount: str, currency: str = "XOF") -> dict:
    """Crée une session de paiement Wave et enregistre son id pour vérification ultérieure."""
    app_url = _get_secret("APP_URL") or "http://localhost:8501"
    payload = {
        "amount": amount,
        "currency": currency,
        "client_reference": f"user-{user_id}",
        "success_url": f"{app_url}?payment=success&uid={user_id}",
        "error_url": f"{app_url}?payment=error&uid={user_id}",
    }
    resp = requests.post(f"{WAVE_API_BASE}/checkout/sessions", json=payload, headers=_headers(), timeout=10)
    resp.raise_for_status()
    session = resp.json()

    with get_engine().begin() as conn:
        conn.execute(
            text("UPDATE users SET last_checkout_id = :cid WHERE id = :uid"),
            {"cid": session["id"], "uid": user_id},
        )
    return session


def retrieve_checkout(checkout_id: str) -> dict:
    resp = requests.get(f"{WAVE_API_BASE}/checkout/sessions/{checkout_id}", headers=_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()


def mark_user_paid(user_id: int):
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE users SET has_paid = TRUE WHERE id = :uid"), {"uid": user_id})


def is_user_paid(user_id: int) -> bool:
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT has_paid FROM users WHERE id = :uid"), {"uid": user_id}).fetchone()
    return bool(row and row.has_paid)


def handle_payment_return() -> bool:
    """Si l'URL contient payment=success/error&uid=..., vérifie le paiement auprès de Wave
    et affiche le résultat. Retourne True si cette page a été affichée (l'appelant doit stopper)."""
    params = st.query_params
    if "payment" not in params or "uid" not in params:
        return False

    try:
        user_id = int(params["uid"])
    except (TypeError, ValueError):
        return False

    status = params["payment"]
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT last_checkout_id FROM users WHERE id = :uid"), {"uid": user_id}
        ).fetchone()

    st.title("📦 Paiement Wave")

    if not row or not row.last_checkout_id:
        st.error("Aucun paiement en cours trouvé pour ce compte.")
    elif status == "success":
        session = retrieve_checkout(row.last_checkout_id)
        if session.get("payment_status") == "succeeded":
            mark_user_paid(user_id)
            st.success("Paiement confirmé. Ton accès est débloqué !")
        else:
            st.warning(
                "Paiement pas encore confirmé côté Wave. Si tu viens de payer, "
                "patiente quelques secondes puis retourne à l'application."
            )
    else:
        st.error("Le paiement a été annulé ou a échoué. Tu peux réessayer depuis l'application.")

    if st.button("Retourner à l'application"):
        st.query_params.clear()
        st.rerun()
    return True


def paywall(user_id: int, amount: str = "15000", currency: str = "XOF") -> bool:
    """Affiche l'écran de paiement si l'utilisateur n'a pas encore payé.
    Retourne True si l'accès est bloqué (l'appelant doit stopper)."""
    if is_user_paid(user_id):
        return False

    st.title("🔒 Débloquer l'accès")
    st.write(f"Un paiement unique de **{amount} {currency}** te donne accès à ton gestionnaire de stock.")
    if st.button("Payer avec Wave"):
        session = create_checkout_session(user_id, amount, currency)
        st.link_button("Ouvrir Wave pour payer", session["wave_launch_url"])
        st.caption("Une fois le paiement effectué, tu seras redirigé automatiquement ici.")
    return True
