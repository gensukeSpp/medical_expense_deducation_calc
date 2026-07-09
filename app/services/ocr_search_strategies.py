"""Coordinate search strategies."""

import difflib
from collections import defaultdict
from typing import Any, Dict, List, Optional, Protocol


class OCRSearchStrategy(Protocol):
    """Protocol for OCR search strategies."""

    def search(
        self, ocr_entries: List[Dict[str, Any]], query: str
    ) -> Optional[List[List[int]] | List[List[List[int]]]]:
        """Search for coordinates."""
        ...


class TextSearchStrategy:
    """Search for exact or similar text matches."""

    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold

    def search(
        self, ocr_entries: List[Dict[str, Any]], query: str
    ) -> Optional[List[List[int]] | List[List[List[int]]]]:
        """Search for exact or similar text matches."""
        from app.coord_search import search_coordinates

        return search_coordinates(ocr_entries, query, self.threshold)


class MultiBoxSubstringStrategy:
    """Search for split text across multiple boxes on the same line."""

    def __init__(self, line_tolerance: float = 20.0, similarity_threshold: float = 0.7):
        self.line_tolerance = line_tolerance
        self.similarity_threshold = similarity_threshold

    def search(
        self, ocr_entries: List[Dict[str, Any]], query: str
    ) -> Optional[List[List[int]] | List[List[List[int]]]]:
        """Search for split text across multiple boxes on the same line."""
        return self._find_multi_boxes_by_substring(ocr_entries, query, self.line_tolerance, self.similarity_threshold)

    def _find_multi_boxes_by_substring(
        self,
        ocr_entries: List[Dict[str, Any]],
        full_query: str,
        line_tolerance: float,
        similarity_threshold: float,
    ) -> Optional[List[List[List[int]]]]:
        if not ocr_entries or not full_query:
            return None

        # Step 1: Group OCR entries by Y-center into lines
        lines: Dict[float, List[Dict[str, Any]]] = defaultdict(list)
        for entry in ocr_entries:
            box = entry.get("box")
            if not box or len(box) < 4:
                continue
            cy = (box[0][1] + box[2][1]) / 2.0
            assigned = False
            for key in sorted(lines.keys()):
                if abs(cy - key) <= line_tolerance:
                    lines[key].append(entry)
                    assigned = True
                    break
            if not assigned:
                lines[cy].append(entry)

        # Step 2: Find the best line with substring matches
        best_candidates: List[Dict[str, Any]] = []
        best_similarity: float = 0.0

        for line_entries in lines.values():
            candidates = []
            for entry in line_entries:
                text = entry.get("text", "")
                if not text:
                    continue
                clean_text = text.replace("様", "").strip()
                if full_query in clean_text or clean_text in full_query:
                    candidates.append(entry)

            if not candidates:
                continue

            # Sort by X coordinate (left to right)
            candidates.sort(key=lambda e: e["box"][0][0] if e.get("box") else 0)

            # Concatenate texts
            concat_text = "".join(c.get("text", "").replace("様", "").strip() for c in candidates)

            similarity = difflib.SequenceMatcher(None, concat_text, full_query).ratio()
            if similarity > best_similarity and similarity >= similarity_threshold:
                best_similarity = similarity
                best_candidates = candidates

        if not best_candidates:
            return None

        # Step 3: Build multi-box list
        return [c["box"] for c in best_candidates]
