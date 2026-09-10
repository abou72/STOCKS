"""
Gestionnaire de Stock - Application Streamlit (multi-utilisateurs)
Stockage des données sur Neon (PostgreSQL)
Export des rapports en PDF
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from sqlalchemy import text

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from db import get_engine, init_schema
from auth import login_form, logout_button, handle_password_reset_page
from payment import paywall, handle_payment_return

st.set_page_config(page_title="Gestion de Stock Boutique Samba", page_icon="📦", layout="wide")

# Prix d'accès unique — ajuste selon ton offre
PRIX_ACCES = "1000"
DEVISE_ACCES = "XOF"

init_schema()

if handle_password_reset_page():
    st.stop()

if handle_payment_return():
    st.stop()

if not login_form():
    st.stop()

logout_button()
user_id = st.session_state["user"]["id"]
est_admin = st.session_state["user"].get("is_admin", False)
engine = get_engine()

if not est_admin and paywall(user_id, amount=PRIX_ACCES, currency=DEVISE_ACCES):
    st.stop()


# ----------------------------------------------------------------------
# FONCTIONS DE GESTION DES DONNEES (Neon / PostgreSQL, filtrées par utilisateur)
# ----------------------------------------------------------------------
def charger_stock() -> pd.DataFrame:
    return pd.read_sql_query(
        text("SELECT * FROM produits WHERE user_id = :uid ORDER BY id"),
        engine, params={"uid": user_id}
    )


def charger_mouvements() -> pd.DataFrame:
    return pd.read_sql_query(
        text("SELECT * FROM mouvements WHERE user_id = :uid ORDER BY date DESC"),
        engine, params={"uid": user_id}
    )


def ajouter_produit(nom, categorie, quantite, prix, seuil):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO produits (user_id, nom, categorie, quantite, prix_unitaire, seuil_alerte, derniere_maj)
            VALUES (:uid, :nom, :cat, :qte, :prix, :seuil, :maj)
        """), {"uid": user_id, "nom": nom, "cat": categorie, "qte": quantite,
               "prix": prix, "seuil": seuil, "maj": datetime.now()})


def modifier_quantite(produit_id, nouvelle_quantite):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE produits SET quantite = :qte, derniere_maj = :maj
            WHERE id = :pid AND user_id = :uid
        """), {"qte": nouvelle_quantite, "maj": datetime.now(), "pid": produit_id, "uid": user_id})


def supprimer_produit(produit_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM produits WHERE id = :pid AND user_id = :uid"),
                      {"pid": produit_id, "uid": user_id})


def enregistrer_mouvement(produit_id, produit_nom, type_mvt, quantite, motif):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO mouvements (user_id, date, produit_id, produit_nom, type, quantite, motif)
            VALUES (:uid, :date, :pid, :nom, :type, :qte, :motif)
        """), {"uid": user_id, "date": datetime.now(), "pid": produit_id,
               "nom": produit_nom, "type": type_mvt, "qte": quantite, "motif": motif})


