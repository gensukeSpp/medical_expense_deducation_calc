import cv2
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def resize_image_for_ocr(input_path: Path, output_dir: Path, target_short_side=960) -> Path | None:
    """
    画像をOCRに適したサイズにリサイズし、出力ディレクトリに保存する関数
    :param input_path: 元画像のPathオブジェクト
    :param output_dir: 出力ディレクトリのPathオブジェクト
    :param target_short_side: 短辺の目標サイズ(px)
    :return: 保存された画像のPathオブジェクト、または読み込み失敗時にNone
    """
    # 画像の読み込み
    img = cv2.imread(str(input_path))
    if img is None:
        logger.error(f"画像を読み込めませんでした: {input_path}")
        return None

    h, w = img.shape[:2]

    # 短辺が target_short_side になるように倍率を計算
    scale = target_short_side / min(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)

    # リサイズ実行 (補間には文字が綺麗に残る INTER_CUBIC を使用)
    resized_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    # グレースケール化
    resized_img = cv2.cvtColor(resized_img, cv2.COLOR_BGR2GRAY)

    # 保存先パスの生成
    output_path = output_dir / f"resized_gray_{input_path.name}"
    
    # 保存
    cv2.imwrite(str(output_path), resized_img)
    print(f"リサイズ完了: {output_path.name} ({w}x{h} -> {new_w}x{new_h})")
    return output_path
