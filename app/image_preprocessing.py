"""Image preprocessing for OCR quality improvement (Issue #36)."""

from __future__ import annotations

from typing import Callable, Optional

import cv2
import numpy as np


def apply_clahe(gray: np.ndarray, clip_limit: float = 2.0, tile_grid_size: tuple[int, int] = (8, 8)) -> np.ndarray:
    """CLAHE（局所コントラスト強調）を適用する。

    Args:
        gray: 単チャネル uint8 グレースケール画像。
        clip_limit: コントラスト制限値。
        tile_grid_size: タイル分割サイズ。

    Returns:
        強調されたグレースケール画像。
    """
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe.apply(gray)


def apply_adaptive_threshold(enhanced: np.ndarray, block_size: int = 11, c: int = 2) -> np.ndarray:
    """適応的二値化（影や輝度ムラを低減）を適用する。

    Args:
        enhanced: 単チャネル uint8 グレースケール画像（CLAHE 適用後を想定）。
        block_size: 局所領域のブロックサイズ（奇数）。
        c: しきい値から引く定数。

    Returns:
        二値化画像（0 または 255）。
    """
    return cv2.adaptiveThreshold(
        enhanced,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        c,
    )


def build_preprocess_fn(mode: str) -> Optional[Callable[[np.ndarray], np.ndarray]]:
    """前処理モードに応じた前処理関数を返す。`none` は None を返す。

    Args:
        mode: "none" | "clahe" | "adaptive" | "clahe+adaptive"。

    Returns:
        前処理関数（None の場合は前処理を適用しない）。

    Raises:
        ValueError: 未知の前処理モードが指定された場合。
    """
    if mode == "none":
        return None
    if mode == "clahe":
        return lambda img: apply_clahe(img)
    if mode == "adaptive":
        return lambda img: apply_adaptive_threshold(img)
    if mode == "clahe+adaptive":

        def combined(img: np.ndarray) -> np.ndarray:
            return apply_adaptive_threshold(apply_clahe(img))

        return combined
    raise ValueError(f"Unknown preprocessing mode: {mode}")
