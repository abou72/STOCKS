"""
Abonnement mensuel via GeniusPay (page de checkout hébergée : Wave, Orange Money, MTN, Moov, carte).

Flux :
1. L'utilisateur connecté dont l'abonnement est expiré voit l'écran « Débloquer l'accès ».
2. On crée un paiement GeniusPay (POST /payments) et on enregistre sa référence (MTX-...).
3. L'utilisateur paie sur la page GeniusPay, puis est redirigé vers success_url / error_url.
4. On interroge GeniusPay (GET /payments/{reference}) : jamais de confiance dans la seule redirection.
   Si le statut est « completed », l'accès est prolongé de 30 jours — une seule fois par paiement.

Streamlit ne peut pas recevoir de webhook : la vérification se fait donc au retour de l'utilisateur.

Secrets nécessaires : GENIUSPAY_API_KEY (pk_...), GENIUSPAY_API_SECRET (sk_...), APP_URL.
Optionnel : GENIUSPAY_BASE_URL (pour pointer vers un serveur de test).
"""
import os
from urllib.parse import quote

import requests
import streamlit as st
from sqlalchemy import text

from db import get_engine
from theme import hero, esc, fcfa, TONES

PRIX_ABONNEMENT = 5000      # FCFA par mois (minimum GeniusPay : 200)
DUREE_JOURS = 30
DEVISE = "XOF"
GENIUSPAY_BASE_DEFAULT = "https://geniuspay.ci/api/v1/merchant"
NOW_UTC = "timezone('utc', now())"


class PaiementError(Exception):
    pass


def _get_secret(key: str):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except FileNotFoundError:
        pass
    return os.environ.get(key)


def _base_url() -> str:
    return (_get_secret("GENIUSPAY_BASE_URL") or GENIUSPAY_BASE_DEFAULT).rstrip("/")


def _headers() -> dict:
    cle, secret = _get_secret("GENIUSPAY_API_KEY"), _get_secret("GENIUSPAY_API_SECRET")
    if not cle or not secret:
        raise PaiementError(
            "Clés GeniusPay manquantes. Ajoute GENIUSPAY_API_KEY et GENIUSPAY_API_SECRET dans les secrets de l'application."
        )
    return {
        "X-API-Key": cle,
        "X-API-Secret": secret,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "GestionStock/1.0",
    }


def _appeler(methode: str, chemin: str, **kwargs) -> dict:
    try:
        resp = requests.request(methode, f"{_base_url()}{chemin}", headers=_headers(), timeout=15, **kwargs)
    except requests.RequestException as e:
        raise PaiementError(f"Impossible de joindre GeniusPay : {e}")
    try:
        corps = resp.json()
    except ValueError:
        corps = {}
    if resp.status_code >= 400 or not corps.get("success"):
        message = (corps.get("error") or {}).get("message") or f"Réponse inattendue de GeniusPay (HTTP {resp.status_code})."
        raise PaiementError(message)
    return corps["data"]


