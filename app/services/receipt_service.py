"""Receipt service: orchestrates receipt operations using separated components."""

from pathlib import Path
from typing import List, Dict, Any, Optional

from app.services.receipt_file_repository import ReceiptFileRepository
from app.services.receipt_database_repository import ReceiptDatabaseRepository
from app.services.receipt_normalizer import ReceiptNormalizer
from app.services.ocr_coordinate_service import OCRCoordinateService
from app.services.receipt_updater import ReceiptUpdater


class ReceiptService:
    """
    Service class for receipt operations.

    This class now acts as an orchestrator that coordinates the separated components:
    - ReceiptFileRepository: File I/O operations
    - ReceiptDatabaseRepository: Database operations
    - ReceiptNormalizer: Data normalization
    - OCRCoordinateService: Coordinate search and feedback
    - ReceiptUpdater: Update orchestration

    The original responsibilities have been distributed to these components,
    following the Single Responsibility Principle.
    """

    def __init__(
        self,
        output_dir: Path,
        db_path: Optional[Path] = None,
    ):
        """
        Initialize the service with separated components.

        Args:
            output_dir: Directory for JSON file storage.
            db_path: Optional path to SQLite database.
        """
        # Initialize repositories and services
        self.file_repo = ReceiptFileRepository(output_dir)
        self.db_repo = ReceiptDatabaseRepository(db_path)
        self.normalizer = ReceiptNormalizer()
        self.coord_service = OCRCoordinateService(db_path, output_dir)

        # Initialize the updater with all components
        self.updater = ReceiptUpdater(
            file_repo=self.file_repo,
            db_repo=self.db_repo,
            normalizer=self.normalizer,
            coord_service=self.coord_service,
        )

    def get_all_receipts(self) -> List[Dict[str, Any]]:
        """一覧表示用のデータを取得・整形する。"""
        items = []
        for file_path in self.file_repo.find_all_receipt_files():
            try:
                data = self.file_repo.load_receipt(file_path.stem.replace("-structured_data", ""))
                file_stem = file_path.stem.replace("-structured_data", "")
                clinic = data.get("clinic")
                date = data.get("date")
                if clinic and date:
                    display_name = f"{clinic}-{date} [{file_stem}]"
                else:
                    display_name = file_stem
                items.append(
                    {
                        "file_stem": file_stem,
                        "display_name": display_name,
                        "clinic": clinic,
                        "date": date,
                        "low_confidence": data.get("low_confidence", False),
                    }
                )
            except Exception as e:
                from app.error_logging import append_error

                append_error(self.file_repo.output_dir, str(file_path), str(e), "read_index", {})
                continue
        return items

    def get_receipt_detail(self, file_stem: str) -> Dict[str, Any]:
        """詳細表示用のデータを取得し、表示用フィールドに整形する。"""
        data = self.file_repo.load_receipt(file_stem)
        fields = [
            ("name", {"label": "氏名", "value": data.get("name", "")}),
            ("clinic", {"label": "クリニック名(調剤薬局名)", "value": data.get("clinic", "")}),
            ("amount", {"label": "支払い金額", "value": data.get("amount", "")}),
            ("date", {"label": "発行日", "value": data.get("date", "")}),
        ]
        return {"file_stem": file_stem, "fields": fields, "data": data}

    def update_receipt(self, file_stem: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a receipt with the given changes.

        This method delegates to the ReceiptUpdater which coordinates
        all the separated components for the update operation.

        Args:
            file_stem: The stem of the file to update.
            updates: Dictionary of field updates.

        Returns:
            Result dictionary with status, data, and feedback information.
        """
        return self.updater.update_receipt(file_stem, updates)
