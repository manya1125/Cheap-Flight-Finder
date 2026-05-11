import email.utils as email_utils
import re
import secrets
import sqlite3
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash


class NewUser:
    def __init__(self, db_file):
        self.db_file = db_file

    def _connect(self):
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn

    def is_valid_email(self, email):
        try:
            parsed_email = email_utils.parseaddr(email)[1]
            return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", parsed_email))
        except Exception:
            return False

    def register_new_user(self, first_name, last_name, email, password):
        password_hash = generate_password_hash(password)

        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT id, password_hash
                FROM users
                WHERE email = ?
                LIMIT 1
                """,
                (email,),
            ).fetchone()

            if existing:
                if existing["password_hash"]:
                    return False

                conn.execute(
                    """
                    UPDATE users
                    SET first_name = ?, last_name = ?, password_hash = ?
                    WHERE email = ?
                    """,
                    (first_name, last_name, password_hash, email),
                )
                return True

            conn.execute(
                """
                INSERT INTO users (
                    first_name,
                    last_name,
                    email,
                    password_hash,
                    alert_frequency,
                    preferred_origin,
                    max_price
                )
                VALUES (?, ?, ?, ?, 'instant', 'LON', NULL)
                """,
                (first_name, last_name, email, password_hash),
            )
            return True

    def create_imported_user(self, first_name, last_name, email):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO users (
                    first_name,
                    last_name,
                    email,
                    password_hash,
                    alert_frequency,
                    preferred_origin,
                    max_price
                )
                VALUES (?, ?, ?, NULL, 'instant', 'LON', NULL)
                """,
                (first_name, last_name, email),
            )

    def get_user_by_email(self, email):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    first_name,
                    last_name,
                    email,
                    password_hash,
                    alert_frequency,
                    preferred_origin,
                    max_price,
                    reset_token,
                    reset_token_expires_at
                FROM users
                WHERE email = ?
                LIMIT 1
                """,
                (email,),
            ).fetchone()
        return dict(row) if row else None

    def authenticate_user(self, email, password):
        user = self.get_user_by_email(email)
        if not user or not user["password_hash"]:
            return None

        if not check_password_hash(user["password_hash"], password):
            return None

        return self._public_user(user)

    def _public_user(self, user):
        return {
            "id": user["id"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "email": user["email"],
            "alert_frequency": user.get("alert_frequency"),
            "preferred_origin": user.get("preferred_origin"),
            "max_price": user.get("max_price"),
        }

    def get_public_user(self, email):
        user = self.get_user_by_email(email)
        if not user:
            return None
        return self._public_user(user)

    def get_all_users(self):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    first_name,
                    last_name,
                    email,
                    alert_frequency,
                    preferred_origin,
                    max_price
                FROM users
                ORDER BY id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_users_by_origin(self, origin_code):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    first_name,
                    last_name,
                    email,
                    alert_frequency,
                    preferred_origin,
                    max_price
                FROM users
                WHERE preferred_origin = ?
                ORDER BY id DESC
                """,
                (origin_code,),
            ).fetchall()
        return [dict(row) for row in rows]

    def count_users(self):
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()
        return row["total"]

    def user_exists(self, email):
        return self.get_user_by_email(email) is not None

    def update_preferences(self, email, alert_frequency, preferred_origin, max_price):
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET alert_frequency = ?, preferred_origin = ?, max_price = ?
                WHERE email = ?
                """,
                (alert_frequency, preferred_origin, max_price, email),
            )
        return self.get_public_user(email)

    def create_reset_token(self, email):
        user = self.get_user_by_email(email)
        if not user:
            return None

        token = secrets.token_urlsafe(24)
        expires_at = (datetime.utcnow() + timedelta(minutes=30)).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET reset_token = ?, reset_token_expires_at = ?
                WHERE email = ?
                """,
                (token, expires_at, email),
            )
        return token

    def reset_password(self, token, password):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT email, reset_token_expires_at
                FROM users
                WHERE reset_token = ?
                LIMIT 1
                """,
                (token,),
            ).fetchone()

            if not row:
                return False

            expires_at = row["reset_token_expires_at"]
            if not expires_at or datetime.utcnow() > datetime.fromisoformat(expires_at):
                return False

            conn.execute(
                """
                UPDATE users
                SET password_hash = ?, reset_token = NULL, reset_token_expires_at = NULL
                WHERE reset_token = ?
                """,
                (generate_password_hash(password), token),
            )
        return True

    def delete_account(self, email):
        with self._connect() as conn:
            conn.execute("DELETE FROM wishlist WHERE email = ?", (email,))
            conn.execute("DELETE FROM users WHERE email = ?", (email,))

    def add_to_wishlist(self, email, city):
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO wishlist (email, city)
                    VALUES (?, ?)
                    """,
                    (email, city),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_wishlist(self, email):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT city FROM wishlist WHERE email = ? ORDER BY city ASC",
                (email,),
            ).fetchall()
        return [row["city"] for row in rows]

    def count_wishlist_items(self):
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM wishlist").fetchone()
        return row["total"]
