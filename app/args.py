import argparse
import logging
import os
from pathlib import Path


def setup_args():
    """引数を解析し、初期化処理を行う"""
    # Setup logging
    logging.basicConfig(level=logging.INFO)

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

    return args


def setup_directories(args):
    """出力ディレクトリを作成する"""
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {input_dir}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    processed_dir = Path(args.processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir = Path(args.failed_dir)
    failed_dir.mkdir(parents=True, exist_ok=True)

    return input_dir, output_dir, processed_dir, failed_dir
