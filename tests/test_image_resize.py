import pytest
import cv2
import numpy as np
from pathlib import Path
from app.image_resize import resize_image_for_ocr

def test_resize_nonexistent(monkeypatch, tmp_path):
    """
    Template test: ensure resize_image_for_ocr handles unreadable input images gracefully.
    This test monkeypatches cv2.imread to return None so the function returns None.
    """
    input_path = tmp_path / "nope.jpg"
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # monkeypatch cv2.imread to simulate unreadable image
    import app.image_resize as image_resize
    monkeypatch.setattr(image_resize.cv2, "imread", lambda p: None)

    result = resize_image_for_ocr(input_path, output_dir)
    assert result is None

