"""Tests for app/coord_search.py — coordinate search via similarity matching."""

from __future__ import annotations

import pytest
from app.coord_search import (
    search_coordinates,
    search_coordinates_multi,
    search_by_proximity,
    search_by_proximity_multi,
    search_fields_by_proximity,
    _is_multi_box,
    _calculate_box_center,
    _euclidean_distance,
)

MULTI_BOX_NAME = [
    [[67, 126], [205, 130], [203, 198], [65, 194]],
    [[255, 126], [379, 135], [374, 209], [250, 200]],
]

OCR_ENTRIES_SPLIT_NAME = [
    {"text": "山田", "confidence": 0.99, "box": [[67, 126], [205, 130], [203, 198], [65, 194]]},
    {"text": "太郎様", "confidence": 0.91, "box": [[255, 126], [379, 135], [374, 209], [250, 200]]},
]


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


class TestBoxCenter:
    """Test _calculate_box_center helper."""

    def test_valid_box(self):
        """4点座標から正しい中心が計算される"""
        box = [[0, 0], [10, 0], [10, 10], [0, 10]]
        center = _calculate_box_center(box)
        assert center == (5.0, 5.0)

    def test_edge_case_box(self):
        """座標がすべて同じ場合"""
        box = [[5, 5], [5, 5], [5, 5], [5, 5]]
        center = _calculate_box_center(box)
        assert center == (5.0, 5.0)

    def test_empty_box(self):
        """空の box は None"""
        assert _calculate_box_center([]) is None

    def test_invalid_box(self):
        """不完全な box は None"""
        assert _calculate_box_center([[1, 2]]) is None


class TestEuclideanDistance:
    """Test _euclidean_distance helper."""

    def test_same_point(self):
        """同一地点からの距離は 0"""
        assert _euclidean_distance((5.0, 5.0), (5.0, 5.0)) == 0.0

    def test_vertical_distance(self):
        """垂直方向の距離"""
        assert _euclidean_distance((0.0, 0.0), (0.0, 10.0)) == 10.0

    def test_horizontal_distance(self):
        """水平方向の距離"""
        assert _euclidean_distance((0.0, 0.0), (10.0, 0.0)) == 10.0

    def test_diagonal_distance(self):
        """対角線方向の距離"""
        assert abs(_euclidean_distance((0.0, 0.0), (3.0, 4.0)) - 5.0) < 1e-10


class TestSearchByProximity:
    """Test search_by_proximity single field search."""

    @pytest.fixture
    def sample_entries(self):
        """OCR エントリのサンプル（座標近接テスト用）"""
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
        ]

    def test_exact_match(self, sample_entries):
        """同一座標で正しくマッチする"""
        target = [[50, 100], [200, 100], [200, 140], [50, 140]]
        result = search_by_proximity(sample_entries, target)
        assert result is not None
        assert result["text"] == "山田 太郎"

    def test_within_threshold(self, sample_entries):
        """しきい値内のズレでマッチする"""
        # ターゲットを「あおばクリニック」(center: 175, 180) から 10px ずらす
        target = [[55, 165], [305, 165], [305, 205], [55, 205]]  # center: (180, 185), 距離 ~7.07px
        result = search_by_proximity(sample_entries, target, threshold=20.0)
        assert result is not None
        assert result["text"] == "あおばクリニック"

    def test_beyond_threshold(self, sample_entries):
        """しきい値超過で None を返す"""
        # 領収書下端から遠く離れた座標
        target = [[0, 500], [100, 500], [100, 550], [0, 550]]
        result = search_by_proximity(sample_entries, target, threshold=20.0)
        assert result is None

    def test_empty_entries(self):
        """空エントリで None"""
        result = search_by_proximity([], [[0, 0], [10, 0], [10, 10], [0, 10]])
        assert result is None

    def test_empty_target(self, sample_entries):
        """空の target_box で None"""
        result = search_by_proximity(sample_entries, [])
        assert result is None

    def test_nearest_match(self):
        """複数候補から最小距離のエントリが選択される"""
        entries = [
            {"text": "遠い", "box": [[0, 0], [10, 0], [10, 10], [0, 10]]},  # center: (5, 5), 距離: ~247.5
            {"text": "近い", "box": [[200, 200], [300, 200], [300, 240], [200, 240]]},  # center: (250, 220)
        ]
        # target = あおばクリニックの中心付近 (175, 180)
        target = [[50, 160], [300, 160], [300, 200], [50, 200]]  # center: (175, 180)
        result = search_by_proximity(entries, target, threshold=100.0)
        assert result is not None
        assert result["text"] == "近い"


