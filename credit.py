"""
Cahier de crédit : dettes des clients, remboursements, relances WhatsApp et relevé PDF.
Toutes les requêtes sont filtrées par user_id (chaque boutique ne voit que ses clients).
"""
import re
from datetime import datetime
from io import BytesIO
from urllib.parse import quote

import pandas as pd
import streamlit as st
from sqlalchemy import text

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from theme import (hero, section, kpi_grid, row_card_html, render_rows, show_flash, flash, esc, fcfa)


# ----------------------------------------------------------------------
# DONNEES
# ----------------------------------------------------------------------
def lister_clients(engine, user_id) -> pd.DataFrame:
    df = pd.read_sql_query(text("""
        SELECT c.id, c.nom, c.telephone,
               COALESCE(SUM(CASE WHEN o.type = 'dette' THEN o.montant END), 0) AS total_dettes,
               COALESCE(SUM(CASE WHEN o.type = 'remboursement' THEN o.montant END), 0) AS total_rembourse,
               COALESCE(SUM(CASE WHEN o.type = 'dette' THEN o.montant ELSE -o.montant END), 0) AS solde,
               MAX(o.date) AS derniere_op
        FROM clients_credit c
        LEFT JOIN credit_operations o ON o.client_id = c.id AND o.user_id = c.user_id
        WHERE c.user_id = :uid
        GROUP BY c.id, c.nom, c.telephone
        ORDER BY solde DESC, c.nom
    """), engine, params={"uid": user_id})
    for col in ("total_dettes", "total_rembourse", "solde"):
        df[col] = df[col].astype(float)
    return df


def ajouter_client(engine, user_id, nom, telephone) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text("INSERT INTO clients_credit (user_id, nom, telephone) VALUES (:u, :n, :t) RETURNING id"),
            {"u": user_id, "n": nom, "t": telephone or None},
        ).scalar()


def enregistrer_operation(engine, user_id, client_id, type_op, montant, note="", produit_id=None, quantite=None):
    """Enregistre une dette ou un remboursement. Lève ValueError avec un message lisible si impossible.
    Une dette liée à un produit retire aussi la quantité du stock (mouvement « Sortie »), dans la même transaction."""
    if montant <= 0:
        raise ValueError("Le montant doit être supérieur à 0.")
    with engine.begin() as conn:
        client = conn.execute(
            text("SELECT id, nom FROM clients_credit WHERE id = :c AND user_id = :u FOR UPDATE"),
            {"c": client_id, "u": user_id},
        ).fetchone()
        if not client:
            raise ValueError("Client introuvable.")

        if type_op == "remboursement":
            solde = conn.execute(
                text("SELECT COALESCE(SUM(CASE WHEN type = 'dette' THEN montant ELSE -montant END), 0) "
                     "FROM credit_operations WHERE client_id = :c AND user_id = :u"),
                {"c": client_id, "u": user_id},
            ).scalar()
            if montant > float(solde):
                raise ValueError(f"Le remboursement ({fcfa(montant)}) dépasse le solde dû ({fcfa(solde)}).")

        elif produit_id:
            produit = conn.execute(
                text("SELECT id, nom, quantite FROM produits WHERE id = :p AND user_id = :u FOR UPDATE"),
                {"p": produit_id, "u": user_id},
            ).fetchone()
            if not produit:
                raise ValueError("Produit introuvable.")
            if quantite is None or quantite <= 0:
                raise ValueError("La quantité doit être supérieure à 0.")
            if quantite > produit.quantite:
                raise ValueError(f"Stock insuffisant pour « {produit.nom} » (disponible : {produit.quantite}).")
            maintenant = datetime.now()
            conn.execute(
                text("UPDATE produits SET quantite = quantite - :q, derniere_maj = :m WHERE id = :p AND user_id = :u"),
                {"q": quantite, "m": maintenant, "p": produit_id, "u": user_id},
            )
            conn.execute(
                text("INSERT INTO mouvements (user_id, date, produit_id, produit_nom, type, quantite, motif) "
                     "VALUES (:u, :d, :p, :n, 'Sortie', :q, :mo)"),
                {"u": user_id, "d": maintenant, "p": produit_id, "n": produit.nom, "q": quantite,
                 "mo": f"Vente à crédit — {client.nom}"},
            )
            if not note:
                note = f"{quantite} × {produit.nom}"

        conn.execute(
            text("INSERT INTO credit_operations (user_id, client_id, type, montant, note, produit_id, date) "
                 "VALUES (:u, :c, :t, :m, :n, :p, :d)"),
            {"u": user_id, "c": client_id, "t": type_op, "m": montant, "n": note or None,
             "p": produit_id if type_op == "dette" else None, "d": datetime.now()},
        )


