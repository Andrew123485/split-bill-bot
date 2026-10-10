import sqlite3
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import DATABASE_PATH


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Bills table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bills (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        payer_user_id INTEGER NOT NULL,
        payer_name TEXT NOT NULL,
        payer_username TEXT,
        payer_phone TEXT,
        payer_bank TEXT,
        total_amount REAL NOT NULL DEFAULT 0.0,
        fiscal_qr TEXT,
        chat_id INTEGER,
        status TEXT NOT NULL DEFAULT 'open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bill_id TEXT NOT NULL,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        quantity REAL NOT NULL DEFAULT 1.0,
        total_price REAL NOT NULL,
        category TEXT NOT NULL DEFAULT 'shared',
        is_alcohol INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
    );
    """)

    # Participants table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bill_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        username TEXT,
        is_nondrinker INTEGER NOT NULL DEFAULT 0,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(bill_id, user_id),
        FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
    );
    """)

    # Item claims (which users claimed which item; if none claimed, it falls back to shared among all eligible)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS item_claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bill_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        UNIQUE(item_id, user_id),
        FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


def create_bill(
    title: str,
    payer_user_id: int,
    payer_name: str,
    payer_username: Optional[str] = None,
    payer_phone: Optional[str] = None,
    payer_bank: Optional[str] = None,
    total_amount: float = 0.0,
    fiscal_qr: Optional[str] = None,
    chat_id: Optional[int] = None,
    items: Optional[List[Dict[str, Any]]] = None,
) -> str:
    bill_id = uuid.uuid4().hex[:10]
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO bills (id, title, payer_user_id, payer_name, payer_username, payer_phone, payer_bank, total_amount, fiscal_qr, chat_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (bill_id, title, payer_user_id, payer_name, payer_username, payer_phone, payer_bank, total_amount, fiscal_qr, chat_id),
    )

    # Automatically add payer as a participant
    cursor.execute(
        """
        INSERT OR IGNORE INTO participants (bill_id, user_id, name, username, is_nondrinker)
        VALUES (?, ?, ?, ?, 0)
        """,
        (bill_id, payer_user_id, payer_name, payer_username),
    )

    calc_total = 0.0
    if items:
        for item in items:
            name = item.get("name", "Товар")
            price = float(item.get("price", 0.0))
            quantity = float(item.get("quantity", 1.0))
            total_price = float(item.get("total_price", price * quantity))
            calc_total += total_price
            category = item.get("category", "shared")
            is_alcohol = 1 if item.get("is_alcohol") or category == "alcohol" else 0

            cursor.execute(
                """
                INSERT INTO items (bill_id, name, price, quantity, total_price, category, is_alcohol)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (bill_id, name, price, quantity, total_price, category, is_alcohol),
            )

    if total_amount <= 0.0 and calc_total > 0.0:
        cursor.execute("UPDATE bills SET total_amount = ? WHERE id = ?", (round(calc_total, 2), bill_id))

    conn.commit()
    conn.close()
    return bill_id


def get_bill(bill_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bills WHERE id = ?", (bill_id,))
    bill_row = cursor.fetchone()
    if not bill_row:
        conn.close()
        return None

    bill = dict(bill_row)

    # Fetch items
    cursor.execute("SELECT * FROM items WHERE bill_id = ?", (bill_id,))
    items_rows = cursor.fetchall()
    items = []
    for r in items_rows:
        item = dict(r)
        # Fetch claims for this item
        cursor.execute("SELECT user_id FROM item_claims WHERE item_id = ?", (item["id"],))
        claims = [c["user_id"] for c in cursor.fetchall()]
        item["claimed_by"] = claims
        items.append(item)
    bill["items"] = items

    # Fetch participants
    cursor.execute("SELECT * FROM participants WHERE bill_id = ?", (bill_id,))
    participants = [dict(p) for p in cursor.fetchall()]
    bill["participants"] = participants

    conn.close()
    return bill


def add_or_update_participant(
    bill_id: str,
    user_id: int,
    name: str,
    username: Optional[str] = None,
    is_nondrinker: Optional[bool] = None,
):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM participants WHERE bill_id = ? AND user_id = ?", (bill_id, user_id))
    existing = cursor.fetchone()

    if existing:
        if is_nondrinker is not None:
            cursor.execute(
                "UPDATE participants SET name = ?, username = ?, is_nondrinker = ? WHERE bill_id = ? AND user_id = ?",
                (name, username or existing["username"], 1 if is_nondrinker else 0, bill_id, user_id),
            )
        else:
            cursor.execute(
                "UPDATE participants SET name = ?, username = ? WHERE bill_id = ? AND user_id = ?",
                (name, username or existing["username"], bill_id, user_id),
            )
    else:
        nd_val = 1 if is_nondrinker else 0
        cursor.execute(
            "INSERT INTO participants (bill_id, user_id, name, username, is_nondrinker) VALUES (?, ?, ?, ?, ?)",
            (bill_id, user_id, name, username, nd_val),
        )

    conn.commit()
    conn.close()


def update_participant_name(bill_id: str, user_id: int, new_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE participants SET name = ? WHERE bill_id = ? AND user_id = ?",
        (new_name, bill_id, user_id),
    )
    cursor.execute(
        "UPDATE bills SET payer_name = ? WHERE id = ? AND payer_user_id = ?",
        (new_name, bill_id, user_id),
    )
    conn.commit()
    conn.close()


def toggle_nondrinker(bill_id: str, user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT is_nondrinker FROM participants WHERE bill_id = ? AND user_id = ?", (bill_id, user_id))
    row = cursor.fetchone()
    new_val = 0
    if row:
        new_val = 0 if row["is_nondrinker"] else 1
        cursor.execute(
            "UPDATE participants SET is_nondrinker = ? WHERE bill_id = ? AND user_id = ?",
            (new_val, bill_id, user_id),
        )

        # If user becomes nondrinker, unclaim any alcohol items they claimed
        if new_val == 1:
            cursor.execute(
                """
                DELETE FROM item_claims
                WHERE user_id = ? AND item_id IN (
                    SELECT id FROM items WHERE bill_id = ? AND (is_alcohol = 1 OR category = 'alcohol')
                )
                """,
                (user_id, bill_id),
            )

    conn.commit()
    conn.close()
    return bool(new_val)


def toggle_item_claim(bill_id: str, item_id: int, user_id: int) -> bool:
    """
    Toggles whether user_id claimed item_id.
    Returns True if claimed now, False if un-claimed.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM item_claims WHERE item_id = ? AND user_id = ?", (item_id, user_id))
    existing = cursor.fetchone()

    is_claimed = False
    if existing:
        cursor.execute("DELETE FROM item_claims WHERE id = ?", (existing["id"],))
        is_claimed = False
    else:
        cursor.execute(
            "INSERT INTO item_claims (bill_id, item_id, user_id) VALUES (?, ?, ?)",
            (bill_id, item_id, user_id),
        )
        is_claimed = True

    conn.commit()
    conn.close()
    return is_claimed


def set_item_category(item_id: int, category: str, is_alcohol: bool):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE items SET category = ?, is_alcohol = ? WHERE id = ?",
        (category, 1 if is_alcohol else 0, item_id),
    )
    conn.commit()
    conn.close()


