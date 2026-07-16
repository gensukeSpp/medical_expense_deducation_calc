"""Image processing orchestrator.

ImageProcessingService is the single orchestrator for the OCR processing pipeline.
It coordinates:
1. OCR pipeline execution (via app.ocr_pipeline.process_image)
2. Coordinate normalization (via app.coord_normalizer.normalize_coordinates)
3. Structural parsing (via app.structural_parser.process_input_json)
4. Low-confidence flag augmentation (inline)

This service is used by both the CLI (app/processor.py) and the watcher (app/watcher.py).
"""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime

from paddleocr import PaddleOCR
from app.ocr_pipeline import process_image
from app.coord_normalizer import normalize_coordinates
from app.structural_parser import process_input_json
from app.input import read_json
from app.output import write_json_atomic

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """
    Orchestrator for single-image OCR processing.

    Coordinates the full pipeline: OCR → coordinate normalization →
    structural parsing → low-confidence flag augmentation.
    """

    def __init__(self, ocr_engine: PaddleOCR) -> None:
        self.ocr_engine = ocr_engine

    def process(
        self,
        image_path: Path,
        output_dir: Path,
        model: str,
        db_path: Path | str | None = None,
    ) -> None:
        """Run the full processing pipeline for a single image.

        Args:
            image_path: Path to the input image file.
            output_dir: Directory for output JSON files.
            model: LLM model name or 'mock' for local heuristic.
            db_path: Optional SQLite database path for persisting results.
        """
        # 1. File metadata
        mtime = self._get_mtime(image_path)

        # 2. Output path determination
        output_json_path = self._make_output_path(image_path, output_dir, mtime)

        # 3. OCR pipeline
        self._run_ocr(image_path, output_dir, output_json_path)

        # 4. Coordinate normalization
        low_confidence = self._normalize_coords(output_json_path)

        # 5. Structural parsing
        self._parse_structured(output_json_path, model, output_dir, db_path)

        # 6. Low-confidence flag augmentation
        if low_confidence:
            self._apply_low_confidence_flag(image_path, output_dir, mtime)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_mtime(image_path: Path) -> int:
        try:
            return int(image_path.stat().st_mtime)
        except Exception:
            return int(datetime.now().timestamp())

    @staticmethod
    def _make_output_path(image_path: Path, output_dir: Path, mtime: int) -> Path:
        out_fname = f"{image_path.stem}_{mtime}-raw_data.json"
        return output_dir / out_fname

    def _run_ocr(self, image_path: Path, output_dir: Path, output_json_path: Path) -> None:
        try:
            structured = process_image(
                image_path,
                output_dir=output_dir,
                output_json_path=output_json_path,
                ocr=self.ocr_engine,
            )
            if structured is None:
                logger.warning("process_image returned None for %s", image_path)
                return
            elif isinstance(structured, dict):
                logger.info("Saved 1 item to %s", output_json_path)
            else:
                logger.info("Saved %d items to %s", len(structured), output_json_path)
        except Exception:
            logger.exception("OCR pipeline failed for %s", image_path)
            raise

    @staticmethod
    def _normalize_coords(output_json_path: Path) -> bool:
        """Run coordinate normalization. Returns True if low_confidence flag should be set."""
        low_confidence = False
        try:
            norm_result = normalize_coordinates(output_json_path)
            low_confidence = norm_result.get("low_confidence", False)

            if norm_result.get("normalized"):
                logger.info(
                    "Normalized coordinates for %s (offset_x=%d, offset_y=%d)",
                    output_json_path,
                    norm_result["offset_x"],
                    norm_result["offset_y"],
                )
            elif low_confidence:
                logger.info(
                    "Skipped coordinate normalization for %s (topmost confidence=%.3f < 0.8)",
                    output_json_path,
                    norm_result.get("topmost_confidence", 0),
                )
        except Exception:
            logger.exception("Coordinate normalization failed for %s", output_json_path)
        return low_confidence

    @staticmethod
    def _parse_structured(
        output_json_path: Path,
        model: str,
        output_dir: Path,
        db_path: Path | str | None,
    ) -> None:
        try:
            process_input_json(
                output_json_path,
                model=model,
                output_dir=output_dir,
                db_path=db_path,
            )
            logger.info("Structured data generated for %s", output_json_path)
        except Exception:
            logger.exception("Failed to generate structured data for %s", output_json_path)
            raise

    @staticmethod
    def _apply_low_confidence_flag(image_path: Path, output_dir: Path, mtime: int) -> None:
        """Set low_confidence flag in the structured data JSON file."""
        try:
            structured_data_path = output_dir / f"{image_path.stem}_{mtime}-structured_data.json"
            if structured_data_path.exists():
                sd = read_json(structured_data_path)
                sd["low_confidence"] = True
                write_json_atomic(structured_data_path, sd)
                logger.info("Set low_confidence flag in %s", structured_data_path)
        except Exception:
            logger.exception("Failed to apply low_confidence flag for %s", image_path)