class TestSearchByProximityMulti:
    """Test search_by_proximity_multi multiple field search."""

    @pytest.fixture
    def sample_entries(self):
        """OCR エントリのサンプル"""
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
        ]

    def test_multi_search(self, sample_entries):
        """複数フィールドの座標を一括検索できる"""
        field_box_map = {
            "name": [[50, 100], [200, 100], [200, 140], [50, 140]],
            "clinic": [[50, 160], [300, 160], [300, 200], [50, 200]],
        }
        results = search_by_proximity_multi(sample_entries, field_box_map)
        assert results["name"] is not None
        assert results["name"]["text"] == "山田 太郎"
        assert results["clinic"] is not None
        assert results["clinic"]["text"] == "あおばクリニック"

    def test_multi_search_partial(self, sample_entries):
        """一部フィールドがしきい値超過の場合、該当フィールドのみ None"""
        field_box_map = {
            "name": [[50, 100], [200, 100], [200, 140], [50, 140]],
            "far_field": [[0, 500], [100, 500], [100, 550], [0, 550]],
        }
        results = search_by_proximity_multi(sample_entries, field_box_map, threshold=20.0)
        assert results["name"] is not None
        assert results["far_field"] is None


class TestIsMultiBox:
    """Tests for _is_multi_box helper."""

    def test_is_multi_box_true(self):
        """マルチbox形式 → True"""
        assert _is_multi_box(MULTI_BOX_NAME) is True

    def test_is_multi_box_false_single(self):
        """単一box形式 → False"""
        single_box = [[50, 100], [200, 100], [200, 140], [50, 140]]
        assert _is_multi_box(single_box) is False

    def test_is_multi_box_false_invalid(self):
        """不正データ → False"""
        assert _is_multi_box([]) is False
        assert _is_multi_box(None) is False
        assert _is_multi_box("not a list") is False
        assert _is_multi_box([1, 2, 3]) is False


class TestSearchFieldsByProximity:
    """Tests for search_fields_by_proximity."""

    @pytest.fixture
    def sample_entries(self):
        """OCR エントリのサンプル（近接検索テスト用）"""
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
        ]

    def test_search_fields_by_proximity_single(self, sample_entries):
        """単一box → 単一テキスト返却"""
        field_map = {
            "name": [[50, 100], [200, 100], [200, 140], [50, 140]],
        }
        results = search_fields_by_proximity(sample_entries, field_map)
        assert results["name"] == "山田 太郎"

    def test_search_fields_by_proximity_multi(self):
        """マルチbox → 連結テキスト返却"""
        field_map = {"name": MULTI_BOX_NAME}
        results = search_fields_by_proximity(OCR_ENTRIES_SPLIT_NAME, field_map)
        assert results["name"] == "山田太郎"  # "様" 除去後

    def test_search_fields_by_proximity_multi_with_sama(self):
        """マルチboxで「様」サフィックス除去"""
        entries = [
            {"text": "佐藤", "confidence": 0.99, "box": [[50, 100], [150, 100], [150, 150], [50, 150]]},
            {"text": "花子様", "confidence": 0.92, "box": [[200, 100], [320, 100], [320, 150], [200, 150]]},
        ]
        multi_box = [
            [[50, 100], [150, 100], [150, 150], [50, 150]],
            [[200, 100], [320, 100], [320, 150], [200, 150]],
        ]
        results = search_fields_by_proximity(entries, {"name": multi_box})
        assert results["name"] == "佐藤花子"

    def test_search_fields_by_proximity_threshold(self, sample_entries):
        """閾値超過 → None"""
        far_box = [[0, 500], [100, 500], [100, 550], [0, 550]]
        results = search_fields_by_proximity(sample_entries, {"far": far_box}, threshold=20.0)
        assert results["far"] is None
