"""OCR pipeline utilities.

Provides process_image() to resize image, run PaddleOCR predict, normalize results,
and optionally write structured JSON output.
"""

from pathlib import Path
import cv2
from typing import List, Optional

from .image_resize import resize_image_for_ocr


def _normalize_results(results) -> List[dict]:
    structured_data = []
    if not results or results[0] is None:
        return structured_data

    result = results[0]

    if isinstance(result, dict):
        rec_texts = result.get("rec_texts", [])
        rec_polys = result.get("rec_polys", [])
        rec_probs = result.get("rec_probs") or result.get("rec_scores") or []

        for i, text in enumerate(rec_texts):
            box = rec_polys[i] if i < len(rec_polys) else []
            confidence = float(rec_probs[i]) if i < len(rec_probs) else None

            structured_data.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "box": [[int(p[0]), int(p[1])] for p in box],
                }
            )
    else:
        for line in result:
            box = line[0]
            text_info = line[1]
            confidence = None
            if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                confidence = float(text_info[1])

            structured_data.append(
                {
                    "text": text_info[0] if text_info else "",
                    "confidence": confidence,
                    "box": [[int(p[0]), int(p[1])] for p in box],
                }
            )

    return structured_data


def process_image(
    image_path: Path | str,
    output_dir: Path | str,
    output_json_path: Optional[Path | str] = None,
    ocr=None,
) -> List[dict]:
    """Process a single image: resize, OCR, normalize, and optionally write JSON.

    Args:
        image_path: input image path
        output_dir: directory to store resized image
        output_json_path: if provided, write structured JSON to this path
        ocr: optional PaddleOCR instance. If None, caller should supply one.

    Returns:
        List of dicts with keys: text, confidence, box
    """
    image_path = Path(image_path)
    output_dir = Path(output_dir)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # produce resized image in output_dir
    resized_path = resize_image_for_ocr(image_path, output_dir)
    if resized_path is None:
        return []

    img = cv2.imread(str(resized_path))

    if ocr is None:
        raise ValueError("An initialized PaddleOCR instance must be provided as `ocr`")

    results = ocr.predict(img)
    structured = _normalize_results(results)

    if output_json_path:
        from .output import write_json_atomic

        output_json_path = Path(output_json_path)
        write_json_atomic(output_json_path, structured)

    return structured
