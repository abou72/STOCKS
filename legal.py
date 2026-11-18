"""
Confidentialité et données personnelles (Afrique de l'Ouest) :
- politique de confidentialité et d'utilisation des données, versionnée ;
- écran de consentement (inscription et chaque nouvelle version) ;
- page « Confidentialité & mes données » : lecture de la politique, export (accès / portabilité), suppression du compte.

Cadre de référence : loi ivoirienne n° 2013-450 du 19 juin 2013 (autorité : ARTCI) et Acte additionnel
A/SA.1/01/10 de la CEDEAO du 16 février 2010, ainsi que les lois nationales des autres pays de la zone.
Ce texte est un modèle de travail : à faire relire par un juriste avant mise en production.
"""
import io
import json
import os

import pandas as pd
import streamlit as st
from sqlalchemy import text

from security import (verify_password, verifier_blocage, enregistrer_echec, cle, TropDeTentatives)
from theme import hero, section, kpi_grid, esc

POLICY_VERSION = "2026-11-12"
POLICY_DATE = "12 novembre 2026"
SESSION_TIMEOUT_MIN = 60

A_RENSEIGNER = "[à renseigner]"


def _secret(key: str, defaut: str = A_RENSEIGNER) -> str:
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except FileNotFoundError:
        pass
    return os.environ.get(key) or defaut


def infos_editeur() -> dict:
    return {
        "editeur": _secret("LEGAL_EDITEUR"),
        "adresse": _secret("LEGAL_ADRESSE"),
        "email": _secret("LEGAL_CONTACT_EMAIL"),
        "hebergement": _secret("LEGAL_HEBERGEMENT"),
    }


def champs_legaux_incomplets() -> list[str]:
    return [k for k, v in infos_editeur().items() if v == A_RENSEIGNER]


def politique_markdown() -> str:
    i = infos_editeur()
    return f"""
*Version {POLICY_VERSION} — en vigueur depuis le {POLICY_DATE}*

### 1. Qui est responsable de tes données ?
**Éditeur de BizStock :** {i['editeur']} — {i['adresse']} — contact : **{i['email']}**.

- Pour les données de **ton compte** (email, nom de boutique, abonnement), l'éditeur est **responsable du traitement**.
- Pour les données de **ton activité** (produits, mouvements de stock, clients à crédit), **c'est toi, la boutique, le responsable du traitement**.
  L'éditeur agit comme **sous-traitant** : il les héberge et les traite uniquement pour te fournir le service, selon tes instructions.

### 2. Quelles données sont collectées ?
- **Compte :** email, nom de la boutique, mot de passe (conservé uniquement sous forme chiffrée irréversible), date d'inscription, date et version de ton consentement.
- **Activité :** produits, quantités, prix, mouvements de stock, et le cahier de crédit (nom du client, téléphone facultatif, montants, notes).
- **Abonnement :** référence, montant, statut et date des paiements. Les numéros de Mobile Money ou de carte sont traités par **GeniusPay** et ne sont **jamais** stockés par BizStock.
- **Sécurité :** compteurs de tentatives de connexion, stockés sous forme hachée (l'email n'y apparaît pas en clair) et effacés après 30 jours.

### 3. Pourquoi et sur quelle base ?
- Fournir le service et gérer ton abonnement (exécution du contrat).
- Protéger les comptes : blocage après échecs de connexion, prévention des abus (intérêt légitime de sécurité).
- Respecter nos obligations légales, notamment comptables (conservation des traces de paiement).
- Ton **consentement**, donné à l'inscription puis à chaque nouvelle version de ce document.

Nous **ne vendons pas** tes données, nous ne faisons **pas de publicité ciblée** et nous n'utilisons **aucun outil de mesure d'audience tiers**.

### 4. Qui y a accès ? Hébergement et transferts
Pour faire fonctionner BizStock, nous faisons appel à des prestataires techniques :
- **Hébergement de la base de données :** {i['hebergement']} ;
- **Hébergement de l'application** ;
- **GeniusPay** (paiement de l'abonnement) ;
- un prestataire d'envoi d'emails (réinitialisation du mot de passe).

Ces serveurs peuvent se trouver **hors de Côte d'Ivoire et hors de l'espace CEDEAO**. Un tel transfert est encadré par la loi applicable
(en Côte d'Ivoire : autorisation préalable de l'ARTCI, articles 7 et 26 de la loi n° 2013-450) et par les garanties de sécurité de nos prestataires.
Les polices de caractères et le logo sont servis par l'application elle-même : ton navigateur ne contacte aucun service tiers pour l'affichage.

### 5. Combien de temps ?
- **Compte actif :** tes données sont conservées tant que ton compte existe.
- **Suppression du compte :** tes données (compte, produits, mouvements, cahier de crédit) sont effacées immédiatement de la base active.
  Elles peuvent subsister quelque temps dans les sauvegardes techniques de l'hébergeur, jusqu'à leur rotation.
- **Traces de paiement :** conservées **sans lien avec ton identité** (référence, montant, date) pour nos obligations comptables.

### 6. Tes droits
Tu peux **accéder** à tes données, les **rectifier**, t'**opposer** à leur traitement, les **faire effacer**, en obtenir une **copie** (portabilité) et **retirer ton consentement**.
- **Dans l'application :** onglet « Confidentialité & mes données » (export Excel/JSON, suppression du compte).
- **Par email :** {i['email']}.

Si un de **tes clients à crédit** veut accéder à ses données, les corriger ou les faire effacer, il s'adresse à **ta boutique** : c'est toi qui peux modifier ou supprimer sa fiche dans le cahier de crédit.

### 7. Tes responsabilités envers tes clients (cahier de crédit)
- **Informe tes clients** que leur nom, leur numéro et le montant dû sont enregistrés dans ton cahier de crédit.
- N'enregistre que le **nécessaire** : nom, téléphone (facultatif), montants. N'écris **pas** de données sensibles (santé, religion, opinions…) dans les notes.
- Relance de façon **respectueuse** et **ne divulgue pas** la dette à des tiers.
- Si la loi de ton pays l'exige, **déclare** ton propre traitement auprès de l'autorité de protection des données.

### 8. Sécurité
Mots de passe chiffrés (bcrypt) ; blocage temporaire après 5 échecs de connexion ; requêtes protégées contre les injections ; isolation stricte entre boutiques ;
déconnexion automatique après {SESSION_TIMEOUT_MIN} minutes d'inactivité ; connexions chiffrées (HTTPS) fournies par l'hébergeur.
En cas de violation de données susceptible de te porter préjudice, nous t'informerons et nous préviendrons l'autorité compétente lorsque la loi l'exige.

### 9. Mineurs
BizStock s'adresse à des commerçants et professionnels majeurs.

### 10. Réclamation
Tu peux saisir l'autorité de protection des données de ton pays : **ARTCI** (Côte d'Ivoire), **CDP** (Sénégal), **CIL** (Burkina Faso),
**APDP** (Bénin, Mali), **IPDCP** (Togo), **HAPDP** (Niger)…
Cadre de référence : loi n° 2013-450 du 19 juin 2013 (Côte d'Ivoire), Acte additionnel A/SA.1/01/10 de la CEDEAO du 16 février 2010 et lois nationales applicables.

### 11. Modifications
Chaque nouvelle version de ce document te sera présentée et devra être acceptée pour continuer à utiliser l'application.
"""


