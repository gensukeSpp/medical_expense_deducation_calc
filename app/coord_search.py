"""Coordinate search: find the best matching OCR text entry for a query string."""

from __future__ import annotations

import difflib
from typing import Any, List, Optional
from app.normalization import normalize_text


def search_coordinates(
    ocr_entries: List[dict[str, Any]],
    query: str,
    threshold: float = 0.7,
) -> Optional[List[List[int]]]:
    """Search OCR entries for the text that best matches the query using similarity ratio.

    Args:
        ocr_entries: List of OCR result dicts with keys 'text', 'confidence', 'box'.
                     box format: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        query: The text string to search for (usually old_value from a correction).
        threshold: Minimum similarity ratio (0.0-1.0) to accept a match.
                   Default 0.7.

    Returns:
        The box coordinates of the best matching entry, or None if no match
        meets the threshold.
    """
    if not query or not ocr_entries:
        return None

    normalized_query = normalize_text(query)
    if not normalized_query:
        return None

    best_ratio: float = 0.0
    best_box: Optional[List[List[int]]] = None

    for entry in ocr_entries:
        text = entry.get("text", "")
        if not text:
            continue

        # ratio = difflib.SequenceMatcher(None, query, text).ratio()
        # if ratio > best_ratio:
        #     best_ratio = ratio
        #     best_box = entry.get("box")

        normalized_text = normalize_text(text)
        if not normalized_text:
            continue

        ratio = difflib.SequenceMatcher(None, normalized_query, normalized_text).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_box = entry.get("box")

    if best_ratio >= threshold and best_box is not None:
        return best_box

    return None


def search_coordinates_multi(
    ocr_entries: List[dict[str, Any]],
    field_map: dict[str, str],
    threshold: float = 0.7,
) -> dict[str, Optional[List[List[int]]]]:
    """Search coordinates for multiple fields at once.

    Args:
        ocr_entries: List of OCR result dicts.
        field_map: Mapping of field names to query strings (e.g. {'amount': '3800'}).
        threshold: Minimum similarity ratio for each search.

    Returns:
        Dict mapping field names to their box coordinates or None if not found.
    """
    result: dict[str, Optional[List[List[int]]]] = {}
    for field_name, query in field_map.items():
        result[field_name] = search_coordinates(ocr_entries, query, threshold)
    return result
