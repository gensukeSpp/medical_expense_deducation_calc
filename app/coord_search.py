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


def _is_multi_box(value: Any) -> bool:
    """Check if a field value is a multi-box (list of boxes) format.

    Multi-box format: [[[x1,y1],[x2,y2],...], [[x1,y1],[x2,y2],...]]
    Single-box format: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]

    Args:
        value: The field value to check.

    Returns:
        True if value is multi-box, False otherwise.
    """
    if not isinstance(value, list) or not value:
        return False
    if not isinstance(value[0], list) or not value[0]:
        return False
    return isinstance(value[0][0], list)


def search_fields_by_proximity(
    ocr_entries: List[Dict[str, Any]],
    field_box_map: Dict[str, Any],
    threshold: float = 20.0,
) -> Dict[str, Optional[str]]:
    """Search fields by proximity, supporting both single and multi-box formats.

    Single-box fields use search_by_proximity() directly.
    Multi-box fields (e.g., split name) search each box, concatenate texts
    in X-coordinate order, and strip the "様" suffix.

    Args:
        ocr_entries: List of OCR result dicts.
        field_box_map: Mapping of field names to box(es).
            - Single box: List[List[int]] — 4-point polygon
            - Multi box: List[List[List[int]]] — list of 4-point polygons
        threshold: Maximum pixel distance for proximity matching.

    Returns:
        Dict mapping field names to concatenated text or None if not found.
    """
    result: Dict[str, Optional[str]] = {}
    for field_name, boxes in field_box_map.items():
        if boxes is None:
            result[field_name] = None
            continue

        if _is_multi_box(boxes):
            # Multi-box: search each box, concatenate texts in X order
            texts_with_x: List[tuple[str, float]] = []
            all_found = True
            for sub_box in boxes:
                match = search_by_proximity(ocr_entries, sub_box, threshold)
                if match and match.get("text"):
                    cx = _calculate_box_center(sub_box)
                    x_center = cx[0] if cx else 0.0
                    texts_with_x.append((match["text"], x_center))
                else:
                    all_found = False
                    break

            if all_found and texts_with_x:
                # Sort by X coordinate (left to right)
                texts_with_x.sort(key=lambda t: t[1])
                concat_text = "".join(t[0] for t in texts_with_x)
                # Strip "様" suffix
                concat_text = concat_text.rstrip("様")
                result[field_name] = concat_text
            else:
                result[field_name] = None
        else:
            # Single box: use existing search_by_proximity
            match = search_by_proximity(ocr_entries, boxes, threshold)
            if match and match.get("text"):
                result[field_name] = match["text"]
            else:
                result[field_name] = None

    return result


def find_clinic_by_text_similarity(
    clinic_name: str,
    clinics: list[dict[str, Any]],
    threshold: float = 0.6,
) -> Optional[dict[str, Any]]:
    """Find the best matching clinic by text similarity.

    Compares the extracted clinic name against all known clinic names
    using difflib.SequenceMatcher with normalize_text() preprocessing.

    Args:
        clinic_name: The extracted clinic name (may have OCR errors).
        clinics: List of clinic dicts with at least 'name' key.
        threshold: Minimum similarity ratio (0.0-1.0) to accept a match.
                   Default 0.6.

    Returns:
        The best matching clinic dict, or None if no match meets the threshold.
    """
    if not clinic_name or not clinics:
        return None

    norm_query = normalize_text(clinic_name)
    if not norm_query:
        return None

    best_ratio: float = 0.0
    best_clinic: Optional[dict[str, Any]] = None

    for clinic in clinics:
        name = clinic.get("name", "")
        if not name:
            continue
        norm_name = normalize_text(name)
        if not norm_name:
            continue
        ratio = difflib.SequenceMatcher(None, norm_query, norm_name).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_clinic = clinic

    if best_ratio >= threshold and best_clinic is not None:
        return best_clinic

    return None


def match_template_by_layout(
    ocr_entries: list[dict[str, Any]],
    templates: list[dict[str, Any]],
    proximity_threshold: float = 50.0,
    match_ratio: float = 0.6,
) -> Optional[dict[str, Any]]:
    """Find a template whose field coordinates best match the OCR layout.

    For each template, checks what percentage of its coords_corrections
    fields have nearby OCR entries within the proximity threshold.

    Args:
        ocr_entries: List of OCR entry dicts with 'text', 'confidence', 'box'.
        templates: List of template dicts with 'coords_corrections'.
        proximity_threshold: Max pixel distance for proximity matching.
                             Default 50.0 (DEFAULT_PROXIMITY_THRESHOLD).
        match_ratio: Minimum ratio of matched fields (0.0-1.0) to accept.
                     Default 0.6.

    Returns:
        The best matching template dict, or None if no match meets the ratio.
    """
    if not ocr_entries or not templates:
        return None

    best_template: Optional[dict[str, Any]] = None
    best_rate: float = 0.0

    for template in templates:
        coords = template.get("coords_corrections")
        if not coords:
            continue

        fields = list(coords.keys())
        if not fields:
            continue

        matched_count = 0
        for field_name in fields:
            field_box = coords[field_name]
            if field_box is None:
                continue
            match = search_by_proximity(ocr_entries, field_box, proximity_threshold)
            if match:
                matched_count += 1

        rate = matched_count / len(fields)
        if rate > best_rate:
            best_rate = rate
            best_template = template

    if best_rate >= match_ratio and best_template is not None:
        return best_template

    return None