# ----------------------------------------------------------------------
# Abonnement
# ----------------------------------------------------------------------
def abonnement_info(user_id: int) -> dict:
    """Retourne {'actif': bool, 'paid_until': datetime|None, 'jours': int}."""
    with get_engine().connect() as conn:
        row = conn.execute(
            text(f"SELECT paid_until, (paid_until IS NOT NULL AND paid_until > {NOW_UTC}) AS actif, "
                 f"CASE WHEN paid_until IS NULL THEN 0 ELSE CEIL(EXTRACT(EPOCH FROM (paid_until - {NOW_UTC})) / 86400.0) END AS jours "
                 "FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).fetchone()
    if not row:
        return {"actif": False, "paid_until": None, "jours": 0}
    return {"actif": bool(row.actif), "paid_until": row.paid_until, "jours": max(int(row.jours or 0), 0)}


def is_user_paid(user_id: int) -> bool:
    return abonnement_info(user_id)["actif"]


def creer_paiement(user_id: int, email: str, nom_boutique: str) -> str:
    """Crée le paiement GeniusPay et retourne l'URL de checkout."""
    app_url = (_get_secret("APP_URL") or "http://localhost:8501").rstrip("/")
    payload = {
        "amount": PRIX_ABONNEMENT,
        "currency": DEVISE,
        "description": f"Abonnement Gestion de Stock — {DUREE_JOURS} jours",
        "customer": {"name": nom_boutique or email, "email": email},
        "success_url": f"{app_url}?payment=success&uid={user_id}",
        "error_url": f"{app_url}?payment=error&uid={user_id}",
        "metadata": {"user_id": str(user_id), "plan": "monthly"},
    }
    data = _appeler("POST", "/payments", json=payload)
    url = data.get("checkout_url") or data.get("payment_url")
    reference = data.get("reference")
    if not url or not reference:
        raise PaiementError("GeniusPay n'a pas renvoyé de lien de paiement.")
    with get_engine().begin() as conn:
        conn.execute(
            text("INSERT INTO paiements_abonnement (reference, user_id, amount, status) VALUES (:r, :u, :a, 'pending')"),
            {"r": reference, "u": user_id, "a": PRIX_ABONNEMENT},
        )
    return url


def verifier_et_crediter(reference: str, user_id: int) -> str:
    """Interroge GeniusPay. Retourne le statut ('completed', 'pending', 'failed'...).
    Si le paiement est « completed » et pas encore crédité, prolonge l'abonnement (atomique, une seule fois)."""
    data = _appeler("GET", f"/payments/{quote(reference, safe='')}")
    statut = str(data.get("status") or "pending")
    meta_uid = (data.get("metadata") or {}).get("user_id")
    if meta_uid is not None and str(meta_uid) != str(user_id):
        raise PaiementError("Ce paiement n'appartient pas à ce compte.")

    engine = get_engine()
    if statut == "completed":
        if float(data.get("amount") or 0) < PRIX_ABONNEMENT:
            raise PaiementError("Le montant payé est inférieur au prix de l'abonnement.")
        with engine.begin() as conn:
            row = conn.execute(
                text("UPDATE paiements_abonnement SET status = 'completed', credited = TRUE "
                     "WHERE reference = :r AND user_id = :u AND credited = FALSE RETURNING user_id"),
                {"r": reference, "u": user_id},
            ).fetchone()
            if row:
                conn.execute(
                    text(f"UPDATE users SET has_paid = TRUE, "
                         f"paid_until = GREATEST(COALESCE(paid_until, {NOW_UTC}), {NOW_UTC}) + (:j * INTERVAL '1 day') "
                         "WHERE id = :u"),
                    {"j": DUREE_JOURS, "u": user_id},
                )
    else:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE paiements_abonnement SET status = :s WHERE reference = :r AND user_id = :u AND credited = FALSE"),
                {"s": statut, "r": reference, "u": user_id},
            )
    return statut


def _dernier_paiement(user_id: int):
    with get_engine().connect() as conn:
        return conn.execute(
            text("SELECT reference, credited, status FROM paiements_abonnement WHERE user_id = :u "
                 "ORDER BY created_at DESC LIMIT 1"),
            {"u": user_id},
        ).fetchone()


def _fmt_date(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


# ----------------------------------------------------------------------
# Écrans
# ----------------------------------------------------------------------
def handle_payment_return() -> bool:
    """Si l'URL contient payment=success/error&uid=..., vérifie le paiement et affiche le résultat.
    Retourne True si cette page a été affichée (l'appelant doit stopper)."""
    params = st.query_params
    if "payment" not in params or "uid" not in params:
        return False
    try:
        user_id = int(params["uid"])
    except (TypeError, ValueError):
        return False

    hero("Paiement GeniusPay", "Vérification de ton paiement en cours…", badge="Abonnement")
    dernier = _dernier_paiement(user_id)

    if not dernier:
        st.error("Aucun paiement en cours trouvé pour ce compte.")
    elif params["payment"] != "success":
        st.error("Le paiement a été annulé ou a échoué. Tu peux réessayer depuis l'application.")
    elif dernier.credited:
        info = abonnement_info(user_id)
        st.success(f"Paiement confirmé. Ton abonnement est actif jusqu'au {_fmt_date(info['paid_until'])}.")
    else:
        try:
            statut = verifier_et_crediter(dernier.reference, user_id)
        except PaiementError as e:
            st.error(str(e))
        else:
            if statut == "completed":
                info = abonnement_info(user_id)
                st.success(f"Paiement confirmé. Ton abonnement est actif jusqu'au {_fmt_date(info['paid_until'])}.")
            elif statut in ("pending", "processing"):
                st.warning("Paiement pas encore confirmé. Si tu viens de payer, patiente quelques secondes puis vérifie à nouveau.")
                if st.button("Vérifier à nouveau", type="primary"):
                    st.rerun()
            else:
                st.error("Le paiement n'a pas abouti. Tu peux réessayer depuis l'application.")

    if st.button("Retourner à l'application"):
        st.query_params.clear()
        st.rerun()
    return True


def _bouton_paiement(user_id: int, email: str, nom_boutique: str, libelle: str, cle: str):
    if st.button(libelle, type="primary", key=cle):
        try:
            url = creer_paiement(user_id, email, nom_boutique)
        except PaiementError as e:
            st.error(str(e))
        else:
            st.link_button("Ouvrir la page de paiement GeniusPay", url, type="primary")
            st.caption("Après le paiement, tu es redirigé automatiquement ici pour débloquer ton accès.")


def paywall(user_id: int, email: str, nom_boutique: str) -> bool:
    """Affiche l'écran d'abonnement si l'accès n'est pas actif. Retourne True si l'accès est bloqué."""
    info = abonnement_info(user_id)
    if info["actif"]:
        return False

    hero("Débloquer l'accès", "Un abonnement mensuel pour gérer ton stock et ton cahier de crédit, partout, depuis ton téléphone.", badge="Abonnement")
    if info["paid_until"]:
        st.warning(f"Ton abonnement a expiré le {_fmt_date(info['paid_until'])}. Renouvelle-le pour retrouver ton accès.")

    st.markdown(
        f'<div class="pay-card"><div class="price">{esc(fcfa(PRIX_ABONNEMENT))}</div>'
        f'<div class="per">par mois · {DUREE_JOURS} jours d\'accès</div>'
        '<ul><li>Stock, mouvements et alertes de réapprovisionnement</li>'
        '<li>Cahier de crédit avec relances WhatsApp</li>'
        '<li>Rapports PDF</li>'
        '<li>Paiement par Wave, Orange Money, MTN, Moov ou carte</li></ul></div>',
        unsafe_allow_html=True,
    )
    _, centre, _ = st.columns([1, 2, 1])
    with centre:
        _bouton_paiement(user_id, email, nom_boutique, "Payer avec GeniusPay", "pay_main")
    return True


def renouveler_sidebar(user: dict):
    """Dans la barre latérale : jours restants et bouton de renouvellement quand il reste 5 jours ou moins."""
    info = abonnement_info(user["id"])
    if not info["actif"]:
        return
    c = TONES["amber"] if info["jours"] <= 5 else TONES["mint"]
    st.markdown(
        f'<span class="pill" style="--c:{c}">Abonnement · {info["jours"]} j restants</span>',
        unsafe_allow_html=True,
    )
    if info["jours"] <= 5:
        _bouton_paiement(user["id"], user["email"], user.get("nom_boutique"), "Renouveler (+30 jours)", "pay_renew")
