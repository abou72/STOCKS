"""
Connexion à la base de données Neon (PostgreSQL) et création du schéma.
"""
import os
import streamlit as st
from sqlalchemy import create_engine, text


def get_database_url() -> str:
    """
    Récupère l'URL de connexion Neon.
    Ordre de priorité : st.secrets["DATABASE_URL"] puis variable d'environnement DATABASE_URL.
    Format attendu (fourni par Neon) :
        postgresql://user:password@ep-xxx.neon.tech/dbname?sslmode=require
    """
    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except FileNotFoundError:
        pass  # pas de fichier secrets.toml en local, on retombe sur l'env var

    url = os.environ.get("DATABASE_URL")
    if not url:
        st.error(
            "Aucune URL de connexion trouvée. Ajoute DATABASE_URL dans "
            ".streamlit/secrets.toml (en local) ou dans les secrets de l'app (Streamlit Cloud)."
        )
        st.stop()
    return url


@st.cache_resource
def get_engine():
    url = get_database_url()
    return create_engine(url, pool_pre_ping=True)


def init_schema():
    """Crée les tables si elles n'existent pas encore (idempotent, sûr à appeler à chaque démarrage)."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nom_boutique TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                reset_token TEXT,
                reset_token_expires TIMESTAMP
            )
        """))
        # Colonnes ajoutées après la création initiale de la table (sûr à rejouer)
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token TEXT"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS has_paid BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_checkout_id TEXT"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS produits (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                nom TEXT NOT NULL,
                categorie TEXT DEFAULT 'Non classé',
                quantite INTEGER NOT NULL DEFAULT 0,
                prix_unitaire NUMERIC NOT NULL DEFAULT 0,
                seuil_alerte INTEGER NOT NULL DEFAULT 5,
                derniere_maj TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mouvements (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                date TIMESTAMP,
                produit_id INTEGER REFERENCES produits(id) ON DELETE SET NULL,
                produit_nom TEXT,
                type TEXT NOT NULL,
                quantite INTEGER NOT NULL,
                motif TEXT
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_produits_user ON produits(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mouvements_user ON mouvements(user_id)"))