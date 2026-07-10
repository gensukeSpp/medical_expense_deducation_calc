"""OCR coordinate service: handles coordinate search and feedback logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.coord_search import search_by_proximity_multi
from app.error_logging import append_error
from app.services.ocr_search_strategies import MultiBoxSubstringStrategy, TextSearchStrategy
from app.services.receipt_database_repository import ReceiptDatabaseRepository
from app.template_feedback import process_correction_feedback


class OCRCoordinateRepositoryAdapter:
    """Adapter that exposes the repository interface expected by the coordinate service."""

    def __init__(self, repository: Any, output_dir: Optional[Path] = None):
        self._repository = repository
        self.output_dir = output_dir

    @property
    def db_path(self) -> Optional[Path]:
        if hasattr(self._repository, "db_path"):
            return getattr(self._repository, "db_path")
        return None

    def get_ocr_entries(self, receipt_id: Optional[str], file_stem: str) -> Optional[List[Dict[str, Any]]]:
        if hasattr(self._repository, "get_ocr_entries"):
            return self._repository.get_ocr_entries(receipt_id, file_stem)

        if hasattr(self._repository, "get_receipt_by_id") and receipt_id:
            receipt = self._repository.get_receipt_by_id(receipt_id)
            if receipt:
                ocr_entries = receipt.get("ocr_json")
                if isinstance(ocr_entries, list):
                    return ocr_entries
                # 移行前のコード（旧 _get_ocr_entries）では dict 形式も考慮されていましたが、新しい実装では isinstance(ocr_entries, list) の判定のみとなっており...
                # ↑ https://github.com/gensukeSpp/medical_expense_deducation_calc/pull/30
                # 【注意】おそらく SRP レビュー対応のとき、ここを変更する際は、要確認!!
                if isinstance(ocr_entries, dict):
                    if "words" in ocr_entries:
                        return ocr_entries["words"]
                    if "text_lines" in ocr_entries:
                        return [{"text": t} for t in ocr_entries["text_lines"]]
                    return ocr_entries.get("ocr_entries") or ocr_entries.get("ocr_json") or ocr_entries.get("data")

        if self.output_dir:
            candidates = [self.output_dir / f"{file_stem}-raw_data.json"]
            candidates.extend(self.output_dir.glob(f"{file_stem}*-raw_data.json"))

            for raw_path in candidates:
                if not raw_path.exists():
                    continue
                with raw_path.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("ocr_entries") or data.get("ocr_json") or data.get("data")

        return None

    def get_latest_template_by_clinic(self, clinic_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if clinic_id is None:
            return None
        if hasattr(self._repository, "get_latest_template_by_clinic"):
            return self._repository.get_latest_template_by_clinic(clinic_id)
        return None


class OCRCoordinateService:
    """Service for handling OCR coordinate search and feedback."""

    def __init__(
        self,
        repository: Any = None,
        search_strategies: Optional[List[Any] | Any] = None,
        feedback_processor: Any = None,
        output_dir: Optional[Path] = None,
        db_path: Optional[Path] = None,
    ):
        """Initialize the service.

        The constructor is intentionally backward-compatible with the earlier
        signature that accepted a DB path directly, while still supporting
        repository injection for the SRP-oriented architecture.
        """
        if isinstance(repository, (str, Path)) and db_path is None:
            db_path = Path(repository)
            repository = None

        if output_dir is None and isinstance(search_strategies, (str, Path)):
            output_dir = Path(search_strategies)
            search_strategies = None

        if db_path is not None and repository is None:
            repository = ReceiptDatabaseRepository(db_path)

        self.output_dir = Path(output_dir) if output_dir is not None else None
        self.db_path = Path(db_path) if db_path is not None else None
        self.repository = OCRCoordinateRepositoryAdapter(
            repository or ReceiptDatabaseRepository(self.db_path), self.output_dir
        )

        if search_strategies is None:
            self.search_strategies: List[Any] = [TextSearchStrategy(), MultiBoxSubstringStrategy()]
        elif isinstance(search_strategies, list):
            self.search_strategies = search_strategies
        else:
            self.search_strategies = [search_strategies]

        self.feedback_processor = feedback_processor or process_correction_feedback

    def _build_field_queries(self, old_data: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, str]:
        field_queries: Dict[str, str] = {}
        for field_name, new_value in updates.items():
            if new_value is None or str(new_value).strip() == "":
                continue
            # Use the new value as the query for coordinate search
            query_val = new_value
            if query_val is not None:
                field_queries[field_name] = str(query_val)
        return field_queries

    def _resolve_coord_results(
        self, ocr_entries: List[Dict[str, Any]], field_queries: Dict[str, str], clinic_id: Optional[str]
    ) -> Dict[str, Any]:
        coord_results: Dict[str, Any] = {}

        for field_name, query in field_queries.items():
            coord = None
            for strategy in self.search_strategies:
                coord = strategy.search(ocr_entries, query)
                if coord is not None:
                    break
            coord_results[field_name] = coord

        template = self.repository.get_latest_template_by_clinic(clinic_id)
        if template and template.get("coords_corrections"):
            proximity_results = search_by_proximity_multi(ocr_entries, template["coords_corrections"])
            for field_name, match in proximity_results.items():
                # 修正対象のフィールドに対してすでに検索戦略で新しい座標が見つかっている場合はスキップする
                if field_name in field_queries and coord_results.get(field_name) is not None:
                    continue
                if match and match.get("box"):
                    coord_results[field_name] = match["box"]
                elif field_name not in coord_results:
                    coord_results[field_name] = None

        return coord_results

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
            field_queries = self._build_field_queries(old_data, updates)
            if not field_queries:
                return None

            # Get OCR entries via repository
            ocr_entries = self.repository.get_ocr_entries(receipt_id or file_stem, file_stem)
            if not ocr_entries:
                return None

            coord_results = self._resolve_coord_results(ocr_entries, field_queries, clinic_id)
            """
            リポジトリのみがインジェクションされて db_path が直接渡されなかった場合、self.db_path は None になります。\n
            この場合、self.repository.db_path から取得できるデータベースパスを利用するようにフォールバックしないと、feedback_processor が None を受け取ってエラーになります。
            """
            resolved_db_path = self.db_path or self.repository.db_path

            if hasattr(self.feedback_processor, "process"):
                return self.feedback_processor.process(
                    db_path=resolved_db_path,
                    clinic_id=clinic_id,
                    field_coords_map=coord_results,
                    receipt_id=receipt_id,
                )

            return self.feedback_processor(
                db_path=resolved_db_path,
                clinic_id=clinic_id,
                field_coords_map=coord_results,
                receipt_id=receipt_id,
            )

        except Exception as exc:
            append_error(
                self.output_dir or Path("."),
                str(file_path),
                str(exc),
                "coordinate_feedback",
                {"updates": updates},
            )
            return None