def supprimer_client(engine, user_id, client_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM clients_credit WHERE id = :c AND user_id = :u"), {"c": client_id, "u": user_id})


def historique_client(engine, user_id, client_id) -> pd.DataFrame:
    df = pd.read_sql_query(text("""
        SELECT o.date, o.type, o.montant, o.note
        FROM credit_operations o
        WHERE o.client_id = :c AND o.user_id = :u
        ORDER BY o.date, o.id
    """), engine, params={"c": client_id, "u": user_id})
    df["montant"] = df["montant"].astype(float)
    signe = df["type"].map({"dette": 1, "remboursement": -1}).fillna(0)
    df["solde_apres"] = (signe * df["montant"]).cumsum()
    return df


# ----------------------------------------------------------------------
# OUTILS
# ----------------------------------------------------------------------
def lien_whatsapp(telephone, message):
    """Construit un lien wa.me (numéros ivoiriens à 10 chiffres complétés avec l'indicatif 225)."""
    chiffres = re.sub(r"\D", "", telephone or "")
    if chiffres.startswith("00"):
        chiffres = chiffres[2:]
    if not chiffres:
        return None
    if not chiffres.startswith("225") and len(chiffres) in (8, 10):
        chiffres = "225" + chiffres
    return f"https://wa.me/{chiffres}?text={quote(message)}"


def _jours_depuis(date):
    if pd.isna(date):
        return None
    return (datetime.now() - pd.Timestamp(date).to_pydatetime()).days


def generer_pdf_releve(nom_boutique, client, historique: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(f"Relevé de compte — {client['nom']}", styles["Title"]),
        Paragraph(f"{nom_boutique} · généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["Normal"]),
        Spacer(1, 14),
        Paragraph(f"Total des crédits : {client['total_dettes']:,.0f} FCFA", styles["Normal"]),
        Paragraph(f"Total remboursé : {client['total_rembourse']:,.0f} FCFA", styles["Normal"]),
        Paragraph(f"<b>Solde restant dû : {client['solde']:,.0f} FCFA</b>", styles["Normal"]),
        Spacer(1, 16),
    ]
    data = [["Date", "Opération", "Montant", "Solde après", "Note"]]
    for _, o in historique.iterrows():
        libelle = "Crédit" if o["type"] == "dette" else "Remboursement"
        data.append([str(o["date"])[:16].replace("T", " "), libelle, f"{o['montant']:,.0f}",
                     f"{o['solde_apres']:,.0f}", o["note"] or ""])
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3D2E")),
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
# PAGE
# ----------------------------------------------------------------------
def page_credit(engine, user_id, stock: pd.DataFrame, nom_boutique: str):
    hero("Cahier de crédit", "Qui te doit quoi, les remboursements, et la relance WhatsApp en un clic.", badge="Crédit clients")
    show_flash()

    clients = lister_clients(engine, user_id)
    debiteurs = clients[clients["solde"] > 0]
    total_du = float(debiteurs["solde"].sum()) if not debiteurs.empty else 0.0
    gros = debiteurs.iloc[0] if not debiteurs.empty else None
    kpi_grid([
        {"label": "Total à recouvrer", "value": fcfa(total_du), "tone": "coral", "sub": "crédits non soldés"},
        {"label": "Clients débiteurs", "value": str(len(debiteurs)), "tone": "amber", "sub": f"sur {len(clients)} client(s)"},
        {"label": "Plus gros solde", "value": fcfa(gros["solde"]) if gros is not None else "—", "tone": "lime",
         "sub": gros["nom"] if gros is not None else "aucun crédit en cours"},
        {"label": "Déjà remboursé", "value": fcfa(clients["total_rembourse"].sum() if not clients.empty else 0), "tone": "mint", "sub": "au total"},
    ])

    onglet_soldes, onglet_op, onglet_fiche = st.tabs(["📒 Soldes", "➕ Nouvelle opération", "👤 Fiche client"])

    # ---------------- Soldes ----------------
    with onglet_soldes:
        if clients.empty:
            st.info("Aucun client pour le moment. Ajoute ta première opération dans l'onglet « Nouvelle opération ».")
        else:
            recherche = st.text_input("🔍 Rechercher un client", key="credit_recherche")
            vue = clients
            if recherche:
                vue = clients[clients["nom"].str.contains(recherche, case=False, na=False)]
            lignes = []
            for _, c in vue.iterrows():
                jours = _jours_depuis(c["derniere_op"])
                if c["solde"] <= 0:
                    tone, pastille = "mint", "Soldé"
                elif jours is not None and jours > 30:
                    tone, pastille = "coral", f"En retard · {jours} j"
                else:
                    tone, pastille = "amber", "En cours"
                meta = (c["telephone"] or "Pas de téléphone") + (f" · dernier mouvement il y a {jours} j" if jours is not None else "")
                lignes.append(row_card_html(c["nom"], meta, fcfa(c["solde"]), tone, pastille))
            render_rows(lignes)
            if vue.empty:
                st.caption("Aucun client ne correspond à la recherche.")

    # ---------------- Nouvelle opération ----------------
    with onglet_op:
        options = {int(c["id"]): c["nom"] for _, c in clients.iterrows()}
        choix = st.selectbox("Client", [0] + list(options.keys()),
                             format_func=lambda i: "➕ Nouveau client" if i == 0 else options[i], key="credit_client")
        nom_nouveau = tel_nouveau = ""
        if choix == 0:
            c1, c2 = st.columns(2)
            nom_nouveau = c1.text_input("Nom du client", key="credit_nom_nouveau")
            tel_nouveau = c2.text_input("Téléphone (pour la relance WhatsApp)", key="credit_tel_nouveau")

        type_label = st.radio("Type d'opération", ["Crédit accordé", "Remboursement reçu"], horizontal=True, key="credit_type")
        est_dette = type_label == "Crédit accordé"

        produit_id, quantite, montant_defaut = None, None, 0
        if est_dette and not stock.empty:
            if st.checkbox("Lier à un produit du stock (déduit la quantité vendue)", key="credit_lier"):
                dispo = stock[stock["quantite"] > 0]
                if dispo.empty:
                    st.warning("Aucun produit en stock.")
                else:
                    labels = {int(p["id"]): f"{p['nom']} (stock : {int(p['quantite'])})" for _, p in dispo.iterrows()}
                    produit_id = st.selectbox("Produit", list(labels.keys()), format_func=lambda i: labels[i], key="credit_produit")
                    ligne = dispo[dispo["id"] == produit_id].iloc[0]
                    quantite = st.number_input("Quantité vendue", min_value=1, max_value=int(ligne["quantite"]), step=1, value=1, key="credit_qte")
                    montant_defaut = int(round(float(ligne["prix_unitaire"]) * quantite))

        montant = st.number_input("Montant (FCFA)", min_value=0, step=500, value=int(montant_defaut),
                                  key=f"credit_montant_{produit_id}_{quantite}")
        note = st.text_input("Note (optionnel)", key="credit_note")

        if st.button("Enregistrer l'opération", type="primary", key="credit_valider"):
            try:
                if choix == 0:
                    if not nom_nouveau.strip():
                        raise ValueError("Le nom du client est obligatoire.")
                    client_id = ajouter_client(engine, user_id, nom_nouveau.strip(), tel_nouveau.strip())
                    nom_client = nom_nouveau.strip()
                else:
                    client_id, nom_client = choix, options[choix]
                enregistrer_operation(engine, user_id, client_id, "dette" if est_dette else "remboursement",
                                      float(montant), note.strip(), produit_id, quantite)
            except ValueError as e:
                st.error(str(e))
            else:
                flash(f"{'Crédit' if est_dette else 'Remboursement'} de {fcfa(montant)} enregistré pour {nom_client}.")
                for k in ("credit_nom_nouveau", "credit_tel_nouveau", "credit_note", "credit_lier"):
                    st.session_state.pop(k, None)
                st.rerun()

    # ---------------- Fiche client ----------------
    with onglet_fiche:
        if clients.empty:
            st.info("Aucun client enregistré.")
        else:
            noms = {int(c["id"]): c["nom"] for _, c in clients.iterrows()}
            cid = st.selectbox("Client", list(noms.keys()), format_func=lambda i: noms[i], key="credit_fiche")
            client = clients[clients["id"] == cid].iloc[0]
            kpi_grid([
                {"label": "Solde dû", "value": fcfa(client["solde"]), "tone": "coral" if client["solde"] > 0 else "mint",
                 "sub": client["nom"]},
                {"label": "Crédits accordés", "value": fcfa(client["total_dettes"]), "tone": "amber"},
                {"label": "Remboursé", "value": fcfa(client["total_rembourse"]), "tone": "mint"},
            ])

            hist = historique_client(engine, user_id, cid)
            colA, colB = st.columns(2)
            with colA:
                if client["solde"] > 0:
                    message = (f"Bonjour {client['nom']}, c'est {nom_boutique}. Petit rappel : il vous reste "
                               f"{fcfa(client['solde'])} à régler. Merci et bonne journée !")
                    lien = lien_whatsapp(client["telephone"], message)
                    if lien:
                        st.link_button("💬 Relancer sur WhatsApp", lien, type="primary")
                    else:
                        st.caption("Ajoute un numéro de téléphone pour activer la relance WhatsApp.")
            with colB:
                if not hist.empty:
                    st.download_button("📄 Relevé PDF", data=generer_pdf_releve(nom_boutique, client, hist),
                                       file_name=f"releve_{re.sub(r'[^A-Za-z0-9]+', '_', client['nom'])}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                       mime="application/pdf", type="primary", key="credit_pdf")

            section("Historique")
            if hist.empty:
                st.info("Aucune opération pour ce client.")
            else:
                lignes = []
                for _, o in hist.iloc[::-1].iterrows():
                    est_d = o["type"] == "dette"
                    meta = str(o["date"])[:16].replace("T", " ") + (f" · {o['note']}" if o["note"] else "")
                    lignes.append(row_card_html("Crédit accordé" if est_d else "Remboursement", meta,
                                                ("+ " if est_d else "− ") + fcfa(o["montant"]),
                                                "amber" if est_d else "mint", f"solde {fcfa(o['solde_apres'])}"))
                render_rows(lignes)

            with st.expander("Zone sensible — supprimer ce client"):
                st.caption("Supprime le client et tout son historique de crédit. Le stock et les mouvements ne changent pas.")
                if st.checkbox("Je confirme la suppression", key=f"credit_confirm_{cid}"):
                    if st.button("Supprimer définitivement", key=f"credit_suppr_{cid}"):
                        supprimer_client(engine, user_id, cid)
                        flash(f"Client « {client['nom']} » supprimé.")
                        st.rerun()
