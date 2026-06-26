"""Database helper module using SQLite."""

from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


def get_db_connection(db_path: str | Path) -> sqlite3.Connection:
    """Establish a connection to the SQLite database.

    Args:
        db_path: Path to the database file.

    Returns:
        sqlite3.Connection: Connection object with row_factory set and foreign keys enabled.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def insert_receipt(
    db_path: str | Path,
    receipt_id: str,
    source_path: str,
    ocr_json: Dict[str, Any] | None,
    normalized_json: Dict[str, Any] | None,
    clinic_id: str | None = None,
) -> None:
    """Insert a new receipt record into the database.

    Args:
        db_path: Path to the SQLite database.
        receipt_id: UUID string.
        source_path: Path of the source image or PDF.
        ocr_json: Raw OCR data as dict.
        normalized_json: Normalized data (date, amount, etc.) as dict.
        clinic_id: Optional clinic ID referencing clinics table.
    """
    ocr_str = json.dumps(ocr_json, ensure_ascii=False) if ocr_json is not None else None
    norm_str = json.dumps(normalized_json, ensure_ascii=False) if normalized_json is not None else None

    """
    コンテキストマネージャ（with conn:）として使用された場合、トランザクションのコミット/ロールバックのみを管理し、接続のクローズ（close()）は行いません。\n
    このため、with get_db_connection(db_path) as conn: のように呼び出すと、関数が終了してもデータベース接続（およびファイル記述子）がオープンされたままになり、コネクションリークが発生します。
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO receipts (id, source_path, ocr_json, normalized_json, clinic_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (receipt_id, str(source_path), ocr_str, norm_str, clinic_id),
            )
    finally:
        conn.close()


