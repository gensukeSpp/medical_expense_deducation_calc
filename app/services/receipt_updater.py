"""Receipt updater: orchestrates receipt update operations."""

from pathlib import Path
from typing import Dict, Any, Optional

from app.services.receipt_file_repository import ReceiptFileRepository
from app.services.receipt_database_repository import ReceiptDatabaseRepository
from app.services.receipt_normalizer import ReceiptNormalizer
from app.services.ocr_coordinate_service import OCRCoordinateService
from app.error_logging import append_error


class ReceiptUpdater:
    """
    Orchestrator for receipt update operations.

    Coordinates file I/O, database operations, normalization, and coordinate feedback
    to update a receipt while maintaining separation of concerns.
    """

    def __init__(
        self,
        file_repo: ReceiptFileRepository,
        db_repo: ReceiptDatabaseRepository,
        normalizer: ReceiptNormalizer,
        coord_service: OCRCoordinateService,
    ):
        """
        Initialize the updater.

        Args:
            file_repo: Repository for file operations.
            db_repo: Repository for database operations.
            normalizer: Service for data normalization.
            coord_service: Service for coordinate search and feedback.
        """
        self.file_repo = file_repo
        self.db_repo = db_repo
        self.normalizer = normalizer
        self.coord_service = coord_service

    def update_receipt(
        self,
        file_stem: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update a receipt with the given changes.

        Orchestrates the following steps:
        1. Load existing data from file
        2. Apply updates and normalize data
        3. Update database via repository (corrections, clinic ID)
        4. Process coordinate feedback via coord service
        5. Save updated data to file

        Args:
            file_stem: The stem of the file to update.
            updates: Dictionary of field updates.

        Returns:
            Result dictionary with status, data, and feedback information.
        """
        file_path = self.file_repo.output_dir / f"{file_stem}-structured_data.json"

        # Step 1: Load existing data
        try:
            old_data = self.file_repo.load_receipt(file_stem)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check low_confidence flag — skip template updates when OCR quality is low
        low_confidence = old_data.get("low_confidence", False)

        # Step 2: Apply updates and normalize
        updated_data = self.normalizer.normalize(updates, old_data)

        # Step 3: Database updates (delegated to repository)
        feedback_info: Dict[str, Any] = {"receipt_id": None, "clinic_id": None}
        if self.db_repo.is_available():
            try:
                feedback_info = self.db_repo.apply_receipt_updates(
                    file_stem=file_stem,
                    file_path=file_path,
                    old_data=old_data,
                    updated_data=updated_data,
                    updates=updates,
                )
            except Exception as e:
                append_error(
                    self.file_repo.output_dir,
                    str(file_path),
                    str(e),
                    "update_item_db",
                    {},
                )

        # Step 4: Coordinate feedback (skip if low confidence — don't update templates)
        feedback_result = None
        if not low_confidence:
            feedback_result = self.coord_service.process_feedback(
                file_stem=file_stem,
                file_path=file_path,
                old_data=old_data,
                updates=updates,
                receipt_id=feedback_info.get("receipt_id"),
                clinic_id=feedback_info.get("clinic_id"),
            )

        # Step 5: Save updated data to file
        self.file_repo.save_receipt(file_stem, updated_data)

        # Build result
        coord_errors: list = []
        if feedback_result and feedback_result.get("not_found_fields"):
            coord_errors = feedback_result["not_found_fields"]

        return {
            "status": "updated",
            "data": updated_data,
            "coord_errors": coord_errors,
            "feedback_result": feedback_result,
        }
