"""Tests for coordinate normalizer: absolute → relative coordinate conversion."""

from __future__ import annotations

import json
from pathlib import Path
from app.coord_normalizer import normalize_coordinates, _find_min_coords, _subtract_offset


def _make_raw_data(entries: list[dict]) -> Path:
    """Helper to create a temporary raw_data.json file and return its path."""
    import tempfile

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(entries, tmp, ensure_ascii=False)
    tmp.close()
    return Path(tmp.name)


class TestFindMinCoords:
    """Tests for _find_min_coords helper."""

    def test_basic(self):
        entries = [
            {"text": "領収書", "confidence": 0.9, "box": [[152, 2], [477, 8], [476, 73], [151, 66]]},
            {"text": "山田太郎", "confidence": 0.95, "box": [[67, 126], [205, 130], [203, 198], [65, 194]]},
        ]
        min_x, min_y, topmost_conf = _find_min_coords(entries)
        assert min_x == 65  # from "山田太郎" box[3][0]
        assert min_y == 2  # from "領収書" box[0][1]
        assert topmost_conf == 0.9  # "領収書" is topmost

    def test_empty_list(self):
        min_x, min_y, topmost_conf = _find_min_coords([])
        assert min_x is None
        assert min_y is None
        assert topmost_conf is None

    def test_invalid_box_skipped(self):
        entries = [
            {"text": "A", "confidence": 0.9, "box": []},
            {"text": "B", "confidence": 0.8, "box": [[10, 10], [20, 10], [20, 20], [10, 20]]},
        ]
        min_x, min_y, topmost_conf = _find_min_coords(entries)
        assert min_x == 10
        assert min_y == 10
        assert topmost_conf == 0.8

    def test_confidence_none(self):
        entries = [
            {"text": "A", "confidence": None, "box": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        ]
        _, _, topmost_conf = _find_min_coords(entries)
        assert topmost_conf is None


class TestSubtractOffset:
    """Tests for _subtract_offset helper."""

    def test_basic(self):
        box = [[152, 2], [477, 8], [476, 73], [151, 66]]
        result = _subtract_offset(box, 65, 2)
        assert result == [[87, 0], [412, 6], [411, 71], [86, 64]]

    def test_zero_offset(self):
        box = [[10, 10], [20, 10], [20, 20], [10, 20]]
        result = _subtract_offset(box, 0, 0)
        assert result == [[10, 10], [20, 10], [20, 20], [10, 20]]


class TestNormalizeCoordinates:
    """Tests for normalize_coordinates main function."""

    def test_basic_normalization(self, tmp_path):
        """Normal confidence: coordinates should be normalized."""
        entries = [
            {"text": "領収書", "confidence": 0.9, "box": [[152, 2], [477, 8], [476, 73], [151, 66]]},
            {"text": "山田太郎", "confidence": 0.95, "box": [[67, 126], [205, 130], [203, 198], [65, 194]]},
        ]
        raw_path = tmp_path / "test-raw_data.json"
        json.dump(entries, open(raw_path, "w", encoding="utf-8"))

        result = normalize_coordinates(raw_path)

        assert result["normalized"] is True
        assert result["low_confidence"] is False
        assert result["offset_x"] == 65
        assert result["offset_y"] == 2
        assert result["topmost_confidence"] == 0.9

        # Verify file was updated
        updated = json.load(open(raw_path, encoding="utf-8"))
        # First box: [152-65, 2-2] = [87, 0], etc.
        assert updated[0]["box"] == [[87, 0], [412, 6], [411, 71], [86, 64]]
        # Second box: [67-65, 126-2] = [2, 124], etc.
        assert updated[1]["box"] == [[2, 124], [140, 128], [138, 196], [0, 192]]

    def test_low_confidence_skips(self, tmp_path):
        """Confidence < 0.8: should skip normalization."""
        entries = [
            {"text": "昂", "confidence": 0.5, "box": [[404, 3], [463, 3], [463, 28], [404, 28]]},
            {"text": "なの花薬局", "confidence": 0.9, "box": [[136, 978], [650, 985], [650, 1015], [136, 1008]]},
        ]
        raw_path = tmp_path / "test-raw_data.json"
        json.dump(entries, open(raw_path, "w", encoding="utf-8"))

        result = normalize_coordinates(raw_path)

        assert result["normalized"] is False
        assert result["low_confidence"] is True
        assert result["topmost_confidence"] == 0.5

        # File should be unchanged
        updated = json.load(open(raw_path, encoding="utf-8"))
        assert updated[0]["box"] == [[404, 3], [463, 3], [463, 28], [404, 28]]

    def test_none_confidence_skips(self, tmp_path):
        """None confidence: should treat as low confidence."""
        entries = [
            {"text": "A", "confidence": None, "box": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        ]
        raw_path = tmp_path / "test-raw_data.json"
        json.dump(entries, open(raw_path, "w", encoding="utf-8"))

        result = normalize_coordinates(raw_path)

        assert result["normalized"] is False
        assert result["low_confidence"] is True

    def test_empty_list(self, tmp_path):
        """Empty OCR entries: should return normalized=False."""
        raw_path = tmp_path / "test-raw_data.json"
        json.dump([], open(raw_path, "w", encoding="utf-8"))

        result = normalize_coordinates(raw_path)

        assert result["normalized"] is False
        assert result["low_confidence"] is False

    def test_single_entry(self, tmp_path):
        """Single entry: min_x=min_y=0, normalized but offset is 0,0."""
        entries = [
            {"text": "A", "confidence": 0.9, "box": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        ]
        raw_path = tmp_path / "test-raw_data.json"
        json.dump(entries, open(raw_path, "w", encoding="utf-8"))

        result = normalize_coordinates(raw_path)

        assert result["normalized"] is True
        assert result["offset_x"] == 0
        assert result["offset_y"] == 0

    def test_file_not_found(self):
        """Non-existent file should raise FileNotFoundError."""
        import pytest

        with pytest.raises(FileNotFoundError):
            normalize_coordinates(Path("/nonexistent/path.json"))

    def test_all_invalid_boxes(self, tmp_path):
        """All entries have invalid boxes: should return normalized=False."""
        entries = [
            {"text": "A", "confidence": 0.9, "box": []},
            {"text": "B", "confidence": 0.8, "box": None},
        ]
        raw_path = tmp_path / "test-raw_data.json"
        json.dump(entries, open(raw_path, "w", encoding="utf-8"))

        result = normalize_coordinates(raw_path)

        assert result["normalized"] is False
        assert result["low_confidence"] is False

    def test_preserves_other_fields(self, tmp_path):
        """Non-box fields in entries should be preserved after normalization."""
        entries = [
            {"text": "A", "confidence": 0.9, "box": [[10, 10], [20, 10], [20, 20], [10, 20]], "extra": "keep"},
        ]
        raw_path = tmp_path / "test-raw_data.json"
        json.dump(entries, open(raw_path, "w", encoding="utf-8"))

        normalize_coordinates(raw_path)

        updated = json.load(open(raw_path, encoding="utf-8"))
        assert updated[0]["extra"] == "keep"
        assert updated[0]["text"] == "A"
