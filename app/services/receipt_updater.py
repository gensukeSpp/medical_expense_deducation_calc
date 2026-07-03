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

        This method orchestrates the following steps:
        1. Load existing data from file
        2. Apply updates and normalize data
        3. Update database (corrections, clinic ID)
        4. Process coordinate feedback
        5. Save updated data to file

        Args:
            file_stem: The stem of the file to update.
            updates: Dictionary of field updates.

        Returns:
            Result dictionary with status, data, and feedback information.
        """
        file_path = self.file_repo.output_dir / f"{file_stem}-structured_data.json"

        try:
            # Step 1: Load existing data
            old_data = self.file_repo.load_receipt(file_stem)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")

        # Step 2: Apply updates and normalize
        updated_data = self.normalizer.normalize(updates, old_data)

        # Initialize tracking variables
        receipt_id_for_feedback: Optional[str] = None
        clinic_id_for_feedback: Optional[str] = None
        feedback_result = None
        coord_errors: list = []

        # Step 3: Database operations (if database is available)
        if self.db_repo.is_available():
            try:
                # Get or create receipt record
                receipt = self.db_repo.get_receipt_by_id(file_stem)
                if receipt:
                    receipt_id_for_feedback = receipt["id"]
                    clinic_id_for_feedback = receipt.get("clinic_id")
                else:
                    receipt_id_for_feedback = file_stem
                    source_path = str(file_path)
                    self.db_repo.insert_receipt(
                        receipt_id=receipt_id_for_feedback,
                        source_path=source_path,
                        ocr_json=None,
                        normalized_json=old_data,
                        clinic_id=None,
                    )

                # Add corrections for each updated field
                for field_name, new_value in updates.items():
                    old_value = old_data.get(field_name)
                    self.db_repo.add_correction(
                        receipt_id=receipt_id_for_feedback,
                        field_name=field_name,
                        old_value=str(old_value) if old_value is not None else None,
                        new_value=str(new_value) if new_value is not None else None,
                    )

                # Update clinic ID if needed
                current_clinic = updated_data.get("clinic")
                if clinic_id_for_feedback is None and current_clinic:
                    try:
                        clinic_id_for_feedback = self.db_repo.get_or_create_clinic(str(current_clinic))
                    except RuntimeError:
                        # Database not available, skip clinic update
                        clinic_id_for_feedback = None

                if clinic_id_for_feedback:
                    self.db_repo.update_receipt_clinic_id(receipt_id_for_feedback, clinic_id_for_feedback)

                # Step 4: Process coordinate feedback
                feedback_result = self._process_coordinate_feedback(
                    file_stem=file_stem,
                    file_path=file_path,
                    old_data=old_data,
                    updated_data=updated_data,
                    updates=updates,
                    receipt_id=receipt_id_for_feedback,
                    clinic_id=clinic_id_for_feedback,
                )

            except Exception as e:
                append_error(
                    self.file_repo.output_dir,
                    str(file_path),
                    str(e),
                    "update_item_db",
                    {},
                )

        # Step 5: Save updated data to file
        self.file_repo.save_receipt(file_stem, updated_data)

        # Build result
        if feedback_result and feedback_result.get("not_found_fields"):
            coord_errors = feedback_result["not_found_fields"]

        return {
            "status": "updated",
            "data": updated_data,
            "coord_errors": coord_errors,
            "feedback_result": feedback_result,
        }

    def _process_coordinate_feedback(
        self,
        file_stem: str,
        file_path: Path,
        old_data: Dict[str, Any],
        updated_data: Dict[str, Any],
        updates: Dict[str, Any],
        receipt_id: str,
        clinic_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Process coordinate feedback for the updated receipt.

        Args:
            file_stem: The file stem.
            file_path: Path to the structured data file.
            old_data: Previous data before updates.
            updated_data: Data after updates.
            updates: The applied updates.
            receipt_id: The receipt ID.
            clinic_id: The clinic ID.

        Returns:
            Feedback result dictionary, or None if no feedback was processed.
        """
        if not clinic_id:
            return None

        try:
            # Build field queries from updates
            field_queries = {}
            for field_name, new_value in updates.items():
                old_value = old_data.get(field_name)
                query_val = old_value if old_value is not None else new_value
                if query_val is not None:
                    field_queries[field_name] = str(query_val)

            # Get raw data path (for potential future use)
            _ = sorted(self.file_repo.find_all_receipt_files())

            # Get OCR entries
            ocr_entries = self.file_repo.get_ocr_entries(file_stem)

            if ocr_entries and field_queries:
                coord_results = {}
                template_coords = None

                if clinic_id:
                    template = self.db_repo.get_latest_template_by_clinic(clinic_id)
                    if template:
                        template_coords = template.get("coords_corrections")

                if template_coords and ocr_entries:
                    from app.coord_search import search_by_proximity_multi

                    proximity_results = search_by_proximity_multi(ocr_entries, template_coords)
                    for field_name, match in proximity_results.items():
                        if match and match.get("box"):
                            coord_results[field_name] = match["box"]
                        else:
                            coord_results[field_name] = None
                else:
                    from app.coord_search import search_coordinates

                    for field_name, query in field_queries.items():
                        coord_results[field_name] = search_coordinates(ocr_entries, query) if ocr_entries else None

                return self.coord_service._process_correction_feedback(
                    clinic_id=clinic_id,
                    field_coords_map=coord_results,
                    receipt_id=receipt_id,
                )

        except Exception as e:
            append_error(
                self.file_repo.output_dir,
                str(file_path),
                str(e),
                "coordinate_feedback",
                {"updates": updates},
            )

        return None
