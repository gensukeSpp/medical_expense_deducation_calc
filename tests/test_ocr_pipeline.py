"""Tests for app/ocr_pipeline.py process_image preprocess extension (Issue #36)."""

from __future__ import annotations

import cv2
import numpy as np

from app.ocr_pipeline import process_image


class TestProcessImagePreprocess:
    def test_writes_preprocessed_image_and_passes_to_ocr(self, tmp_path):
        # 元画像作成（カラー）
        src = tmp_path / "img.jpg"
        cv2.imwrite(str(src), np.full((100, 80, 3), 150, dtype=np.uint8))

        # resize 内部で cv2 実処理を行いたいため、resize を本来どおり使う
        # （process_image は resized_gray_* を生成後、preprocess_fn へ渡す）
        from unittest.mock import Mock

        ocr = Mock()
        ocr.predict.return_value = [
            [
                ([[0, 0], [10, 0], [10, 5], [0, 5]], ("top", 0.9)),
            ]
        ]

        preprocessed_out = tmp_path / "processed" / "preprocessed_img.jpg"
        preprocessed_out.parent.mkdir(parents=True, exist_ok=True)

        def fake_preprocess(img):
            return np.where(img > 128, 255, 0).astype(np.uint8)

        structured = process_image(
            src,
            output_dir=tmp_path,
            output_json_path=tmp_path / "raw.json",
            ocr=ocr,
            preprocess_fn=fake_preprocess,
            preprocess_output_path=preprocessed_out,
        )

        assert structured and structured[0]["text"] == "top"
        assert preprocessed_out.exists()
        # predict に渡された画像は前処理済みであるべき
        passed_img = ocr.predict.call_args[0][0]
        assert set(np.unique(passed_img)).issubset({0, 255})
