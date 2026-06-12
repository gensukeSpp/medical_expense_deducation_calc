# High-level Architecture (snapshot 2026-06-12)

Date: 2026-06-12

Purpose
- Snapshot of the current OCR pipeline architecture and operational decisions. Keep this file brief; create a new dated file for each meaningful change.

Overview
- Purpose: Extract structured text and coordinate data from medical receipts for downstream manual labeling and later template-based automation.
- Primary runtime: CPU-first PaddleOCR-based pipeline with optional inotify (watchdog) watcher.

Core components
- main.py
  - Thin CLI entrypoint. Supports single-file processing and watching modes.
  - Flags: --image-name, --input-dir, --output-dir, --watch, --use-watchdog, --processed-dir, --failed-dir, --poll-interval, --retries.

- app/image_resize.py
  - Resizes images so the short side == 960 px (default), converts to grayscale, writes resized image (prefix: resized_gray_).

- app/ocr_pipeline.py
  - process_image(image_path, output_json_path, ocr): runs resize_image_for_ocr, calls PaddleOCR.predict, normalizes outputs to list of {text, confidence, box}, and delegates JSON writing to app/output.write_json_atomic.

- app/output.py
  - write_json_atomic(path, data): atomic JSON write using a temp file + os.replace + fsync with retry semantics.

- app/watcher.py
  - scan_and_process: polling-based batch scanner that lists images, checks file stability, and calls process_one.
  - process_one: deterministic output naming (see below), stability check, retry loop, moves originals to processed/ or failed/; avoids overwriting by suffixing collisions with timestamps.
  - run_watchdog: optional inotify-style observer (watchdog). On file creation, waits for file stability in a background thread before processing.

Dataflow
- Input image -> app/image_resize.py -> PaddleOCR -> app/ocr_pipeline._normalize_results -> app/output.write_json_atomic -> output_json/{stem}_{mtime}-raw_data.json
- After successful processing the original image is moved to processed_dir; failed attempts are moved to failed_dir.

Key design decisions (current)
- Deterministic output filename: {image_stem}_{mtime}-raw_data.json. This enables idempotency and quick detection of already-processed images.
- File-stability check: is_file_stable ensures files still being written are skipped and retried later.
- Atomic JSON writes via tmp file + os.replace + fsync reduce corruption risk.
- Watcher: supports both polling and watchdog observer; watchdog is optional and code falls back to polling if not available.
- Dependency management: project uses uv for adding runtime/test deps (uv add ...) — prefer uv over ad-hoc pip in docs and onboarding.

Operational notes
- Recommended Python: 3.11 (pyproject.toml). Use pyenv or venv.
- Tests: pytest-based integration tests exist for watcher scan behavior and file-stability logic (tests/test_watcher_integration.py).
- Temporary resized images are currently written next to source (prefixed). Consider moving them to a temp dir or deleting after processing in future change.

Next steps / improvements
- Move resized images to a temp location and delete after successful processing.
- Add CI (GitHub Actions) to run pytest on push/PR.
- Design SQLite schema for clinic templates and implement template cache + LLM-based clinic name extraction.

Change log
- 2026-06-12: Initial snapshot — added watcher, deterministic naming, stability checks, atomic writes, tests, docs.