def get_receipt(db_path: str | Path, receipt_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a receipt from the database.

    Args:
        db_path: Path to the SQLite database.
        receipt_id: UUID string.

    Returns:
        Optional[Dict[str, Any]]: The receipt row as a dict, with JSON fields decoded,
                                  or None if not found.
    """
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, source_path, ocr_json, normalized_json, clinic_id, created_at
            FROM receipts
            WHERE id = ?
            """,
            (receipt_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        result = dict(row)
        if result["ocr_json"]:
            result["ocr_json"] = json.loads(result["ocr_json"])
        if result["normalized_json"]:
            result["normalized_json"] = json.loads(result["normalized_json"])
        return result
    finally:
        conn.close()


def upsert_clinic(db_path: str | Path, clinic_id: str, name: str) -> None:
    """Insert or update a clinic.

    Args:
        db_path: Path to the SQLite database.
        clinic_id: ID of the clinic.
        name: Name of the clinic.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO clinics (id, name)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET id = excluded.id
                """,
                (clinic_id, name),
            )
    finally:
        conn.close()


def get_clinic_by_name(db_path: str | Path, name: str) -> Optional[Dict[str, Any]]:
    """Retrieve a clinic by its name.

    Args:
        db_path: Path to the SQLite database.
        name: Name of the clinic.

    Returns:
        Optional[Dict[str, Any]]: The clinic row as a dict, or None if not found.
    """
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT id, name, created_at FROM clinics WHERE name = ?",
            (name,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


"""
get_clinic_by_name の接続リークを修正すると同時に、マルチプロセス環境での競合状態（レースコンディション）を安全に回避するための get_or_create_clinic ヘルパー関数を追加します。\n
これにより、同じクリニック名が同時に処理された場合でも、一意のクリニックIDを安全に取得・作成できるようになります。
"""


def get_or_create_clinic(db_path: str | Path, name: str) -> str:
    """Get the ID of a clinic by name, creating it if it doesn't exist.

    Args:
        db_path: Path to the SQLite database.
        name: Name of the clinic.

    Returns:
        str: The clinic ID.
    """
    import uuid

    clinic = get_clinic_by_name(db_path, name)
    if clinic:
        return clinic["id"]

    new_id = str(uuid.uuid4())
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO clinics (id, name) VALUES (?, ?)",
                (new_id, name),
            )
        return new_id
    except sqlite3.IntegrityError:
        clinic = get_clinic_by_name(db_path, name)
        if clinic:
            return clinic["id"]
        raise
    finally:
        conn.close()


def upsert_template(
    db_path: str | Path,
    template_id: str,
    clinic_id: str,
    version: int,
    coords_corrections: Dict[str, Any],
) -> None:
    """Upsert a template config for a clinic.

    Args:
        db_path: Path to the SQLite database.
        template_id: Unique template ID (UUID string).
        clinic_id: Associated clinic ID.
        version: Version number.
        coords_corrections: Dictionary containing OCR corrections.
    """
    coords_str = json.dumps(coords_corrections, ensure_ascii=False)
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO templates (id, clinic_id, version, coords_corrections)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    clinic_id = excluded.clinic_id,
                    version = excluded.version,
                    coords_corrections = excluded.coords_corrections
                """,
                (template_id, clinic_id, version, coords_str),
            )
    finally:
        conn.close()


def add_correction(
    db_path: str | Path,
    correction_id: str,
    receipt_id: str,
    field_name: str,
    old_value: str | None,
    new_value: str | None,
    user_id: str | None = None,
) -> None:
    """Add a user correction for a receipt and update its normalized_json in a single transaction.

    Args:
        db_path: Path to the SQLite database.
        correction_id: UUID string.
        receipt_id: ID of the receipt to correct.
        field_name: The field name being corrected (e.g. 'amount', 'date').
        old_value: Old value before correction.
        new_value: New corrected value.
        user_id: Optional ID of the user who made the correction.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            # Retrieve the current receipt within the transaction
            cursor = conn.execute(
                "SELECT normalized_json FROM receipts WHERE id = ?",
                (receipt_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Receipt with ID {receipt_id} does not exist.")

            norm_json_str = row["normalized_json"]
            norm_data = json.loads(norm_json_str) if norm_json_str else {}

            # Verify that the old value matches the current state to prevent race conditions
            current_value = norm_data.get(field_name)
            if str(current_value) != str(old_value):
                raise ValueError(f"Conflict: field '{field_name}' has changed since correction was initiated.")

            # Update the target field in the normalized JSON
            norm_data[field_name] = new_value
            updated_norm_json_str = json.dumps(norm_data, ensure_ascii=False)

            # Execute correction insertion and receipt normalized_json update
            conn.execute(
                """
                INSERT INTO corrections (id, receipt_id, field_name, old_value, new_value, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (correction_id, receipt_id, field_name, old_value, new_value, user_id),
            )
            conn.execute(
                "UPDATE receipts SET normalized_json = ? WHERE id = ?",
                (updated_norm_json_str, receipt_id),
            )
    finally:
        conn.close()


def insert_user(db_path: str | Path, user_id: str, name: str) -> None:
    """Insert a user.

    Args:
        db_path: Path to the SQLite database.
        user_id: ID of the user.
        name: Name of the user.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (id, name) VALUES (?, ?)",
                (user_id, name),
            )
    finally:
        conn.close()


def get_receipt_by_source_path(db_path: str | Path, source_path: str) -> Optional[Dict[str, Any]]:
    """Retrieve a receipt by its source_path.

    Args:
        db_path: Path to the SQLite database.
        source_path: The source path stored in the receipts table.

    Returns:
        Optional[Dict[str, Any]]: The receipt row as a dict with JSON fields decoded,
                                  or None if not found.
    """
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, source_path, ocr_json, normalized_json, clinic_id, created_at
            FROM receipts
            WHERE source_path = ?
            """,
            (source_path,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        result = dict(row)
        if result["ocr_json"]:
            result["ocr_json"] = json.loads(result["ocr_json"])
        if result["normalized_json"]:
            result["normalized_json"] = json.loads(result["normalized_json"])
        return result
    finally:
        conn.close()


def get_latest_template_by_clinic(db_path: str | Path, clinic_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the latest template (highest version) for a clinic.

    Args:
        db_path: Path to the SQLite database.
        clinic_id: The clinic ID.

    Returns:
        Optional[Dict[str, Any]]: The template row as a dict with coords_corrections decoded,
                                  or None if no template exists.
    """
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, clinic_id, version, coords_corrections, created_at
            FROM templates
            WHERE clinic_id = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (clinic_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        result = dict(row)
        if result["coords_corrections"]:
            result["coords_corrections"] = json.loads(result["coords_corrections"])
        return result
    finally:
        conn.close()


def insert_template_history(
    db_path: str | Path,
    history_id: str,
    template_id: str,
    clinic_id: str,
    version: int,
    coords_corrections: Dict[str, Any] | None,
    changed_fields: str | None,
    change_reason: str = "user_correction",
    receipt_id: str | None = None,
) -> None:
    """Insert a template history record before updating the template.

    Args:
        db_path: Path to the SQLite database.
        history_id: UUID string for the history record.
        template_id: The template ID.
        clinic_id: The clinic ID.
        version: The version number at the time of this snapshot.
        coords_corrections: The coords_corrections dict to snapshot.
        changed_fields: JSON string of field names that changed.
        change_reason: Reason for the change. Defaults to 'user_correction'.
        receipt_id: Optional receipt ID associated with the change.
    """
    coords_str = json.dumps(coords_corrections, ensure_ascii=False) if coords_corrections else None
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO template_history
                    (id, template_id, clinic_id, version, coords_corrections, changed_fields, change_reason, receipt_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (history_id, template_id, clinic_id, version, coords_str, changed_fields, change_reason, receipt_id),
            )
    finally:
        conn.close()
