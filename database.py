"""
database.py
===========
SQLite persistence layer for the shop bot.

Design notes
------------
* All access goes through the ``Database`` class - no raw SQL scattered
  around the codebase.
* ``sqlite3`` connections are opened per-operation (short-lived) which is
  the recommended pattern for small/medium Telegram bots: it avoids
  cross-thread issues with a single long-lived connection while
  python-telegram-bot's async handlers may run on different tasks.
* Tables are created automatically on first run via ``init_db``.
* Order numbers are generated as ``ORD-<YYYYMMDD>-<sequence>`` and are
  guaranteed unique by the ``UNIQUE`` constraint on the column plus a
  retry loop.
"""

from __future__ import annotations

import random
import sqlite3
import string
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, List, Optional

from config import DB_NAME, STATUS_WAITING


# ---------------------------------------------------------------------------
# Data classes returned to callers (typed, easier to work with than raw rows)
# ---------------------------------------------------------------------------


@dataclass
class Order:
    id: int
    order_number: str
    user_id: int
    username: Optional[str]
    product_code: str
    product_name: str
    model: str
    quantity: int
    price_per_item: int
    total_price: int
    date: str
    full_name: str
    phone: str
    address: str
    postal_code: str
    status: str
    tracking_code: Optional[str]
    receipt_file_id: Optional[str]


# ---------------------------------------------------------------------------
# Database class
# ---------------------------------------------------------------------------


class Database:
    """Thin synchronous wrapper around sqlite3 used by the bot handlers."""

    def __init__(self, db_name: str = DB_NAME) -> None:
        self.db_name = db_name
        self.init_db()

    # -- connection helpers -------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # -- schema ---------------------------------------------------------

    def init_db(self) -> None:
        """Create all required tables if they do not already exist."""
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id      INTEGER PRIMARY KEY,
                    username     TEXT,
                    full_name    TEXT,
                    phone        TEXT,
                    address      TEXT,
                    postal_code  TEXT,
                    created_at   TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_number     TEXT NOT NULL UNIQUE,
                    user_id          INTEGER NOT NULL,
                    username         TEXT,
                    product_code     TEXT NOT NULL,
                    product_name     TEXT NOT NULL,
                    model            TEXT NOT NULL,
                    quantity         INTEGER NOT NULL,
                    price_per_item   INTEGER NOT NULL,
                    total_price      INTEGER NOT NULL,
                    date             TEXT NOT NULL,
                    full_name        TEXT NOT NULL,
                    phone            TEXT NOT NULL,
                    address          TEXT NOT NULL,
                    postal_code      TEXT NOT NULL,
                    status           TEXT NOT NULL,
                    tracking_code    TEXT,
                    receipt_file_id  TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );
                """
            )

    # -- users ------------------------------------------------------------

    def upsert_user(
        self,
        user_id: int,
        username: Optional[str],
        full_name: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        postal_code: Optional[str] = None,
    ) -> None:
        """Insert the user if new, otherwise update the provided fields."""
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO users
                        (user_id, username, full_name, phone, address,
                         postal_code, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        full_name,
                        phone,
                        address,
                        postal_code,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
            else:
                # Only overwrite fields that were actually supplied.
                fields, values = [], []
                for col, val in (
                    ("username", username),
                    ("full_name", full_name),
                    ("phone", phone),
                    ("address", address),
                    ("postal_code", postal_code),
                ):
                    if val is not None:
                        fields.append(f"{col} = ?")
                        values.append(val)
                if fields:
                    values.append(user_id)
                    conn.execute(
                        f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?",
                        values,
                    )

    # -- order number generation ------------------------------------------

    def _generate_order_number(self, conn: sqlite3.Connection) -> str:
        """Generate a unique, human-readable order number."""
        today = datetime.now().strftime("%Y%m%d")
        for _ in range(20):
            suffix = "".join(random.choices(string.digits, k=4))
            candidate = f"ORD-{today}-{suffix}"
            row = conn.execute(
                "SELECT 1 FROM orders WHERE order_number = ?", (candidate,)
            ).fetchone()
            if row is None:
                return candidate
        # Extremely unlikely fallback using a timestamp for absolute uniqueness.
        return f"ORD-{today}-{int(datetime.now().timestamp())}"

    # -- orders -------------------------------------------------------------

    def create_order(
        self,
        user_id: int,
        username: Optional[str],
        product_code: str,
        product_name: str,
        model: str,
        quantity: int,
        price_per_item: int,
        full_name: str,
        phone: str,
        address: str,
        postal_code: str,
        receipt_file_id: Optional[str],
    ) -> Order:
        """Persist a new order and return the created ``Order``."""
        total_price = quantity * price_per_item
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._connect() as conn:
            order_number = self._generate_order_number(conn)
            cursor = conn.execute(
                """
                INSERT INTO orders (
                    order_number, user_id, username, product_code,
                    product_name, model, quantity, price_per_item,
                    total_price, date, full_name, phone, address,
                    postal_code, status, tracking_code, receipt_file_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_number,
                    user_id,
                    username,
                    product_code,
                    product_name,
                    model,
                    quantity,
                    price_per_item,
                    total_price,
                    date_str,
                    full_name,
                    phone,
                    address,
                    postal_code,
                    STATUS_WAITING,
                    None,
                    receipt_file_id,
                ),
            )
            order_id = cursor.lastrowid

        return Order(
            id=order_id,
            order_number=order_number,
            user_id=user_id,
            username=username,
            product_code=product_code,
            product_name=product_name,
            model=model,
            quantity=quantity,
            price_per_item=price_per_item,
            total_price=total_price,
            date=date_str,
            full_name=full_name,
            phone=phone,
            address=address,
            postal_code=postal_code,
            status=STATUS_WAITING,
            tracking_code=None,
            receipt_file_id=receipt_file_id,
        )

    def _row_to_order(self, row: sqlite3.Row) -> Order:
        return Order(
            id=row["id"],
            order_number=row["order_number"],
            user_id=row["user_id"],
            username=row["username"],
            product_code=row["product_code"],
            product_name=row["product_name"],
            model=row["model"],
            quantity=row["quantity"],
            price_per_item=row["price_per_item"],
            total_price=row["total_price"],
            date=row["date"],
            full_name=row["full_name"],
            phone=row["phone"],
            address=row["address"],
            postal_code=row["postal_code"],
            status=row["status"],
            tracking_code=row["tracking_code"],
            receipt_file_id=row["receipt_file_id"],
        )

    def get_order_by_number(self, order_number: str) -> Optional[Order]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE order_number = ?", (order_number,)
            ).fetchone()
        return self._row_to_order(row) if row else None

    def get_user_orders(self, user_id: int) -> List[Order]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [self._row_to_order(r) for r in rows]

    def update_order_status(self, order_number: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE orders SET status = ? WHERE order_number = ?",
                (status, order_number),
            )

    def set_tracking_code(self, order_number: str, tracking_code: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE orders
                SET tracking_code = ?, status = ?
                WHERE order_number = ?
                """,
                (tracking_code, "sent", order_number),
            )

    def has_pending_order(self, user_id: int) -> bool:
        """
        Used to help prevent accidental duplicate submissions: returns True
        if the user has an order still waiting for admin review.
        """
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM orders
                WHERE user_id = ? AND status = ?
                LIMIT 1
                """,
                (user_id, STATUS_WAITING),
            ).fetchone()
        return row is not None


# Single shared instance used across the whole application.
db = Database()
