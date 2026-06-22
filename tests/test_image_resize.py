import pytest
from pathlib import Path

from app.image_resize import resize_image_for_ocr


def test_resize_nonexistent(monkeypatch, tmp_path, capsys):
    """
    Template test: ensure resize_image_for_ocr handles unreadable input images gracefully.
    This test monkeypatches cv2.imread to return None so the function prints an error and returns None.
    """
    input_path = tmp_path / "nope.jpg"
    output_path = tmp_path / "out.jpg"

    # monkeypatch cv2.imread to simulate unreadable image
    import app.image_resize as image_resize

    monkeypatch.setattr(image_resize.cv2, "imread", lambda p: None)

    result = resize_image_for_ocr(input_path, output_path)

    # function prints an error and returns None
    captured = capsys.readouterr()
    assert "エラー: 画像を読み込めませんでした" in captured.out
    assert result is None
