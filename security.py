"""
Sécurité de l'authentification : blocage après échecs, limitation de débit, politique de mot de passe.

Principes :
- Les compteurs sont indexés par un hachage (SHA-256) de « portée + email » : on ne stocke jamais l'email brut,
  et le comportement est identique que le compte existe ou non (pas d'énumération de comptes).
- 5 échecs consécutifs => blocage 15 min ; chaque nouveau blocage double la durée
  (15, 30, 60, 120, 240, 480 min, puis 24 h maximum). Une connexion réussie remet tout à zéro.
- Pendant un blocage, le mot de passe n'est même pas vérifié (impossible de continuer à deviner).
"""
import hashlib
import re

import bcrypt
from sqlalchemy import text

from db import get_engine

MAX_ECHECS = 5
DUREES_BLOCAGE_MIN = [15, 30, 60, 120, 240, 480, 1440]
OUBLI_ECHEC_APRES_H = 24          # des échecs isolés vieux de plus de 24 h ne comptent plus
NOW_UTC = "timezone('utc', now())"


class TropDeTentatives(Exception):
    """La clé (compte) est actuellement bloquée."""
    def __init__(self, minutes: int):
        self.minutes = max(int(minutes), 1)
        super().__init__(f"Bloqué encore {self.minutes} minute(s)")


class ConnexionRefusee(Exception):
    """Identifiants incorrects. `restantes` = essais avant blocage ; `bloque_minutes` si ce échec déclenche un blocage."""
    def __init__(self, restantes: int = 0, bloque_minutes: int | None = None):
        self.restantes = restantes
        self.bloque_minutes = bloque_minutes
        super().__init__("Identifiants incorrects")


# ----------------------------------------------------------------------
# Mots de passe
# ----------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# Hash factice : vérifié quand l'email n'existe pas, pour que la durée de réponse ne trahisse pas l'existence d'un compte
DUMMY_HASH = hash_password("mot-de-passe-factice-pour-egaliser-le-temps")

MOTS_DE_PASSE_COURANTS = {
    "12345678", "123456789", "1234567890", "11111111", "00000000", "87654321", "password", "password1",
    "password123", "motdepasse", "motdepasse1", "motdepasse123", "azerty123", "azertyuiop", "azerty1234",
    "qwerty123", "qwertyuiop", "abcd1234", "abc12345", "admin123", "administrateur", "bonjour123", "bienvenue",
    "welcome1", "welcome123", "iloveyou", "abidjan225", "abidjan123", "cotedivoire", "ivoire225", "ci225225",
    "boutique123", "boutique225", "bizstock", "bizstock123", "stock12345", "123456abc", "1q2w3e4r", "00000000",
}


def valider_mot_de_passe(mot_de_passe: str, email: str = "") -> str | None:
    """Retourne un message d'erreur, ou None si le mot de passe est acceptable."""
    if len(mot_de_passe) < 8:
        return "Le mot de passe doit contenir au moins 8 caractères."
    bas = mot_de_passe.lower()
    if bas in MOTS_DE_PASSE_COURANTS:
        return "Ce mot de passe est trop courant. Choisis-en un plus personnel."
    if mot_de_passe.isdigit():
        return "Le mot de passe ne peut pas être uniquement composé de chiffres."
    if len(set(mot_de_passe)) <= 2:
        return "Le mot de passe est trop répétitif."
    local = (email or "").split("@")[0].lower()
    if len(local) >= 4 and local in bas:
        return "Le mot de passe ne doit pas contenir ton adresse email."
    return None


# ----------------------------------------------------------------------
# Blocage après échecs
# ----------------------------------------------------------------------
def cle(portee: str, valeur: str) -> str:
    return hashlib.sha256(f"{portee}:{(valeur or '').strip().lower()}".encode()).hexdigest()


