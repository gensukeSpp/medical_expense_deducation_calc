"""CLI entry point for single-image processing.

This module is the CLI layer for processing a single image.
It handles:
- Argument validation (image_name existence, path safety)
- Error reporting via sys.exit (CLI-appropriate behaviour)
- Delegation of business logic to ImageProcessingService

It does NOT contain any OCR, normalization, or parsing logic.
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path

from paddleocr import PaddleOCR
from app.services.image_processing_service import ImageProcessingService


def process_single_image(
    image_name: str,
    input_dir: Path,
    output_dir: Path,
    model: str,
    db_path: Path | str | None,
    ocr: PaddleOCR,
) -> None:
    """Validate input and delegate processing to ImageProcessingService.

    Args:
        image_name: Name of the image file to process.
        input_dir: Directory containing the input image.
        output_dir: Directory for output JSON files.
        model: LLM model name or 'mock' for local heuristic.
        db_path: Optional SQLite database path.
        ocr: Initialised PaddleOCR instance.

    Exits with code 1 on validation or processing failure.
    """
    image_path = input_dir / image_name
    if not image_path.exists():
        logging.error("Error: %s not found.", image_path)
        sys.exit(1)

    # Ensure image_path is inside input_dir
    try:
        if not image_path.resolve().is_relative_to(input_dir.resolve()):
            logging.error("image-name must be inside input-dir: %s", input_dir)
            sys.exit(1)
    except AttributeError:
        # For older Python versions fallback
        if input_dir.resolve() not in image_path.resolve().parents and image_path.resolve() != input_dir.resolve():
            logging.error("image-name must be inside input-dir: %s", input_dir)
            sys.exit(1)

    try:
        service = ImageProcessingService(ocr_engine=ocr)
        service.process(image_path, output_dir, model, db_path)
    except Exception:
        logging.exception("Processing failed for %s", image_path)
        sys.exit(1)
