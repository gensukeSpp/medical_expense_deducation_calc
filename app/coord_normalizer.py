"""Coordinate normalizer: convert absolute OCR coordinates to relative positions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional


def _find_min_coords(ocr_entries: List[Dict[str, Any]]) -> tuple[Optional[int], Optional[int], Optional[float]]:
    """Find the minimum x, minimum y across all boxes, and the confidence of the topmost element.

    Args:
        ocr_entries: List of OCR result dicts with keys 'text', 'confidence', 'box'.

    Returns:
        Tuple of (min_x, min_y, topmost_confidence).
        min_x/min_y are None if no valid boxes found.
        topmost_confidence is None if no valid entry found.
    """
    min_x: Optional[int] = None
    min_y: Optional[int] = None
    topmost_confidence: Optional[float] = None
    topmost_y: Optional[float] = None

    for entry in ocr_entries:
        if not isinstance(entry, dict):
            continue
        box = entry.get("box")
        if not box or not isinstance(box, list):
            continue

        """
        無効な形式の座標点（リストやタプルではない、または要素数が2未満のもの）が含まれている場合、\n
        非辞書型の要素が ocr_entries に混入した場合の防御的プログラミングも考慮し、事前に有効な座標点（valid_points）を抽出して処理する
        """
        valid_points = [p for p in box if isinstance(p, (list, tuple)) and len(p) >= 2]
        if not valid_points:
            continue

        # Find this box's min x and min y across all points
        for x, y in valid_points:
            if min_x is None or x < min_x:
                min_x = x
            if min_y is None or y < min_y:
                min_y = y

        # Track topmost element's confidence
        box_min_y = min(p[1] for p in valid_points)
        if topmost_y is None or box_min_y < topmost_y:
            topmost_y = box_min_y
            topmost_confidence = entry.get("confidence")

    return min_x, min_y, topmost_confidence


def _subtract_offset(box: List[List[int]], offset_x: int, offset_y: int) -> List[List[int]]:
    """Subtract offset from all points in a box."""
    # box 内に無効な座標点（None や空リストなど）が含まれている場合、スキップ
    return [[p[0] - offset_x, p[1] - offset_y] for p in box if isinstance(p, (list, tuple)) and len(p) >= 2]


def normalize_coordinates(raw_data_path: Path) -> Dict[str, Any]:
    """Normalize OCR coordinates to relative positions.

    Finds the topmost element (min y) and leftmost element (min x),
    then subtracts these offsets from all box coordinates.

    If the topmost element's confidence < 0.8, normalization is skipped.

    Args:
        raw_data_path: Path to the raw_data.json file.

    Returns:
        Dict with keys:
            - normalized: bool — whether normalization was performed
            - low_confidence: bool — whether topmost element had confidence < 0.8
            - topmost_confidence: float or None — confidence of the topmost element
            - offset_x: int — x offset subtracted (0 if skipped)
            - offset_y: int — y offset subtracted (0 if skipped)
    """
    import json

    if not raw_data_path.exists():
        raise FileNotFoundError(f"raw_data not found: {raw_data_path}")

    with open(raw_data_path, encoding="utf-8") as f:
        ocr_entries = json.load(f)

    if not isinstance(ocr_entries, list) or not ocr_entries:
        return {
            "normalized": False,
            "low_confidence": False,
            "topmost_confidence": None,
            "offset_x": 0,
            "offset_y": 0,
        }

    min_x, min_y, topmost_confidence = _find_min_coords(ocr_entries)

    if min_x is None or min_y is None:
        return {
            "normalized": False,
            "low_confidence": False,
            "topmost_confidence": topmost_confidence,
            "offset_x": 0,
            "offset_y": 0,
        }

    # Check confidence: treat None as low confidence (safe side)
    low_confidence = topmost_confidence is None or topmost_confidence < 0.8

    if low_confidence:
        return {
            "normalized": False,
            "low_confidence": True,
            "topmost_confidence": topmost_confidence,
            "offset_x": 0,
            "offset_y": 0,
        }

    # Normalize coordinates: subtract offset from all box points
    normalized_entries = []
    for entry in ocr_entries:
        box = entry.get("box")
        if box and isinstance(box, list):
            entry["box"] = _subtract_offset(box, min_x, min_y)
        normalized_entries.append(entry)

    # Write back atomically
    from app.output import write_json_atomic

    write_json_atomic(raw_data_path, normalized_entries)

    return {
        "normalized": True,
        "low_confidence": False,
        "topmost_confidence": topmost_confidence,
        "offset_x": min_x,
        "offset_y": min_y,
    }