def render_policy():
    st.markdown(politique_markdown())


# ----------------------------------------------------------------------
# Consentement
# ----------------------------------------------------------------------
def enregistrer_consentement(engine, user_id):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET consent_version = :v, consent_at = timezone('utc', now()) WHERE id = :u"),
            {"v": POLICY_VERSION, "u": user_id},
        )


def consentement_a_jour(user: dict) -> bool:
    return user.get("consent_version") == POLICY_VERSION


def ecran_consentement(engine, user: dict):
    hero("Tes données, tes droits", "Avant de continuer, lis et accepte la politique de confidentialité de BizStock.", badge="Confidentialité")
    with st.expander("📄 Lire la politique de confidentialité", expanded=True):
        render_policy()
    accepte = st.checkbox(
        f"J'ai lu et j'accepte la Politique de confidentialité et les conditions d'utilisation des données (version {POLICY_VERSION}).",
        key="consent_ok",
    )
    if st.button("Accepter et continuer", type="primary", disabled=not accepte):
        enregistrer_consentement(engine, user["id"])
        user["consent_version"] = POLICY_VERSION
        st.session_state["user"] = user
        st.rerun()


# ----------------------------------------------------------------------
# Export des données (accès / portabilité)
# ----------------------------------------------------------------------
def collecter_donnees(engine, user_id) -> dict[str, pd.DataFrame]:
    def lire(sql):
        return pd.read_sql_query(text(sql), engine, params={"u": user_id})

    return {
        "Compte": lire("SELECT email, nom_boutique, created_at, paid_until, consent_version, consent_at FROM users WHERE id = :u"),
        "Produits": lire("SELECT id, nom, categorie, quantite, prix_unitaire, seuil_alerte, derniere_maj FROM produits WHERE user_id = :u ORDER BY id"),
        "Mouvements": lire("SELECT id, date, produit_nom, type, quantite, motif FROM mouvements WHERE user_id = :u ORDER BY date"),
        "Clients credit": lire("SELECT id, nom, telephone, created_at FROM clients_credit WHERE user_id = :u ORDER BY id"),
        "Operations credit": lire("SELECT id, client_id, date, type, montant, note FROM credit_operations WHERE user_id = :u ORDER BY date"),
        "Paiements": lire("SELECT reference, amount, status, created_at FROM paiements_abonnement WHERE user_id = :u ORDER BY created_at"),
    }


