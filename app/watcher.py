"""Folder scanner / watcher for OCR batch processing.

Usage (simple):
python app/watcher.py --input-dir ~/Downloads/receipts --output-dir output_json --processed-dir processed --poll-interval 10

Notes:
- Uses polling by default (no extra deps). If watchdog is installed it will not be required, polling is adequate.
- Requires PaddleOCR; ensure environment set up via `uv add` as requested.

Refactored structure (SRP):
- FileRepository: file system operations (stability check, image detection, failed copy, cleanup)
- ReceiptProcessor: business logic (OCR -> normalization -> structural parsing)
- PollingMonitor: polling-based file monitoring (future use)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterable

from paddleocr import PaddleOCR

from .services.file_repository import FileRepository
from .services.receipt_processor import ReceiptProcessor

LOG = logging.getLogger("ocr_watcher")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def is_image_file(p: Path) -> bool:
    #  _resized や temp などの文字列を含むファイル名を明示的に無視する
    if "_resized" in p.name or "temp" in p.name:
        return False
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
    model: str = "mock",
    db_path: Path | str | None = None,
) -> bool:
    """Process a single image. Returns True on success, False on failure.

    Legacy wrapper that delegates to ReceiptProcessor.
    """
    file_repo = FileRepository(
        output_dir=output_dir,
        processed_dir=processed_dir,
        failed_dir=failed_dir,
    )
    processor = ReceiptProcessor(
        ocr=ocr,
        file_repository=file_repo,
        output_dir=output_dir,
        model=model,
        db_path=db_path,
        retries=retries,
    )
    return processor._sync_process(image_path)


def scan_and_process(
    input_dir: Path,
    ocr,
    output_dir: Path,
    processed_dir: Path,
    failed_dir: Path,
    max_files: int | None = None,
    retries: int = 1,
    model: str = "mock",
    db_path: Path | str | None = None,
) -> int:
    """Scan input_dir and process found images. Returns number of processed files."""
    input_dir.mkdir(parents=True, exist_ok=True)
    processed = 0
    candidates = scan_images(input_dir)

    for p in candidates:
        if max_files is not None and processed >= max_files:
            break
        try:
            success = process_one(
                p,
                ocr,
                output_dir,
                processed_dir,
                failed_dir,
                retries=retries,
                model=model,
                db_path=db_path,
            )
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
    model: str = "mock",
    db_path: Path | str | None = None,
):
    LOG.info("Starting watcher: input=%s output=%s processed=%s", input_dir, output_dir, processed_dir)

    ocr = PaddleOCR(use_angle_cls=True, lang="japan", enable_mkldnn=False)

    while True:
        try:
            n = scan_and_process(
                input_dir,
                ocr,
                output_dir,
                processed_dir,
                failed_dir,
                retries=retries,
                model=model,
                db_path=db_path,
            )
            if n > 0:
                LOG.info("Processed %d files this cycle", n)
            else:
                LOG.debug("No files to process")
        except Exception:
            LOG.exception("Watcher encountered an unexpected error")

        if run_once:
            break
        time.sleep(poll_interval)


def run_watchdog(
    input_dir: Path,
    output_dir: Path,
    processed_dir: Path,
    failed_dir: Path,
    poll_interval: int = 10,
    retries: int = 1,
    model: str = "mock",
    db_path: Path | str | None = None,
):
    """Run an inotify-style watcher using watchdog. Falls back to polling if watchdog isn't available."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    except Exception as e:
        LOG.warning("watchdog not available, falling back to polling: %s", e)
        # fallback to polling loop
        run_loop(
            input_dir,
            output_dir,
            processed_dir,
            failed_dir,
            poll_interval=poll_interval,
            run_once=False,
            retries=retries,
            model=model,
            db_path=db_path,
        )
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
                            process_one(
                                p,
                                ocr,
                                output_dir,
                                processed_dir,
                                failed_dir,
                                retries=retries,
                                model=model,
                                db_path=db_path,
                            )

                        t = threading.Thread(target=_delayed, daemon=True)
                        t.start()
            except Exception:
                LOG.exception("Error handling created event %s", getattr(event, "src_path", event))

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
    """Parse command-line arguments. For compatibility with tests."""
    from app.args import setup_args

    # 使用 main.py で定義された引数体系
    args = setup_args(list(argv) if argv is not None else None)
    return args


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from app.args import setup_args, setup_directories

    args = setup_args()
    input_dir, output_dir, processed_dir, failed_dir = setup_directories(args)

    if args.use_watchdog:
        try:
            run_watchdog(
                input_dir,
                output_dir,
                processed_dir,
                failed_dir,
                poll_interval=args.poll_interval,
                retries=args.retries,
                model=args.model,
                db_path=args.db_path,
            )
        except Exception:
            LOG.exception("Watchdog failed, falling back to polling loop")
            run_loop(
                input_dir,
                output_dir,
                processed_dir,
                failed_dir,
                poll_interval=args.poll_interval,
                run_once=args.run_once,
                retries=args.retries,
                model=args.model,
                db_path=args.db_path,
            )
    else:
        run_loop(
            input_dir,
            output_dir,
            processed_dir,
            failed_dir,
            poll_interval=args.poll_interval,
            run_once=args.run_once,
            retries=args.retries,
            model=args.model,
            db_path=args.db_path,
        )
