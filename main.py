# def main():
#     print("Hello from medical-exp-deducation-calc!")
import os
import cv2
import json
from pathlib import Path
from paddleocr import PaddleOCR

from image_resize import resize_image_for_ocr


def main():
    # GPUを使用せずCPUで実行するための設定
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

    # OCRエンジンの初期化
    # lang='japan' を指定
    ocr = PaddleOCR(use_angle_cls=True, lang="japan", enable_mkldnn=False)

    # ホームディレクトリを取得して、Downloads/receipts/ を指定
    # Path.home() は、Windows なら C:\Users\ユーザー名、macOS/Linux なら /home/ユーザー名 を返します
    base_dir = Path.home() / "Downloads" / "receipts"
    # パスが存在するか確認（なければ作成する場合）
    if not base_dir.exists():
        base_dir.mkdir(parents=True, exist_ok=True)
        print(f"ディレクトリを作成しました: {base_dir}")

    image_name = "IMG_20260611_143221.jpg"
    # 画像ファイルへのパスを結合する例
    image_path = base_dir / image_name
    if not os.path.exists(image_path):
        print(f"エラー: {image_path} が見つかりません。")
        return

    output_path = base_dir / f"resized_gray_{image_name}"

    resize_image_for_ocr(image_path, output_path)
    output_img = cv2.imread(str(output_path))

    # 構造化データの作成
    structured_data = []

    try:
        # 推論実行
        # PaddleOCRのpredictは結果をリストとして返すため、[0]で最初のページを取得
        results = ocr.predict(output_img)

        if results and results[0] is not None:
            result = results[0]

        if isinstance(result, dict):
            rec_texts = result.get("rec_texts", [])
            rec_polys = result.get("rec_polys", [])
            rec_probs = result.get("rec_probs") or result.get("rec_scores") or []

            for i, text in enumerate(rec_texts):
                box = rec_polys[i] if i < len(rec_polys) else []
                confidence = float(rec_probs[i]) if i < len(rec_probs) else None

                structured_data.append(
                    {
                        "text": text,
                        "confidence": confidence,
                        "box": [[int(p[0]), int(p[1])] for p in box],
                    }
                )
        else:
            for line in result:
                box = line[0]
                text_info = line[1]
                confidence = None
                if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                    confidence = float(text_info[1])

                structured_data.append(
                    {
                        "text": text_info[0] if text_info else "",
                        "confidence": confidence,
                        "box": [[int(p[0]), int(p[1])] for p in box],
                    }
                )
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return

    # JSONとして保存
    with open("result.json", "w", encoding="utf-8") as f:
        json.dump(structured_data, f, ensure_ascii=False, indent=2)

    print(f"抽出完了: {len(structured_data)} 件のテキストを result.json に保存しました。")


if __name__ == "__main__":
    main()
