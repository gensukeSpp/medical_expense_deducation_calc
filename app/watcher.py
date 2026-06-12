"""Folder scanner / watcher for OCR batch processing.

Usage (simple):
python app/watcher.py --input-dir ~/Downloads/receipts --output-dir output_json --processed-dir processed --poll-interval 10

Notes:
- Uses polling by default (no extra deps). If watchdog is installed it will not be required, polling is adequate.
- Requires PaddleOCR; ensure environment set up via `uv add` as requested.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

from paddleocr import PaddleOCR
from medical_exp_deducation_calc.app.ocr_pipeline import process_image


LOG = logging.getLogger("ocr_watcher")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def is_image_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in IMAGE_EXT


def is_file_stable(p: Path, interval: float = 0.5, checks: int = 3) -> bool:
    """Return True if file size remains unchanged across consecutive checks.

    The function samples file size, then performs `checks` sleeps of `interval` seconds,
    ensuring the size stays identical across all checks. Returns False on any error.
    """
    try:
        prev = p.stat().st_size
    except Exception:
        return False
    for _ in range(checks):
        time.sleep(interval)
        try:
            curr = p.stat().st_size
        except Exception:
            return False
        if curr != prev:
            return False
        prev = curr
    return True


def scan_images(input_dir: Path) -> list[Path]:
    """Return sorted list of candidate image files in input_dir (non-recursive)."""
    return sorted([p for p in input_dir.iterdir() if is_image_file(p)])


def process_one(
    image_path: Path,
    ocr,
    output_dir: Path,
    processed_dir: Path,
    failed_dir: Path,
    retries: int = 1,
) -> bool:
    """Process a single image. Returns True on success, False on failure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    # deterministic output name based on file mtime to enable idempotency
    try:
        mtime = int(image_path.stat().st_mtime)
    except Exception:
        mtime = int(time.time())
    out_fname = f"{image_path.stem}_{mtime}-raw_data.json"
    output_json_path = output_dir / out_fname

    # if output already exists, treat as already processed and move original to processed_dir
    if output_json_path.exists():
        LOG.info("Output already exists for %s -> %s, moving to processed", image_path, output_json_path)
        try:
            dest = processed_dir / image_path.name
            # avoid overwriting existing file in processed_dir
            if dest.exists():
                dest = processed_dir / f"{int(time.time())}_{image_path.name}"
            shutil.move(str(image_path), str(dest))
            LOG.info("Moved %s -> %s", image_path, dest)
            return True
        except Exception:
            LOG.exception("Failed moving already-processed file %s", image_path)
            return False

    # skip files that are still being written
    if not is_file_stable(image_path):
        LOG.info("File appears unstable (still being written), skipping for now: %s", image_path)
        return False

    attempt = 0
    while attempt <= retries:
        try:
            LOG.info("Processing %s (attempt %d)", image_path, attempt + 1)
            structured = process_image(image_path, output_json_path=output_json_path, ocr=ocr)
            LOG.info("Processed %s -> %s (%d items)", image_path, output_json_path, len(structured))

            # Move original file to processed_dir
            dest = processed_dir / image_path.name
            # avoid overwriting existing file in processed_dir
            if dest.exists():
                dest = processed_dir / f"{int(time.time())}_{image_path.name}"
            shutil.move(str(image_path), str(dest))
            LOG.info("Moved %s -> %s", image_path, dest)
            return True
        except Exception as e:
            LOG.exception("Failed processing %s: %s", image_path, e)
            attempt += 1
            time.sleep(1)

    # All attempts failed; move to failed_dir
    try:
        dest = failed_dir / image_path.name
        if dest.exists():
            dest = failed_dir / f"{int(time.time())}_{image_path.name}"
        shutil.move(str(image_path), str(dest))
        LOG.info("Moved failed %s -> %s", image_path, dest)
    except Exception:
        LOG.exception("Failed to move failed file %s", image_path)
    return False


def scan_and_process(
    input_dir: Path,
    ocr,
    output_dir: Path,
    processed_dir: Path,
    failed_dir: Path,
    max_files: int | None = None,
    retries: int = 1,
) -> int:
    """Scan input_dir and process found images. Returns number of processed files."""
    input_dir.mkdir(parents=True, exist_ok=True)
    processed = 0
    candidates = scan_images(input_dir)

    for p in candidates:
        if max_files is not None and processed >= max_files:
            break
        try:
            success = process_one(p, ocr, output_dir, processed_dir, failed_dir, retries=retries)
            if success:
                processed += 1
        except Exception:
            LOG.exception("Unexpected error while handling %s", p)
    return processed


