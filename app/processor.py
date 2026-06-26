import sys
import logging
from datetime import datetime
import argparse
from pathlib import Path

from paddleocr import PaddleOCR


def process_single_image(args: argparse.Namespace, input_dir: Path, output_dir: Path, ocr: PaddleOCR) -> None:
    """単一の画像をOCR処理し、結果をJSONファイルとして保存する。

    Args:
        args (argparse.Namespace): コマンドライン引数。
        input_dir (Path): 入力画像ディレクトリ。
        output_dir (Path): 出力JSONディレクトリ。
        ocr (PaddleOCR): 初期化済みのPaddleOCRインスタンス。
    """
    if args.image_name:
        image_path = input_dir / args.image_name
        if not image_path.exists():
            logging.error("Error: %s not found.", image_path)
            sys.exit(1)
        # Ensure image_path is inside input_dir
        try:
            if not image_path.resolve().is_relative_to(input_dir.resolve()):
                logging.error("image-name must be inside input-dir: %s", input_dir)
                sys.exit(1)
        except AttributeError:
            # For older Python versions fallback
            if input_dir.resolve() not in image_path.resolve().parents and image_path.resolve() != input_dir.resolve():
                logging.error("image-name must be inside input-dir: %s", input_dir)
                sys.exit(1)

        try:
            mtime = int(image_path.stat().st_mtime)
        except Exception:
            mtime = int(datetime.now().timestamp())
        out_fname = f"{image_path.stem}_{mtime}-raw_data.json"
        output_json_path = output_dir / out_fname

        try:
            from app.ocr_pipeline import process_image

            structured = process_image(image_path, output_json_path=output_json_path, ocr=ocr)
            if structured is None:
                logging.warning("process_image returned None for %s", image_path)
            elif isinstance(structured, dict):
                logging.info("Saved 1 item to %s", output_json_path)
            else:
                logging.info("Saved %d items to %s", len(structured), output_json_path)
        except Exception:
            logging.exception("Processing failed for %s", image_path)
            sys.exit(1)
    else:
        print(
            "No --image-name provided. Pass an image name to process a single file, or use "
            "--watch to run the folder watcher."
        )
