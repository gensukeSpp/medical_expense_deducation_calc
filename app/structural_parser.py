from __future__ import annotations

import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.input import read_json
from app.llm_extractor import get_llm_client
from app.normalization import normalize_extracted
from app.output import write_json_atomic
from app.error_logging import append_error
from app.db import insert_receipt, get_or_create_clinic, get_latest_template_by_clinic
from app.coord_search import search_by_proximity_multi

logger = logging.getLogger(__name__)

# Default pixel proximity threshold for coordinate-based template matching.
DEFAULT_PROXIMITY_THRESHOLD: float = 20.0


class OCRResultLoader:
    """Responsible for loading OCR JSON files."""

    @staticmethod
    def load(input_path: Path | str) -> Dict[str, Any]:
        path = Path(input_path)
        return read_json(path)


class ExtractionService:
    """Responsible for extracting data using LLM and template-based proximity matching."""

    def __init__(self, model: str, db_path: Optional[Path | str] = None):
        self.model = model
        self.db_path = db_path if isinstance(db_path, Path) else Path(db_path) if db_path else None

    def extract(self, ocr_json: Dict[str, Any]) -> Dict[str, Any]:
        client = get_llm_client(self.model)
        extracted = client.extract_fields(ocr_json)

        # Template-based proximity extraction (MockLLMClient only)
        if self.model == "mock" and self.db_path and extracted.get("clinic"):
            extracted = self._apply_template_corrections(ocr_json, extracted)

        return extracted

    def _apply_template_corrections(self, ocr_json: Dict[str, Any], extracted: Dict[str, Any]) -> Dict[str, Any]:
        if self.db_path is None:
            return extracted

        try:
            clinic_name = str(extracted["clinic"]).strip()
            if clinic_name:
                clinic_id = get_or_create_clinic(self.db_path, clinic_name)
                template = get_latest_template_by_clinic(self.db_path, clinic_id)
                coords = template.get("coords_corrections") if template else None
                if coords:
                    ocr_entries: List[Dict[str, Any]] = []
                    if isinstance(ocr_json, list):
                        ocr_entries = ocr_json
                    elif isinstance(ocr_json, dict):
                        words = ocr_json.get("words", [])
                        if words:
                            ocr_entries = words
                        # text_lines は box なし → 近接検索不可、スキップ

                    if ocr_entries:
                        proximity_results = search_by_proximity_multi(
                            ocr_entries,
                            coords,
                            threshold=DEFAULT_PROXIMITY_THRESHOLD,
                        )
                        for field_name, match in proximity_results.items():
                            if match and match.get("text") and field_name in extracted:
                                extracted[field_name] = match["text"]
        except Exception as e:
            logger.error(f"Template proximity correction failed: {e}")
        return extracted


class DataNormalizationService:
    """Responsible for normalizing extracted data."""

    def normalize(self, extracted: Dict[str, Any], ocr_json: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_extracted(extracted, ocr_json)


class ReceiptRepository:
    """Responsible for persisting receipt data to the database."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = db_path if isinstance(db_path, Path) else Path(db_path) if db_path else None

    def save(
        self,
        receipt_id: str,
        source_path: Path,
        ocr_json: Dict[str, Any],
        structured: Dict[str, Any],
        clinic_id: Optional[str],
    ) -> None:
        if not self.db_path:
            return

        insert_receipt(
            db_path=self.db_path,
            receipt_id=receipt_id,
            source_path=str(source_path),
            ocr_json=ocr_json,
            normalized_json=structured,
            clinic_id=clinic_id,
        )


class OutputWriter:
    """Responsible for writing structured data to files."""

    def write(self, output_dir: Path, input_path: Path, structured: Dict[str, Any]) -> None:
        out_name = f"{input_path.stem}-structured_data.json"
        out_path = output_dir / out_name
        write_json_atomic(out_path, structured)


class ReceiptProcessingService:
    """Orchestrator for the receipt processing workflow."""

    def __init__(
        self,
        extractor: ExtractionService,
        normalizer: DataNormalizationService,
        repository: ReceiptRepository,
        writer: OutputWriter,
        loader: OCRResultLoader,
    ):
        self.extractor = extractor
        self.normalizer = normalizer
        self.repository = repository
        self.writer = writer
        self.loader = loader

    def process(self, input_path: Path | str, output_dir: Path | str) -> Optional[Dict[str, Any]]:
        input_path = Path(input_path)
        output_dir = Path(output_dir)

        # 1. Load
        try:
            ocr_json = self.loader.load(input_path)
        except Exception as e:
            append_error(output_dir, str(input_path), str(e), "read_input", {})
            return None

        # 2. Extract
        try:
            extracted = self.extractor.extract(ocr_json)
        except Exception as e:
            append_error(output_dir, str(input_path), str(e), "llm_extract", {})
            extracted = {"name": None, "clinic": None, "amount": None, "date": None}

        # 3. Normalize
        try:
            structured = self.normalizer.normalize(extracted, ocr_json)
        except Exception as e:
            append_error(output_dir, str(input_path), str(e), "normalization", {"extracted": extracted})
            structured = extracted

        # 4. Write Output
        try:
            self.writer.write(output_dir, input_path, structured)
        except Exception as e:
            append_error(output_dir, str(input_path), str(e), "write_output", {"structured": structured})
            return None

        # 5. Persist
        try:
            clinic_name = structured.get("clinic")
            clinic_id = None
            if clinic_name:
                clinic_name = str(clinic_name).strip()
                if clinic_name and self.repository.db_path:
                    clinic_id = get_or_create_clinic(self.repository.db_path, clinic_name)

            receipt_id = str(uuid.uuid4())
            self.repository.save(receipt_id, input_path, ocr_json, structured, clinic_id)
        except Exception as e:
            append_error(
                output_dir,
                str(input_path),
                f"DB persistence failed: {e}",
                "db_persistence",
                {"structured": structured},
            )

        return structured


def process_input_json(
    input_path: Path | str,
    model: str = "mock",
    output_dir: Path | str = "output_json",
    db_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Legacy entry point for backward compatibility."""
    extractor = ExtractionService(model, db_path)
    normalizer = DataNormalizationService()
    repository = ReceiptRepository(db_path)
    writer = OutputWriter()
    loader = OCRResultLoader()

    service = ReceiptProcessingService(
        extractor=extractor, normalizer=normalizer, repository=repository, writer=writer, loader=loader
    )
    return service.process(input_path, output_dir)