def run_loop(
    input_dir: Path,
    output_dir: Path,
    processed_dir: Path,
    failed_dir: Path,
    poll_interval: int = 10,
    run_once: bool = False,
    retries: int = 1,
):
    LOG.info("Starting watcher: input=%s output=%s processed=%s", input_dir, output_dir, processed_dir)

    ocr = PaddleOCR(use_angle_cls=True, lang="japan", enable_mkldnn=False)

    while True:
        try:
            n = scan_and_process(input_dir, ocr, output_dir, processed_dir, failed_dir, retries=retries)
            if n > 0:
                LOG.info("Processed %d files this cycle", n)
            else:
                LOG.debug("No files to process")
        except Exception:
            LOG.exception("Watcher encountered an unexpected error")

        if run_once:
            break
        time.sleep(poll_interval)


def run_watchdog(input_dir: Path, output_dir: Path, processed_dir: Path, failed_dir: Path, poll_interval: int = 10, retries: int = 1):
    """Run an inotify-style watcher using watchdog. Falls back to polling if watchdog isn't available."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    except Exception as e:
        LOG.warning("watchdog not available, falling back to polling: %s", e)
        # fallback to polling loop
        run_loop(input_dir, output_dir, processed_dir, failed_dir, poll_interval=poll_interval, run_once=False, retries=retries)
        return

    ocr = PaddleOCR(use_angle_cls=True, lang="japan", enable_mkldnn=False)

    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            try:
                if isinstance(event, FileCreatedEvent):
                    p = Path(event.src_path)
                    if is_image_file(p):
                        LOG.info("Detected new file via watchdog: %s", p)
                        # process in background after ensuring file is stable
                        import threading

                        def _delayed():
                            # wait until stable or timeout
                            if not is_file_stable(p, interval=0.5, checks=4):
                                LOG.info("New file not stable after wait, skipping for now: %s", p)
                                return
                            process_one(p, ocr, output_dir, processed_dir, failed_dir, retries=retries)

                        t = threading.Thread(target=_delayed, daemon=True)
                        t.start()
            except Exception:
                LOG.exception("Error handling created event %s", getattr(event, 'src_path', event))

    observer = Observer()
    handler = Handler()
    observer.schedule(handler, str(input_dir), recursive=False)
    observer.start()
    LOG.info("Watchdog observer started on %s", input_dir)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        LOG.info("Stopping watchdog observer")
        observer.stop()
    observer.join()


def parse_args(argv: Iterable[str] | None = None):
    p = argparse.ArgumentParser(description="OCR folder watcher / batch processor")
    p.add_argument("--input-dir", default=str(Path.home() / "Downloads" / "receipts"))
    p.add_argument("--output-dir", default="output_json")
    p.add_argument("--processed-dir", default="processed")
    p.add_argument("--failed-dir", default="failed")
    p.add_argument("--poll-interval", type=int, default=10, help="Seconds between scans when in watch mode")
    p.add_argument("--run-once", action="store_true", help="Scan once and exit")
    p.add_argument("--retries", type=int, default=1, help="Number of retry attempts per file on failure")
    p.add_argument("--use-watchdog", action="store_true", help="Use watchdog observer instead of polling (requires watchdog package)")
    return p.parse_args(list(argv) if argv is not None else None)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    processed_dir = Path(args.processed_dir)
    failed_dir = Path(args.failed_dir)

    if args.use_watchdog:
        try:
            run_watchdog(input_dir, output_dir, processed_dir, failed_dir, poll_interval=args.poll_interval, retries=args.retries)
        except Exception:
            LOG.exception("Watchdog failed, falling back to polling loop")
            run_loop(input_dir, output_dir, processed_dir, failed_dir, poll_interval=args.poll_interval, run_once=args.run_once, retries=args.retries)
    else:
        run_loop(
            input_dir,
            output_dir,
            processed_dir,
            failed_dir,
            poll_interval=args.poll_interval,
            run_once=args.run_once,
            retries=args.retries,
        )
