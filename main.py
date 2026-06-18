# def main():
#     print("Hello from medical-exp-deducation-calc!")
import os
import cv2
import json
from pathlib import Path
from paddleocr import PaddleOCR


def main():
    import argparse
    from datetime import datetime

    # CPU実行をデフォルトにする
    os.environ["CUDA_VISIBLE_DEVICES"] = os.environ.get("CUDA_VISIBLE_DEVICES", "-1")

    parser = argparse.ArgumentParser(description="Medical expense OCR runner")
    parser.add_argument("--input-dir", default=str(Path.home() / "Downloads" / "receipts"))
    parser.add_argument("--image-name", default=None, help="Process a single image by name")
    parser.add_argument("--output-dir", default="output_json", help="JSON output directory")
    parser.add_argument(
        "--watch", action="store_true", help="Run folder watcher instead of single-file processing"
    )
    parser.add_argument(
        "--use-watchdog",
        action="store_true",
        help="When watching, use watchdog observer (inotify) if available",
    )
    parser.add_argument("--processed-dir", default="processed", help="Directory to move processed images to")
    parser.add_argument("--failed-dir", default="failed", help="Directory to move failed images to")
    parser.add_argument("--poll-interval", type=int, default=10, help="Polling interval for watcher (seconds)")
    parser.add_argument("--retries", type=int, default=1, help="Retry attempts per file on failure")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {input_dir}")

    # OCRエンジン初期化
    ocr = PaddleOCR(use_angle_cls=True, lang="japan", enable_mkldnn=False)

    from app.ocr_pipeline import process_image
    from app import watcher

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    processed_dir = Path(args.processed_dir)
    failed_dir = Path(args.failed_dir)

    if args.watch:
        # Start watcher (either watchdog observer or polling loop)
        if args.use_watchdog:
            print("Starting watcher (watchdog mode)...")
            watcher.run_watchdog(
                input_dir,
                output_dir,
                processed_dir,
                failed_dir,
                poll_interval=args.poll_interval,
                retries=args.retries,
            )
        else:
            print("Starting watcher (polling mode)...")
            watcher.run_loop(
                input_dir,
                output_dir,
                processed_dir,
                failed_dir,
                poll_interval=args.poll_interval,
                run_once=False,
                retries=args.retries,
            )
        return

    if args.image_name:
        image_path = input_dir / args.image_name
        if not image_path.exists():
            print(f"Error: {image_path} not found.")
            return

        out_fname = f"{datetime.now():%Y%m%d}_{image_path.stem}-raw_data.json"
        output_json_path = output_dir / out_fname

        try:
            structured = process_image(image_path, output_json_path=output_json_path, ocr=ocr)
            print(f"Saved {len(structured)} items to {output_json_path}")
        except Exception as e:
            print(f"Processing failed: {e}")
            return
    else:
        print(
            "No --image-name provided. Pass an image name to process a single file, or use --watch to run the folder watcher."
        )


if __name__ == "__main__":
    main()
