"""Coordinate search: find the best matching OCR text entry for a query string."""

from __future__ import annotations

import difflib
import math
from typing import Any, Dict, List, Optional, Tuple
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


def _calculate_box_center(box: List[List[int]]) -> Optional[Tuple[float, float]]:
    """Calculate the center point (cx, cy) of a 4-point box.

    Args:
        box: Four-point coordinates [[x1,y1],[x2,y2],[x3,y3],[x4,y4]].

    Returns:
        Tuple of (cx, cy) or None if the box is invalid.
    """
    if not box or len(box) < 4:
        return None
    try:
        cx = (box[0][0] + box[2][0]) / 2.0
        cy = (box[0][1] + box[2][1]) / 2.0
        return (cx, cy)
    except (IndexError, TypeError):
        return None


def _euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate Euclidean distance between two points.

    Args:
        p1: First point (x, y).
        p2: Second point (x, y).

    Returns:
        Euclidean distance as float.
    """
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def search_by_proximity(
    ocr_entries: List[Dict[str, Any]],
    target_box: List[List[int]],
    threshold: float = 20.0,
) -> Optional[Dict[str, Any]]:
    """Find the OCR entry whose box center is within proximity of target_box center.

    Searches OCR entries by spatial proximity to the target box center.
    Returns the entry with the closest center point within the threshold.

    Args:
        ocr_entries: List of OCR result dicts with keys 'text', 'confidence', 'box'.
                     box format: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        target_box: The target box coordinates to search near.
        threshold: Maximum pixel distance from target box center to accept a match.
                   Default 20.0.

    Returns:
        The closest OCR entry dict whose center is within threshold,
        or None if no match is found.
    """
    if not ocr_entries or not target_box:
        return None

    target_center = _calculate_box_center(target_box)
    if target_center is None:
        return None

    best_entry: Optional[Dict[str, Any]] = None
    best_distance: float = float("inf")

    for entry in ocr_entries:
        entry_box = entry.get("box")
        if not entry_box:
            continue
        entry_center = _calculate_box_center(entry_box)
        if entry_center is None:
            continue

        distance = _euclidean_distance(target_center, entry_center)
        if distance < best_distance:
            best_distance = distance
            best_entry = entry

    if best_entry is not None and best_distance <= threshold:
        return best_entry

    return None


def search_by_proximity_multi(
    ocr_entries: List[Dict[str, Any]],
    field_box_map: Dict[str, List[List[int]]],
    threshold: float = 20.0,
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Search coordinates for multiple fields by proximity at once.

    Args:
        ocr_entries: List of OCR result dicts.
        field_box_map: Mapping of field names to target box coordinates.
        threshold: Maximum pixel distance for each search.

    Returns:
        Dict mapping field names to their matched OCR entry or None.
    """
    result: Dict[str, Optional[Dict[str, Any]]] = {}
    for field_name, target_box in field_box_map.items():
        result[field_name] = search_by_proximity(ocr_entries, target_box, threshold)
    return result
