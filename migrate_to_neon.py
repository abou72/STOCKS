"""
Script de migration : SQLite local (stock.db) -> Neon (PostgreSQL)

Usage :
    python migrate_to_neon.py --sqlite stock.db --email toi@example.com --password monmotdepasse --boutique "Boutique Samba"

Ce que fait le script :
1. Crée ton compte utilisateur sur Neon (ou se connecte s'il existe déjà).
2. Copie tous les produits de stock.db vers Neon, rattachés à ton compte.
3. Copie l'historique des mouvements, en faisant correspondre les anciens id
   de produits SQLite aux nouveaux id générés par Neon.

Prérequis : la variable DATABASE_URL (ou st.secrets["DATABASE_URL"]) doit pointer
vers ta base Neon avant de lancer ce script.
"""
import argparse
import sqlite3
from sqlalchemy import text
from db import get_engine, init_schema
from auth import create_user, authenticate


def migrer(sqlite_path: str, email: str, password: str, boutique: str):
    engine = get_engine()
    init_schema()

    email = email.strip().lower()
    user = authenticate(email, password)
    if not user:
        created = create_user(email, password, boutique)
        if not created:
            raise SystemExit(
                "Ce compte existe déjà sur Neon mais le mot de passe fourni ne correspond pas."
            )
        user = authenticate(email, password)
    user_id = user["id"]
    print(f"Utilisateur cible : {email} (id={user_id})")

    sconn = sqlite3.connect(sqlite_path)
    sconn.row_factory = sqlite3.Row

    produits = sconn.execute("SELECT * FROM produits").fetchall()
    id_mapping = {}
    with engine.begin() as conn:
        for p in produits:
            result = conn.execute(text("""
                INSERT INTO produits (user_id, nom, categorie, quantite, prix_unitaire, seuil_alerte, derniere_maj)
                VALUES (:uid, :nom, :cat, :qte, :prix, :seuil, :maj)
                RETURNING id
            """), {
                "uid": user_id, "nom": p["nom"], "cat": p["categorie"],
                "qte": p["quantite"], "prix": p["prix_unitaire"],
                "seuil": p["seuil_alerte"], "maj": p["derniere_maj"],
            })
            id_mapping[p["id"]] = result.scalar()
    print(f"{len(produits)} produit(s) migré(s).")

    mouvements = sconn.execute("SELECT * FROM mouvements").fetchall()
    with engine.begin() as conn:
        for m in mouvements:
            nouveau_produit_id = id_mapping.get(m["produit_id"])
            conn.execute(text("""
                INSERT INTO mouvements (user_id, date, produit_id, produit_nom, type, quantite, motif)
                VALUES (:uid, :date, :pid, :nom, :type, :qte, :motif)
            """), {
                "uid": user_id, "date": m["date"], "pid": nouveau_produit_id,
                "nom": m["produit_nom"], "type": m["type"], "qte": m["quantite"], "motif": m["motif"],
            })
    print(f"{len(mouvements)} mouvement(s) migré(s).")

    sconn.close()
    print("Migration terminée avec succès.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migration stock.db (SQLite) -> Neon (PostgreSQL)")
    parser.add_argument("--sqlite", default="stock.db", help="Chemin vers le fichier stock.db")
    parser.add_argument("--email", required=True, help="Email du compte à créer/utiliser sur Neon")
    parser.add_argument("--password", required=True, help="Mot de passe du compte")
    parser.add_argument("--boutique", default="Ma boutique", help="Nom de la boutique")
    args = parser.parse_args()
    migrer(args.sqlite, args.email, args.password, args.boutique)
