"""Receipt normalizer: handles data normalization logic."""

from typing import Dict, Any, Optional

from app.normalization import normalize_extracted


class ReceiptNormalizer:
    """Service for normalizing receipt data."""

    def normalize(self, updates: Dict[str, Any], old_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize updated receipt data.

        Args:
            updates: The new values to apply.
            old_data: The existing data before updates.

        Returns:
            Normalized data dictionary.
        """
        updated_data = {**old_data, **updates}
        return normalize_extracted(updated_data, old_data)

    def normalize_amount(self, text: Optional[str]) -> Optional[int]:
        """
        Normalize amount text to integer.

        Args:
            text: Amount text (e.g., '3,800円', '一万二千円').

        Returns:
            Integer amount in JPY, or None if parsing fails.
        """
        from app.normalization import parse_amount

        return parse_amount(text) if text else None

    def normalize_date(self, text: Optional[str]) -> Optional[str]:
        """
        Normalize date text to ISO format.

        Args:
            text: Date text (e.g., '2026/01/15', '2026年1月15日').

        Returns:
            ISO format date string (YYYY-MM-DD), or None if parsing fails.
        """
        from app.normalization import parse_date

        return parse_date(text) if text else None