def verifier_blocage(portee: str, valeur: str):
    """Lève TropDeTentatives si cette clé est bloquée."""
    with get_engine().connect() as conn:
        row = conn.execute(
            text(f"SELECT CEIL(EXTRACT(EPOCH FROM (locked_until - {NOW_UTC})) / 60.0) AS minutes "
                 f"FROM auth_throttle WHERE key = :k AND locked_until IS NOT NULL AND locked_until > {NOW_UTC}"),
            {"k": cle(portee, valeur)},
        ).fetchone()
    if row:
        raise TropDeTentatives(row.minutes)


def enregistrer_echec(portee: str, valeur: str) -> tuple[int, int | None]:
    """Compte un échec. Retourne (essais_restants, minutes_de_blocage_si_déclenché)."""
    k = cle(portee, valeur)
    with get_engine().begin() as conn:
        r = conn.execute(
            text(f"""
                INSERT INTO auth_throttle (key, failed, lock_level, updated_at)
                VALUES (:k, 1, 0, {NOW_UTC})
                ON CONFLICT (key) DO UPDATE SET
                    failed = CASE WHEN auth_throttle.updated_at < {NOW_UTC} - (:h * INTERVAL '1 hour')
                                  THEN 1 ELSE auth_throttle.failed + 1 END,
                    lock_level = CASE WHEN auth_throttle.updated_at < {NOW_UTC} - (:h * INTERVAL '1 hour')
                                      THEN 0 ELSE auth_throttle.lock_level END,
                    updated_at = {NOW_UTC}
                RETURNING failed, lock_level
            """),
            {"k": k, "h": OUBLI_ECHEC_APRES_H},
        ).fetchone()
        if r.failed >= MAX_ECHECS:
            minutes = DUREES_BLOCAGE_MIN[min(r.lock_level, len(DUREES_BLOCAGE_MIN) - 1)]
            conn.execute(
                text(f"UPDATE auth_throttle SET failed = 0, lock_level = lock_level + 1, "
                     f"locked_until = {NOW_UTC} + (:m * INTERVAL '1 minute') WHERE key = :k"),
                {"m": minutes, "k": k},
            )
            return 0, minutes
        return MAX_ECHECS - r.failed, None


def reinitialiser(portee: str, valeur: str):
    """Connexion réussie : on efface compteurs et niveau de blocage."""
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM auth_throttle WHERE key = :k"), {"k": cle(portee, valeur)})


# ----------------------------------------------------------------------
# Limitation de débit (ex. demandes de réinitialisation, inscriptions)
# ----------------------------------------------------------------------
def limiter_debit(portee: str, valeur: str, max_hits: int, fenetre_min: int) -> bool:
    """Compte un appel dans la fenêtre glissante. Retourne True si l'appel est autorisé."""
    with get_engine().begin() as conn:
        r = conn.execute(
            text(f"""
                INSERT INTO auth_throttle (key, failed, window_start, updated_at)
                VALUES (:k, 1, {NOW_UTC}, {NOW_UTC})
                ON CONFLICT (key) DO UPDATE SET
                    failed = CASE WHEN auth_throttle.window_start IS NULL
                                       OR auth_throttle.window_start < {NOW_UTC} - (:f * INTERVAL '1 minute')
                                  THEN 1 ELSE auth_throttle.failed + 1 END,
                    window_start = CASE WHEN auth_throttle.window_start IS NULL
                                             OR auth_throttle.window_start < {NOW_UTC} - (:f * INTERVAL '1 minute')
                                        THEN {NOW_UTC} ELSE auth_throttle.window_start END,
                    updated_at = {NOW_UTC}
                RETURNING failed
            """),
            {"k": cle(portee, valeur), "f": fenetre_min},
        ).fetchone()
    return r.failed <= max_hits


def purger_anciens_compteurs():
    with get_engine().begin() as conn:
        conn.execute(text(
            f"DELETE FROM auth_throttle WHERE updated_at < {NOW_UTC} - INTERVAL '30 days' "
            f"AND (locked_until IS NULL OR locked_until < {NOW_UTC})"))
