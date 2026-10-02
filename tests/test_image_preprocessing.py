"""Tests for app/image_preprocessing.py (Issue #36)."""

from __future__ import annotations

import numpy as np
import pytest

from app.image_preprocessing import apply_clahe, apply_adaptive_threshold, build_preprocess_fn


def _gray_img(width: int = 64, height: int = 64) -> np.ndarray:
    # 0..255 に分布するランダムグレースケール画像
    return np.random.randint(0, 256, (height, width), dtype=np.uint8)


class TestApplyClahe:
    def test_output_same_shape_and_dtype(self):
        img = _gray_img()
        out = apply_clahe(img)
        assert out.shape == img.shape
        assert out.dtype == np.uint8

    def test_increases_contrast_on_low_contrast_image(self):
        # ほぼ平らな画像（標準偏差が小さい）
        img = np.full((64, 64), 100, dtype=np.uint8)
        img[10:20, 10:20] = 120
        out = apply_clahe(img)
        assert out.std() > img.std()


class TestApplyAdaptiveThreshold:
    def test_output_is_binary(self):
        img = _gray_img()
        out = apply_adaptive_threshold(img)
        assert set(np.unique(out)).issubset({0, 255})
        assert out.shape == img.shape


class TestBuildPreprocessFn:
    def test_none_returns_none(self):
        assert build_preprocess_fn("none") is None

    def test_clahe_returns_callable(self):
        fn = build_preprocess_fn("clahe")
        assert callable(fn)
        assert fn(_gray_img()).shape == (64, 64)

    def test_adaptive_returns_callable(self):
        fn = build_preprocess_fn("adaptive")
        assert callable(fn)
        assert set(np.unique(fn(_gray_img()))).issubset({0, 255})

    def test_combined_returns_callable(self):
        fn = build_preprocess_fn("clahe+adaptive")
        assert callable(fn)
        out = fn(_gray_img())
        assert set(np.unique(out)).issubset({0, 255})

    def test_unknown_mode_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown preprocessing mode"):
            build_preprocess_fn("unknown")