def add_item_to_bill(bill_id: str, name: str, price: float, quantity: float = 1.0, category: str = "shared"):
    conn = get_db_connection()
    cursor = conn.cursor()
    total_price = round(price * quantity, 2)
    is_alcohol = 1 if category == "alcohol" else 0

    cursor.execute(
        """
        INSERT INTO items (bill_id, name, price, quantity, total_price, category, is_alcohol)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (bill_id, name, price, quantity, total_price, category, is_alcohol),
    )

    # Update bill total
    cursor.execute("UPDATE bills SET total_amount = total_amount + ? WHERE id = ?", (total_price, bill_id))

    conn.commit()
    conn.close()


def update_bill_status(bill_id: str, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bills SET status = ? WHERE id = ?", (status, bill_id))
    conn.commit()
    conn.close()


def set_bill_payer(bill_id: str, payer_user_id: int, payer_name: str, payer_phone: Optional[str] = None, payer_bank: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ensure this payer is registered as a participant too
    cursor.execute(
        "INSERT OR IGNORE INTO participants (bill_id, user_id, name, is_nondrinker) VALUES (?, ?, ?, 0)",
        (bill_id, payer_user_id, payer_name),
    )

    cursor.execute(
        """
        UPDATE bills
        SET payer_user_id = ?, payer_name = ?,
            payer_phone = COALESCE(?, payer_phone),
            payer_bank = COALESCE(?, payer_bank)
        WHERE id = ?
        """,
        (payer_user_id, payer_name, payer_phone, payer_bank, bill_id),
    )
    conn.commit()
    conn.close()


def add_participant_manual(bill_id: str, name: str, is_nondrinker: bool = False) -> int:
    """Adds a participant manually by name (for offline friends). Generates a unique virtual user_id."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create a unique virtual user_id for this manual friend
    virtual_id = abs(hash(f"{bill_id}_{name}_{datetime.now().timestamp()}")) % 900000 + 100000
    nd_val = 1 if is_nondrinker else 0

    cursor.execute(
        "INSERT INTO participants (bill_id, user_id, name, is_nondrinker) VALUES (?, ?, ?, ?)",
        (bill_id, virtual_id, name, nd_val),
    )
    conn.commit()
    conn.close()
    return virtual_id


def get_latest_bill(user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id:
        cursor.execute(
            """
            SELECT b.id FROM bills b
            LEFT JOIN participants p ON b.id = p.bill_id
            WHERE b.payer_user_id = ? OR p.user_id = ?
            ORDER BY b.created_at DESC LIMIT 1
            """,
            (user_id, user_id),
        )
        row = cursor.fetchone()
        if row:
            conn.close()
            return get_bill(row["id"])

    # Fallback to absolute latest
    cursor.execute("SELECT id FROM bills ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return get_bill(row["id"])
    return None


def get_all_bills(user_id: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute(
            """
            SELECT DISTINCT b.id, b.title, b.payer_name, b.total_amount, b.status, b.created_at,
                   (SELECT COUNT(*) FROM items WHERE bill_id = b.id) as items_count
            FROM bills b
            LEFT JOIN participants p ON b.id = p.bill_id
            WHERE b.payer_user_id = ? OR p.user_id = ?
            ORDER BY b.created_at DESC
            LIMIT ?
            """,
            (user_id, user_id, limit),
        )
    else:
        cursor.execute(
            """
            SELECT b.id, b.title, b.payer_name, b.total_amount, b.status, b.created_at,
                   (SELECT COUNT(*) FROM items WHERE bill_id = b.id) as items_count
            FROM bills b
            ORDER BY b.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_or_create_demo_bill() -> str:
    """Ensures a rich demo bill exists and returns its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM bills WHERE id = 'demo'")
    row = cursor.fetchone()
    conn.close()
    if row:
        return "demo"

    import receipt_parser
    verny_data = receipt_parser.get_sample_verny_receipt()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO bills (id, title, payer_user_id, payer_name, payer_phone, payer_bank, total_amount)
        VALUES ('demo', ?, 1, 'Андрей', '+7 (999) 000-00-00', 'Сбербанк', ?)
        """,
        (verny_data["title"], verny_data["total_amount"]),
    )
    cursor.execute(
        "INSERT INTO participants (bill_id, user_id, name, is_nondrinker) VALUES ('demo', 1, 'Андрей', 0)"
    )
    # Add a couple demo friends
    cursor.execute("INSERT INTO participants (bill_id, user_id, name, is_nondrinker) VALUES ('demo', 2, 'Маша', 1)")
    cursor.execute("INSERT INTO participants (bill_id, user_id, name, is_nondrinker) VALUES ('demo', 3, 'Коля', 0)")

    for it in verny_data["items"]:
        cursor.execute(
            """
            INSERT INTO items (bill_id, name, price, quantity, total_price, category, is_alcohol)
            VALUES ('demo', ?, ?, ?, ?, ?, ?)
            """,
            (it["name"], it["price"], it["quantity"], it["total_price"], it["category"], 1 if it["is_alcohol"] else 0),
        )

    conn.commit()
    conn.close()
    return "demo"


def clear_all_bills():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM item_claims")
    cursor.execute("DELETE FROM items")
    cursor.execute("DELETE FROM participants")
    cursor.execute("DELETE FROM bills")
    conn.commit()
    conn.close()


def delete_bill(bill_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM item_claims WHERE bill_id = ?", (bill_id,))
    cursor.execute("DELETE FROM items WHERE bill_id = ?", (bill_id,))
    cursor.execute("DELETE FROM participants WHERE bill_id = ?", (bill_id,))
    cursor.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
    conn.commit()
    conn.close()