def export_excel(donnees: dict[str, pd.DataFrame]) -> bytes:
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as writer:
        for nom, df in donnees.items():
            df.to_excel(writer, sheet_name=nom[:31], index=False)
    return tampon.getvalue()


def export_json(donnees: dict[str, pd.DataFrame]) -> bytes:
    contenu = {nom: json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False)) for nom, df in donnees.items()}
    return json.dumps(contenu, ensure_ascii=False, indent=2).encode("utf-8")


# ----------------------------------------------------------------------
# Suppression du compte (droit à l'effacement)
# ----------------------------------------------------------------------
def supprimer_compte(engine, user_id, mot_de_passe: str) -> tuple[bool, str]:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT email, password_hash, is_admin FROM users WHERE id = :u"), {"u": user_id}).fetchone()
    if not row:
        return False, "Compte introuvable."
    if row.is_admin:
        return False, "Un compte administrateur ne peut pas être supprimé depuis l'application."
    try:
        verifier_blocage("login", row.email)
    except TropDeTentatives as e:
        return False, f"Trop de tentatives. Réessaie dans {e.minutes} minute(s)."
    if not verify_password(mot_de_passe, row.password_hash):
        _, bloque = enregistrer_echec("login", row.email)
        return False, "Mot de passe incorrect." + (f" Accès bloqué pendant {bloque} minutes." if bloque else "")

    with engine.begin() as conn:
        conn.execute(text("UPDATE paiements_abonnement SET user_id = NULL WHERE user_id = :u"), {"u": user_id})
        conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})  # cascade : produits, mouvements, crédit
        conn.execute(
            text("DELETE FROM auth_throttle WHERE key IN (:a, :b, :c, :d)"),
            {"a": cle("login", row.email), "b": cle("resettoken", row.email), "c": cle("resetreq", row.email), "d": cle("signup", row.email)},
        )
    return True, ""


# ----------------------------------------------------------------------
# Page « Confidentialité & mes données »
# ----------------------------------------------------------------------
def page_confidentialite(engine, user_id: int, user: dict):
    hero("Confidentialité & mes données", "Lis la politique, récupère une copie de tes données ou supprime ton compte, quand tu veux.", badge="Tes droits")
    if user.get("is_admin") and champs_legaux_incomplets():
        st.warning("Administrateur : complète dans les secrets de l'app les champs "
                   + ", ".join(f"LEGAL_{k.upper() if k != 'email' else 'CONTACT_EMAIL'}" for k in champs_legaux_incomplets())
                   + " pour que la politique affiche tes vraies informations.")

    onglet_politique, onglet_export, onglet_suppr = st.tabs(["📄 Politique", "📦 Mes données", "🗑️ Supprimer mon compte"])

    with onglet_politique:
        render_policy()

    with onglet_export:
        st.write("Télécharge **tout ce que BizStock conserve** à ton sujet : compte, produits, mouvements, cahier de crédit et paiements. "
                 "Ton mot de passe et les jetons de sécurité n'en font pas partie.")
        donnees = collecter_donnees(engine, user_id)
        kpi_grid([
            {"label": nom, "value": str(len(df)), "tone": ton, "icon": ico, "sub": "ligne(s)"}
            for (nom, df), ton, ico in zip(
                [(n, d) for n, d in donnees.items() if n != "Compte"],
                ["mint", "lime", "amber", "coral", "teal"], ["📦", "🔁", "👥", "💳", "🧾"])
        ])
        c1, c2 = st.columns(2)
        c1.download_button("📥 Exporter en Excel", data=export_excel(donnees), file_name="mes_donnees_bizstock.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", key="export_xlsx")
        c2.download_button("📥 Exporter en JSON", data=export_json(donnees), file_name="mes_donnees_bizstock.json",
                           mime="application/json", key="export_json")

    with onglet_suppr:
        if user.get("is_admin"):
            st.info("Un compte administrateur ne peut pas être supprimé depuis l'application.")
        else:
            st.error("**Action définitive.** Ton compte, tes produits, tes mouvements et tout ton cahier de crédit seront effacés. "
                     "Les traces de paiement sont conservées sans lien avec ton identité (obligation comptable). "
                     "Ton abonnement en cours prend fin immédiatement ; pour toute question de remboursement, contacte-nous.")
            st.caption("Pense à exporter tes données avant de supprimer ton compte.")
            confirme = st.text_input("Pour confirmer, tape SUPPRIMER", key="suppr_confirm")
            mdp = st.text_input("Ton mot de passe", type="password", key="suppr_mdp")
            if st.button("Supprimer définitivement mon compte", key="suppr_btn", disabled=confirme.strip() != "SUPPRIMER" or not mdp):
                ok, message = supprimer_compte(engine, user_id, mdp)
                if ok:
                    st.session_state.clear()
                    st.session_state["compte_supprime"] = True
                    st.rerun()
                else:
                    st.error(message)