# ----------------------------------------------------------------------
# GENERATION PDF
# ----------------------------------------------------------------------
def generer_pdf_stock(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Rapport d'inventaire", styles["Title"]))
    elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    valeur_totale = (df["quantite"] * df["prix_unitaire"]).sum() if not df.empty else 0
    elements.append(Paragraph(f"Nombre de produits : {len(df)}", styles["Normal"]))
    elements.append(Paragraph(f"Valeur totale du stock : {valeur_totale:,.0f} FCFA", styles["Normal"]))
    elements.append(Spacer(1, 20))

    data = [["Nom", "Catégorie", "Quantité", "Prix unitaire", "Seuil", "Statut"]]
    for _, ligne in df.iterrows():
        statut = "Bas" if ligne["quantite"] <= ligne["seuil_alerte"] else "OK"
        data.append([
            ligne["nom"], ligne["categorie"], str(int(ligne["quantite"])),
            f"{ligne['prix_unitaire']:,.0f}", str(int(ligne["seuil_alerte"])), statut
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("ALIGN", (2, 0), (4, -1), "CENTER"),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generer_pdf_mouvements(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Historique des mouvements de stock", styles["Title"]))
    elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    data = [["Date", "Produit", "Type", "Quantité", "Motif"]]
    for _, ligne in df.iterrows():
        date_aff = str(ligne["date"])[:16].replace("T", " ")
        data.append([date_aff, ligne["produit_nom"], ligne["type"], str(int(ligne["quantite"])), ligne["motif"] or ""])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ----------------------------------------------------------------------
# NAVIGATION
# ----------------------------------------------------------------------
st.sidebar.title("📦 Gestion de Stock")
page = st.sidebar.radio(
    "Menu",
    ["Tableau de bord", "Ajouter un produit", "Entrée / Sortie de stock",
     "Liste des produits", "Historique des mouvements"]
)

stock = charger_stock()

# ----------------------------------------------------------------------
# PAGE : TABLEAU DE BORD
# ----------------------------------------------------------------------
if page == "Tableau de bord":
    nom_boutique = st.session_state["user"].get("nom_boutique") or "Ma boutique"
    st.title(f"Tableau de bord — {nom_boutique}")

    if stock.empty:
        st.info("Aucun produit enregistré pour le moment. Ajoute ton premier produit dans le menu à gauche.")
    else:
        nb_produits = len(stock)
        valeur_totale = (stock["quantite"] * stock["prix_unitaire"]).sum()
        produits_alerte = stock[stock["quantite"] <= stock["seuil_alerte"]]

        col1, col2, col3 = st.columns(3)
        col1.metric("Nombre de produits", nb_produits)
        col2.metric("Valeur totale du stock", f"{valeur_totale:,.0f} FCFA")
        col3.metric("Produits en alerte", len(produits_alerte))

        st.subheader("Quantité en stock par catégorie")
        par_categorie = stock.groupby("categorie")["quantite"].sum()
        st.bar_chart(par_categorie)

        if not produits_alerte.empty:
            st.subheader("⚠️ Produits à réapprovisionner")
            st.dataframe(produits_alerte, use_container_width=True)

        st.divider()
        st.subheader("📄 Export PDF")
        pdf_bytes = generer_pdf_stock(stock)
        st.download_button(
            "Télécharger le rapport d'inventaire (PDF)",
            data=pdf_bytes,
            file_name=f"rapport_stock_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf"
        )

# ----------------------------------------------------------------------
# PAGE : AJOUTER UN PRODUIT
# ----------------------------------------------------------------------
elif page == "Ajouter un produit":
    st.title("Ajouter un nouveau produit")

    with st.form("form_ajout"):
        nom = st.text_input("Nom du produit")
        categorie = st.text_input("Catégorie")
        quantite = st.number_input("Quantité initiale", min_value=0, step=1)
        prix = st.number_input("Prix unitaire (FCFA)", min_value=0.0, step=100.0)
        seuil = st.number_input("Seuil d'alerte (stock bas)", min_value=0, step=1, value=5)
        valider = st.form_submit_button("Ajouter le produit")

        if valider:
            if not nom.strip():
                st.error("Le nom du produit est obligatoire.")
            else:
                ajouter_produit(nom.strip(), categorie.strip() if categorie else "Non classé", quantite, prix, seuil)
                st.success(f"Produit '{nom}' ajouté avec succès.")
                st.rerun()

# ----------------------------------------------------------------------
# PAGE : ENTREE / SORTIE DE STOCK
# ----------------------------------------------------------------------
elif page == "Entrée / Sortie de stock":
    st.title("Mouvement de stock")

    if stock.empty:
        st.warning("Ajoute d'abord des produits avant d'enregistrer un mouvement.")
    else:
        stock["label"] = stock["id"].astype(str) + " - " + stock["nom"]
        choix = st.selectbox("Choisir un produit", stock["label"])
        produit_id = int(choix.split(" - ")[0])
        ligne = stock[stock["id"] == produit_id].iloc[0]

        st.write(f"Stock actuel : **{int(ligne['quantite'])}** unité(s)")

        type_mvt = st.radio("Type de mouvement", ["Entrée (réapprovisionnement)", "Sortie (vente)"])
        quantite_mvt = st.number_input("Quantité", min_value=1, step=1)
        motif = st.text_input("Motif / commentaire (optionnel)")

        if st.button("Valider le mouvement"):
            if "Entrée" in type_mvt:
                nouvelle_quantite = int(ligne["quantite"]) + quantite_mvt
                modifier_quantite(produit_id, nouvelle_quantite)
                enregistrer_mouvement(produit_id, ligne["nom"], "Entrée", quantite_mvt, motif)
                st.success(f"{quantite_mvt} unité(s) ajoutée(s) au stock de '{ligne['nom']}'.")
            else:
                if quantite_mvt > ligne["quantite"]:
                    st.error("Quantité insuffisante en stock pour cette sortie.")
                    st.stop()
                nouvelle_quantite = int(ligne["quantite"]) - quantite_mvt
                modifier_quantite(produit_id, nouvelle_quantite)
                enregistrer_mouvement(produit_id, ligne["nom"], "Sortie", quantite_mvt, motif)
                st.success(f"{quantite_mvt} unité(s) retirée(s) du stock de '{ligne['nom']}'.")

            st.rerun()

# ----------------------------------------------------------------------
# PAGE : LISTE DES PRODUITS
# ----------------------------------------------------------------------
elif page == "Liste des produits":
    st.title("Liste des produits")

    if stock.empty:
        st.info("Aucun produit enregistré.")
    else:
        recherche = st.text_input("🔍 Rechercher un produit (nom ou catégorie)")
        affichage = stock.copy()
        if recherche:
            masque = (
                affichage["nom"].str.contains(recherche, case=False, na=False)
                | affichage["categorie"].str.contains(recherche, case=False, na=False)
            )
            affichage = affichage[masque]

        st.dataframe(affichage.drop(columns=["label"], errors="ignore"), use_container_width=True)

        st.subheader("Supprimer un produit")
        if not affichage.empty:
            affichage["label"] = affichage["id"].astype(str) + " - " + affichage["nom"]
            a_supprimer = st.selectbox("Choisir un produit à supprimer", affichage["label"])
            if st.button("🗑️ Supprimer", type="secondary"):
                id_a_supprimer = int(a_supprimer.split(" - ")[0])
                supprimer_produit(id_a_supprimer)
                st.success("Produit supprimé.")
                st.rerun()

# ----------------------------------------------------------------------
# PAGE : HISTORIQUE DES MOUVEMENTS
# ----------------------------------------------------------------------
elif page == "Historique des mouvements":
    st.title("Historique des mouvements de stock")

    mouvements = charger_mouvements()
    if mouvements.empty:
        st.info("Aucun mouvement enregistré pour le moment.")
    else:
        st.dataframe(mouvements, use_container_width=True)

        st.divider()
        pdf_bytes = generer_pdf_mouvements(mouvements)
        st.download_button(
            "Télécharger l'historique (PDF)",
            data=pdf_bytes,
            file_name=f"mouvements_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf"
        )