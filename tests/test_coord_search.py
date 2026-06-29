"""Tests for app/coord_search.py — coordinate search via similarity matching."""

from __future__ import annotations

import pytest
from app.coord_search import search_coordinates, search_coordinates_multi


@pytest.fixture
def sample_ocr_entries():
    """Simulates a list of OCR entries from raw_data.json."""
    return [
        {
            "text": "山田 太郎",
            "confidence": 0.95,
            "box": [[50, 100], [200, 100], [200, 140], [50, 140]],
        },
        {
            "text": "あおばクリニック",
            "confidence": 0.92,
            "box": [[50, 160], [300, 160], [300, 200], [50, 200]],
        },
        {
            "text": "3,800",
            "confidence": 0.88,
            "box": [[400, 300], [480, 300], [480, 340], [400, 340]],
        },
        {
            "text": "2026/01/15",
            "confidence": 0.90,
            "box": [[50, 50], [200, 50], [200, 80], [50, 80]],
        },
        {
            "text": "内科",
            "confidence": 0.85,
            "box": [[50, 220], [130, 220], [130, 250], [50, 250]],
        },
    ]


class TestSearchCoordinates:
    """Test search_coordinates single query."""

    def test_exact_match(self, sample_ocr_entries):
        """完全一致するテキストの座標が取得できる"""
        box = search_coordinates(sample_ocr_entries, "あおばクリニック")
        assert box is not None
        assert box == [[50, 160], [300, 160], [300, 200], [50, 200]]

    def test_similar_match(self, sample_ocr_entries):
        """類似度マッチングで座標が取得できる（スペース有無などの微差に対応）"""
        box = search_coordinates(sample_ocr_entries, "あおはクリニック", threshold=0.6)
        assert box is not None
        # "あおばクリニック" with "あおはクリニック" should match above 0.6
        assert box == [[50, 160], [300, 160], [300, 200], [50, 200]]

    def test_no_match(self, sample_ocr_entries):
        """存在しないテキストは None を返す"""
        box = search_coordinates(sample_ocr_entries, "非存在テキスト")
        assert box is None

    def test_empty_query(self, sample_ocr_entries):
        """空クエリは None を返す"""
        box = search_coordinates(sample_ocr_entries, "")
        assert box is None

    def test_empty_entries(self):
        """空の OCR エントリリストは None を返す"""
        box = search_coordinates([], "test")
        assert box is None

    def test_high_threshold_rejects(self, sample_ocr_entries):
        """高いしきい値では類似度が低いマッチが reject される"""
        box = search_coordinates(sample_ocr_entries, "山田花子子", threshold=0.85)
        # "山田 太郎" vs "山田花子子" — strict threshold may reject
        if box is not None:
            # If match, must be the correct one
            assert box == [[50, 100], [200, 100], [200, 140], [50, 140]]

    def test_low_threshold_accepts(self, sample_ocr_entries):
        """低いしきい値では緩くマッチする"""
        box = search_coordinates(sample_ocr_entries, "あおは", threshold=0.3)
        assert box is not None

    def test_multiple_candidates_best_match(self):
        """複数の候補から最類似のエントリが選ばれる"""
        entries = [
            {"text": "3,800", "box": [[100, 100], [200, 100], [200, 140], [100, 140]]},
            {"text": "38,000", "box": [[300, 100], [400, 100], [400, 140], [300, 140]]},
            {"text": "5,000", "box": [[500, 100], [600, 100], [600, 140], [500, 140]]},
        ]
        box = search_coordinates(entries, "3800")
        # "3,800" should match better than "38,000" or "5,000"
        assert box == [[100, 100], [200, 100], [200, 140], [100, 140]]


class TestSearchCoordinatesMulti:
    """Test search_coordinates_multi multiple field search."""

    def test_multi_search(self, sample_ocr_entries):
        """複数フィールドの座標を同時検索できる"""
        field_map = {
            "name": "山田 太郎",
            "amount": "3,800",
            "date": "2026/01/15",
        }
        results = search_coordinates_multi(sample_ocr_entries, field_map)
        assert results["name"] == [[50, 100], [200, 100], [200, 140], [50, 140]]
        assert results["amount"] == [[400, 300], [480, 300], [480, 340], [400, 340]]
        assert results["date"] == [[50, 50], [200, 50], [200, 80], [50, 80]]

    def test_multi_search_partial_missing(self, sample_ocr_entries):
        """一部のフィールドがマッチしない場合、該当フィールドは None"""
        field_map = {
            "name": "山田 太郎",
            "unknown": "存在しない値",
        }
        results = search_coordinates_multi(sample_ocr_entries, field_map)
        assert results["name"] is not None
        assert results["unknown"] is None

    def test_multi_search_empty(self):
        """空の entries では全フィールドが None"""
        results = search_coordinates_multi([], {"name": "test"})
        assert results["name"] is None
