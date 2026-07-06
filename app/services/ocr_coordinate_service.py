"""OCR coordinate service: handles coordinate search and feedback logic."""

from pathlib import Path
from typing import Dict, Any, Optional, List

from app.coord_search import search_coordinates, search_by_proximity_multi
from app.template_feedback import process_correction_feedback
from app.db import get_receipt, get_latest_template_by_clinic
from app.error_logging import append_error


class OCRCoordinateService:
    """Service for handling OCR coordinate search and feedback."""

    def __init__(self, db_path: Optional[Path], output_dir: Optional[Path] = None):
        """
        Initialize the service.

        Args:
            db_path: Path to the SQLite database.
            output_dir: Optional directory for raw data files.
        """
        self.db_path = db_path
        self.output_dir = output_dir

    # def update_coordinates(
    #     self,
    #     receipt_id: str,
    #     updated_data: Dict[str, Any],
    #     file_stem: str,
    #     raw_data_json_path: Optional[Path] = None,
    # ) -> Optional[Dict[str, Any]]:
    #     """
    #     Update coordinates based on user corrections.

    #     Args:
    #         receipt_id: The receipt ID.
    #         updated_data: The updated receipt data.
    #         file_stem: The file stem for the receipt.
    #         raw_data_json_path: Optional path to raw data file.

    #     Returns:
    #         Feedback result dictionary, or None if no feedback was processed.
    #     """
    #     if not self.db_path:
    #         return None

    #     try:
    #         # Get OCR entries
    #         ocr_entries = self._get_ocr_entries(receipt_id, file_stem, raw_data_json_path)

    #         if not ocr_entries or not updated_data:
    #             return None

    #         # Build field queries from updates
    #         field_queries = {}
    #         for field_name, new_value in updated_data.items():
    #             if new_value is not None:
    #                 field_queries[field_name] = str(new_value)

    #         coord_results: Dict[str, Optional[List[List[int]]]] = {}
    #         template_coords = None

    #         # Get clinic ID from receipt
    #         receipt = get_receipt(self.db_path, receipt_id)
    #         clinic_id = receipt.get("clinic_id") if receipt else None

    #         if clinic_id:
    #             template = get_latest_template_by_clinic(self.db_path, clinic_id)
    #             if template:
    #                 template_coords = template.get("coords_corrections")

    #         # Search coordinates
    #         if template_coords and ocr_entries:
    #             proximity_results = search_by_proximity_multi(ocr_entries, template_coords)
    #             for field_name, match in proximity_results.items():
    #                 if match and match.get("box"):
    #                     coord_results[field_name] = match["box"]
    #                 else:
    #                     coord_results[field_name] = None
    #         else:
    #             for field_name, query in field_queries.items():
    #                 coord_results[field_name] = search_coordinates(ocr_entries, query) if ocr_entries else None

    #         # Process feedback if clinic_id is available
    #         if clinic_id:
    #             return process_correction_feedback(
    #                 db_path=self.db_path,
    #                 clinic_id=clinic_id,
    #                 field_coords_map=coord_results,
    #                 receipt_id=receipt_id,
    #             )

    #     except Exception as e:
    #         file_path = str(self.output_dir / f"{file_stem}-structured_data.json") if self.output_dir else file_stem
    #         append_error(
    #             self.output_dir or Path("."), file_path, str(e), "coordinate_update", {"receipt_id": receipt_id}
    #         )

    #     return None
    # Deprecated: Coordinate feedback is now handled by process_feedback().
    # This method is kept for reference only and will be removed in a future cleanup.

    def process_feedback(
        self,
        file_stem: str,
        file_path: Path,
        old_data: Dict[str, Any],
        updates: Dict[str, Any],
        receipt_id: Optional[str],
        clinic_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Process coordinate feedback for a receipt update.

        Handles OCR entry retrieval, coordinate search (text + proximity),
        and template feedback in one call. This is the SRP-compliant
        replacement for the old ReceiptUpdater._process_coordinate_feedback.

        Args:
            file_stem: The file stem.
            file_path: Path to the structured data file.
            old_data: Previous data before updates.
            updates: The applied updates.
            receipt_id: The receipt ID.
            clinic_id: The clinic ID.

        Returns:
            Feedback result dictionary, or None if no feedback was processed.
        """
        if not clinic_id:
            return None

        try:
            # Build field queries from updates (with empty string fallback)
            field_queries: Dict[str, str] = {}
            for field_name, new_value in updates.items():
                if new_value is None or str(new_value).strip() == "":
                    continue
                old_value = old_data.get(field_name)
                query_val = old_value if old_value not in (None, "") else new_value  # Bug A: treat "" like None
                if query_val is not None:
                    field_queries[field_name] = str(query_val)

            if not field_queries:
                return None

            # Get OCR entries (DB first, then fallback to file)
            raw_data_json_path: Optional[Path] = None
            if self.output_dir:
                raw_data_json_path = self.output_dir / f"{file_stem}-raw_data.json"
            ocr_entries = self._get_ocr_entries(receipt_id or file_stem, file_stem, raw_data_json_path)

            if not ocr_entries:
                return None

            # Text search for corrected fields
            from app.coord_search import search_coordinates

            coord_results: Dict[str, Any] = {}
            for field_name, query in field_queries.items():
                coord_results[field_name] = search_coordinates(ocr_entries, query)

            # Proximity search for template fields (Bug B: both searches run)
            if clinic_id:
                template = get_latest_template_by_clinic(self.db_path, clinic_id)
                if template and template.get("coords_corrections"):
                    from app.coord_search import search_by_proximity_multi

                    proximity_results = search_by_proximity_multi(ocr_entries, template["coords_corrections"])
                    for field_name, match in proximity_results.items():
                        """
                        レイアウト変更などで座標が移動した場合に、テキスト検索で得られた新しい正確な座標が古い座標（またはその近傍の誤ったテキストの座標）で上書きされてしまい、テンプレートが正しく更新されなくなります。\n
                        修正対象のフィールドについては近接検索による上書きをスキップするように修正すべきです。
                        """
                        if field_name in field_queries:
                            continue
                        if match and match.get("box"):
                            coord_results[field_name] = match["box"]
                        elif field_name not in coord_results:
                            coord_results[field_name] = None

            return self._process_correction_feedback(
                clinic_id=clinic_id,
                field_coords_map=coord_results,
                receipt_id=receipt_id,
            )

        except Exception as e:
            append_error(
                self.output_dir or Path("."),
                str(file_path),
                str(e),
                "coordinate_feedback",
                {"updates": updates},
            )
            return None

    def _get_ocr_entries(
        self,
        receipt_id: str,
        file_stem: str,
        raw_data_json_path: Optional[Path] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get OCR entries from database or raw data file.

        Args:
            receipt_id: The receipt ID.
            file_stem: The file stem.
            raw_data_json_path: Optional path to raw data file.

        Returns:
            List of OCR entry dictionaries, or None if not available.
        """
        ocr_entries = None

        # Try to get from database
        receipt = get_receipt(self.db_path, receipt_id) if self.db_path else None
        if receipt:
            ocr_json = receipt.get("ocr_json")
            if isinstance(ocr_json, list):
                ocr_entries = ocr_json
            elif isinstance(ocr_json, dict) and "words" in ocr_json:
                ocr_entries = ocr_json.get("words", [])
            elif isinstance(ocr_json, dict) and "text_lines" in ocr_json:
                ocr_entries = [{"text": t} for t in ocr_json["text_lines"]]

        # Fallback to raw data file by trying multiple patterns
        if ocr_entries is None and self.output_dir:
            # Try the exact path first
            if raw_data_json_path and raw_data_json_path.exists():
                ocr_entries = self._load_raw_data(raw_data_json_path)
            # Try file_stem-based patterns (same as ReceiptFileRepository.get_ocr_entries)
            if ocr_entries is None:
                import glob as glob_mod

                patterns = [
                    str(self.output_dir / f"{file_stem}*-raw_data.json"),
                    str(self.output_dir / f"{file_stem}.json"),
                ]
                for pattern in patterns:
                    matches = sorted(glob_mod.glob(pattern))
                    if matches:
                        ocr_entries = self._load_raw_data(Path(matches[-1]))
                        if ocr_entries:
                            break

        return ocr_entries

    def _load_raw_data(self, path: Path) -> Optional[List[Dict[str, Any]]]:
        """Load OCR entries from a raw data file."""
        try:
            from app.input import read_json

            raw_data = read_json(path)
            if isinstance(raw_data, list):
                return raw_data
            if isinstance(raw_data, dict):
                if "words" in raw_data:
                    return raw_data["words"]
                if "text_lines" in raw_data:
                    return [{"text": t} for t in raw_data["text_lines"]]
        except Exception as e:
            append_error(self.output_dir or Path("."), str(path), str(e), "fallback_raw_data_read", {})
        return None

    def _process_correction_feedback(
        self,
        clinic_id: str,
        field_coords_map: Dict[str, Optional[List[List[int]]]],
        receipt_id: str,
    ) -> Dict[str, Any]:
        """
        Process correction feedback using template_feedback module.

        Args:
            clinic_id: The clinic ID.
            field_coords_map: Mapping of field names to box coordinates.
            receipt_id: The receipt ID.

        Returns:
            Feedback result dictionary.
        """
        if self.db_path is None:
            raise RuntimeError("Database is not available")
        return process_correction_feedback(
            db_path=self.db_path,
            clinic_id=clinic_id,
            field_coords_map=field_coords_map,
            receipt_id=receipt_id,
        )
