"""Receipt database repository: handles database operations for receipts."""

from pathlib import Path
from typing import Dict, Any, Optional

from app.db import (
    insert_receipt,
    get_receipt,
    add_correction,
    get_receipt_by_source_path,
    get_or_create_clinic,
    get_db_connection,
    get_latest_template_by_clinic,
)


class ReceiptDatabaseRepository:
    """Repository for handling database operations related to receipts."""

    def __init__(self, db_path: Optional[Path]):
        """
        Initialize the repository.

        Args:
            db_path: Path to the SQLite database, or None if no database is used.
        """
        self.db_path = db_path

    def is_available(self) -> bool:
        """
        Check if database operations are available.

        Returns:
            True if db_path is set, False otherwise.
        """
        return self.db_path is not None

    def get_receipt_by_id(self, receipt_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a receipt by its ID.

        Args:
            receipt_id: The UUID string of the receipt.

        Returns:
            Receipt data as a dictionary, or None if not found.
        """
        if not self.is_available():
            return None
        return get_receipt(self.db_path, receipt_id)

    def get_receipt_by_source_path(self, source_path: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a receipt by its source path.

        Args:
            source_path: The source path stored in the receipts table.

        Returns:
            Receipt data as a dictionary, or None if not found.
        """
        if not self.is_available():
            return None
        return get_receipt_by_source_path(self.db_path, source_path)

    def insert_receipt(
        self,
        receipt_id: str,
        source_path: str,
        ocr_json: Optional[Dict[str, Any]],
        normalized_json: Optional[Dict[str, Any]],
        clinic_id: Optional[str] = None,
    ) -> None:
        """
        Insert a new receipt record.

        Args:
            receipt_id: UUID string for the receipt.
            source_path: Path of the source image or PDF.
            ocr_json: Raw OCR data as dict.
            normalized_json: Normalized data as dict.
            clinic_id: Optional clinic ID.
        """
        if not self.is_available():
            return
        insert_receipt(self.db_path, receipt_id, source_path, ocr_json, normalized_json, clinic_id)

    def add_correction(
        self,
        receipt_id: str,
        field_name: str,
        old_value: Optional[str],
        new_value: Optional[str],
    ) -> None:
        """
        Add a correction record for a receipt.

        Args:
            receipt_id: ID of the receipt.
            field_name: The field name being corrected.
            old_value: Old value before correction.
            new_value: New corrected value.
        """
        if not self.is_available():
            return
        add_correction(self.db_path, receipt_id, field_name, old_value, new_value)

    def get_or_create_clinic(self, name: str) -> str:
        """
        Get or create a clinic by name.

        Args:
            name: Name of the clinic.

        Returns:
            The clinic ID.
        """
        if not self.is_available():
            raise RuntimeError("Database is not available")
        return get_or_create_clinic(self.db_path, name)

    def get_latest_template_by_clinic(self, clinic_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest template for a clinic.

        Args:
            clinic_id: The clinic ID.

        Returns:
            Template data as a dictionary, or None if not found.
        """
        if not self.is_available():
            return None
        return get_latest_template_by_clinic(self.db_path, clinic_id)

    def update_receipt_clinic_id(self, receipt_id: str, clinic_id: str) -> None:
        """
        Update the clinic_id for a receipt.

        Args:
            receipt_id: The receipt ID.
            clinic_id: The new clinic ID.
        """
        if not self.is_available():
            return
        conn = get_db_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    "UPDATE receipts SET clinic_id = ? WHERE id = ?",
                    (clinic_id, receipt_id),
                )
        finally:
            conn.close()
