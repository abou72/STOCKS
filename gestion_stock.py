"""
Gestionnaire de Stock - Application Streamlit (multi-utilisateurs)
Stockage sur Neon (PostgreSQL) · Abonnement mensuel via GeniusPay · Cahier de crédit · Export PDF
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
from payment import paywall, handle_payment_return, renouveler_sidebar
from credit import page_credit, lister_clients
from theme import (inject_theme, hero, section, kpi_grid, row_card_html, render_rows,
                   show_flash, flash, esc, fcfa, TONES)

st.set_page_config(page_title="Gestion de Stock Boutique Samba", page_icon="📦", layout="wide")
inject_theme()

init_schema()

if handle_password_reset_page():
    st.stop()

if handle_payment_return():
    st.stop()

if not login_form():
    st.stop()

user = st.session_state["user"]
user_id = user["id"]
est_admin = user.get("is_admin", False)
nom_boutique = user.get("nom_boutique") or "Ma boutique"
engine = get_engine()

with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="logo">◈</div>'
        f'<div><div class="t">Gestion de Stock</div><div class="s">{esc(nom_boutique)}</div></div></div>',
        unsafe_allow_html=True,
    )
logout_button()

if not est_admin and paywall(user_id, user["email"], user.get("nom_boutique")):
    st.stop()

with st.sidebar:
    if est_admin:
        st.markdown(f'<span class="pill" style="--c:{TONES["lime"]}">👑 Accès admin</span>', unsafe_allow_html=True)
    else:
        renouveler_sidebar(user)
    st.divider()


# ----------------------------------------------------------------------
# FONCTIONS DE GESTION DES DONNEES (Neon / PostgreSQL, filtrées par utilisateur)
# ----------------------------------------------------------------------
def charger_stock() -> pd.DataFrame:
    df = pd.read_sql_query(
        text("SELECT * FROM produits WHERE user_id = :uid ORDER BY id"),
        engine, params={"uid": user_id}
    )
    df["prix_unitaire"] = df["prix_unitaire"].astype(float)
    return df


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
COULEUR_ENTETE_PDF = colors.HexColor("#0B3D2E")


def generer_pdf_stock(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Rapport d'inventaire — {nom_boutique}", styles["Title"]))
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
        ("BACKGROUND", (0, 0), (-1, 0), COULEUR_ENTETE_PDF),
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

    elements.append(Paragraph(f"Historique des mouvements de stock — {nom_boutique}", styles["Title"]))
    elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    data = [["Date", "Produit", "Type", "Quantité", "Motif"]]
    for _, ligne in df.iterrows():
        date_aff = str(ligne["date"])[:16].replace("T", " ")
        data.append([date_aff, ligne["produit_nom"], ligne["type"], str(int(ligne["quantite"])), ligne["motif"] or ""])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COULEUR_ENTETE_PDF),
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
PAGES = [
    "📊 Tableau de bord",
    "💳 Cahier de crédit",
    "➕ Ajouter un produit",
    "🔁 Entrée / Sortie de stock",
    "📦 Liste des produits",
    "🕘 Historique des mouvements",
]
page = st.sidebar.radio("Menu", PAGES, label_visibility="collapsed")

stock = charger_stock()

# ----------------------------------------------------------------------
# PAGE : TABLEAU DE BORD
# ----------------------------------------------------------------------
if page == PAGES[0]:
    hero(f"Tableau de bord — {nom_boutique}", "Ton stock, tes alertes et tes crédits clients en un coup d'œil.", badge="En direct")
    show_flash()

    clients = lister_clients(engine, user_id)
    total_credit = float(clients.loc[clients["solde"] > 0, "solde"].sum()) if not clients.empty else 0.0

    if stock.empty:
        kpi_grid([
            {"label": "Produits", "value": "0", "tone": "mint"},
            {"label": "Valeur du stock", "value": fcfa(0), "tone": "lime"},
            {"label": "Alertes", "value": "0", "tone": "amber"},
            {"label": "Crédits à recouvrer", "value": fcfa(total_credit), "tone": "coral"},
        ])
        st.info("Aucun produit enregistré pour le moment. Ajoute ton premier produit dans le menu à gauche.")
    else:
        valeur_totale = float((stock["quantite"] * stock["prix_unitaire"]).sum())
        produits_alerte = stock[stock["quantite"] <= stock["seuil_alerte"]]
        kpi_grid([
            {"label": "Produits", "value": str(len(stock)), "tone": "mint", "sub": f"{int(stock['quantite'].sum())} unités en stock"},
            {"label": "Valeur du stock", "value": fcfa(valeur_totale), "tone": "lime", "sub": "au prix de vente"},
            {"label": "Alertes", "value": str(len(produits_alerte)), "tone": "amber", "sub": "à réapprovisionner"},
            {"label": "Crédits à recouvrer", "value": fcfa(total_credit), "tone": "coral", "sub": f"{int((clients['solde'] > 0).sum()) if not clients.empty else 0} client(s)"},
        ])

        gauche, droite = st.columns([3, 2], gap="large")
        with gauche:
            section("Quantité en stock par catégorie")
            par_categorie = stock.groupby("categorie")["quantite"].sum()
            try:
                st.bar_chart(par_categorie, color="#00F5A0")
            except TypeError:  # anciennes versions de Streamlit sans paramètre color
                st.bar_chart(par_categorie)
        with droite:
            section("À réapprovisionner")
            if produits_alerte.empty:
                st.caption("Rien à signaler, tous les stocks sont au-dessus du seuil.")
            else:
                render_rows([
                    row_card_html(p["nom"], f"seuil : {int(p['seuil_alerte'])}", f"{int(p['quantite'])} restant(s)",
                                  "coral" if p["quantite"] == 0 else "amber")
                    for _, p in produits_alerte.head(6).iterrows()
                ])
            if not clients.empty and total_credit > 0:
                section("Top débiteurs")
                render_rows([
                    row_card_html(c["nom"], c["telephone"] or "—", fcfa(c["solde"]), "coral")
                    for _, c in clients[clients["solde"] > 0].head(4).iterrows()
                ])

        st.divider()
        st.download_button(
            "📄 Télécharger le rapport d'inventaire (PDF)",
            data=generer_pdf_stock(stock),
            file_name=f"rapport_stock_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            type="primary",
        )

# ----------------------------------------------------------------------
# PAGE : CAHIER DE CREDIT
# ----------------------------------------------------------------------
elif page == PAGES[1]:
    page_credit(engine, user_id, stock, nom_boutique)

# ----------------------------------------------------------------------
# PAGE : AJOUTER UN PRODUIT
# ----------------------------------------------------------------------
elif page == PAGES[2]:
    hero("Ajouter un produit", "Renseigne le produit, son prix et le seuil qui déclenche l'alerte.")
    show_flash()

    with st.form("form_ajout"):
        nom = st.text_input("Nom du produit")
        categorie = st.text_input("Catégorie")
        quantite = st.number_input("Quantité initiale", min_value=0, step=1)
        prix = st.number_input("Prix unitaire (FCFA)", min_value=0.0, step=100.0)
        seuil = st.number_input("Seuil d'alerte (stock bas)", min_value=0, step=1, value=5)
        valider = st.form_submit_button("Ajouter le produit", type="primary")

        if valider:
            if not nom.strip():
                st.error("Le nom du produit est obligatoire.")
            else:
                ajouter_produit(nom.strip(), categorie.strip() if categorie else "Non classé", quantite, prix, seuil)
                flash(f"Produit « {nom.strip()} » ajouté avec succès.")
                st.rerun()

# ----------------------------------------------------------------------
# PAGE : ENTREE / SORTIE DE STOCK
# ----------------------------------------------------------------------
elif page == PAGES[3]:
    hero("Mouvement de stock", "Enregistre un réapprovisionnement ou une vente.")
    show_flash()

    if stock.empty:
        st.warning("Ajoute d'abord des produits avant d'enregistrer un mouvement.")
    else:
        stock["label"] = stock["id"].astype(str) + " - " + stock["nom"]
        choix = st.selectbox("Choisir un produit", stock["label"])
        produit_id = int(choix.split(" - ")[0])
        ligne = stock[stock["id"] == produit_id].iloc[0]

        st.write(f"Stock actuel : **{int(ligne['quantite'])}** unité(s)")

        type_mvt = st.radio("Type de mouvement", ["Entrée (réapprovisionnement)", "Sortie (vente)"], horizontal=True)
        quantite_mvt = st.number_input("Quantité", min_value=1, step=1)
        motif = st.text_input("Motif / commentaire (optionnel)")

        if st.button("Valider le mouvement", type="primary"):
            if "Entrée" in type_mvt:
                nouvelle_quantite = int(ligne["quantite"]) + quantite_mvt
                modifier_quantite(produit_id, nouvelle_quantite)
                enregistrer_mouvement(produit_id, ligne["nom"], "Entrée", quantite_mvt, motif)
                flash(f"{quantite_mvt} unité(s) ajoutée(s) au stock de « {ligne['nom']} ».")
            else:
                if quantite_mvt > ligne["quantite"]:
                    st.error("Quantité insuffisante en stock pour cette sortie.")
                    st.stop()
                nouvelle_quantite = int(ligne["quantite"]) - quantite_mvt
                modifier_quantite(produit_id, nouvelle_quantite)
                enregistrer_mouvement(produit_id, ligne["nom"], "Sortie", quantite_mvt, motif)
                flash(f"{quantite_mvt} unité(s) retirée(s) du stock de « {ligne['nom']} ».")

            st.rerun()

# ----------------------------------------------------------------------
# PAGE : LISTE DES PRODUITS
# ----------------------------------------------------------------------
elif page == PAGES[4]:
    hero("Liste des produits", "Recherche, consulte et supprime tes produits.")
    show_flash()

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

        colonnes = {"id": "ID", "nom": "Produit", "categorie": "Catégorie", "quantite": "Quantité",
                    "prix_unitaire": "Prix unitaire", "seuil_alerte": "Seuil", "derniere_maj": "Dernière MAJ"}
        st.dataframe(affichage[list(colonnes)].rename(columns=colonnes), hide_index=True)

        section("Supprimer un produit")
        if not affichage.empty:
            affichage["label"] = affichage["id"].astype(str) + " - " + affichage["nom"]
            a_supprimer = st.selectbox("Choisir un produit à supprimer", affichage["label"])
            if st.checkbox("Je confirme la suppression de ce produit", key="confirm_suppr_produit"):
                if st.button("🗑️ Supprimer"):
                    supprimer_produit(int(a_supprimer.split(" - ")[0]))
                    st.session_state.pop("confirm_suppr_produit", None)
                    flash("Produit supprimé.")
                    st.rerun()

# ----------------------------------------------------------------------
# PAGE : HISTORIQUE DES MOUVEMENTS
# ----------------------------------------------------------------------
elif page == PAGES[5]:
    hero("Historique des mouvements", "Toutes les entrées et sorties de stock, de la plus récente à la plus ancienne.")
    show_flash()

    mouvements = charger_mouvements()
    if mouvements.empty:
        st.info("Aucun mouvement enregistré pour le moment.")
    else:
        colonnes = {"date": "Date", "produit_nom": "Produit", "type": "Type", "quantite": "Quantité", "motif": "Motif"}
        st.dataframe(mouvements[list(colonnes)].rename(columns=colonnes), hide_index=True)

        st.divider()
        st.download_button(
            "📄 Télécharger l'historique (PDF)",
            data=generer_pdf_mouvements(mouvements),
            file_name=f"mouvements_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            type="primary",
        )
