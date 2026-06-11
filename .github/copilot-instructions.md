# Copilot instructions for medical-exp-deducation-calc

Purpose
- Short, machine-readable guidance for Copilot sessions: how to run, test, lint, and where to look for the program flow and extension points.

Build / Run / Test / Lint
- Python requirement: >= 3.11 (see pyproject.toml).
- Recommended virtualenv:
  - python -m venv .venv
  - source .venv/bin/activate
  - pip install --upgrade pip
- Install runtime dependencies (no lockfile provided):
  - pip install "paddleocr[doc-parser]>=3.6.0" "paddlepaddle>=3.3.1"
  - or (if packaging tooling is present): pip install -e .
- Run the app (simple):
  - Edit main.py to set image_name or place an image at: ~/Downloads/receipts/IMG_YYYYMMDD_xxx.jpg
  - python main.py
  - Note: main.py sets CUDA_VISIBLE_DEVICES="-1" to force CPU. To use GPU, remove or override that env var before running.
- Quick single-test run:
  - Temporarily change image_name in main.py to a known test image, then run python main.py and inspect result.json.
- Output locations:
  - result.json in the working directory (list of {text, confidence, box}).
  - resized grayscale images saved next to the input with prefix resized_gray_.
- Lint / format:
  - black .
  - black path/to/file.py
  - Black config: pyproject.toml (line-length 119).
- Tests:
  - No tests currently. When adding pytest tests, run a single test with:
    - pytest tests/test_file.py::test_name
    - or pytest -k <expr>

High-level architecture
- Purpose: a focused OCR pipeline: preprocess images, run PaddleOCR, normalize outputs, and write structured JSON for downstream labeling/storage.
- Core components:
  - main.py: entrypoint; sets CPU env, initializes PaddleOCR (lang="japan"), calls image_resize.resize_image_for_ocr, runs ocr.predict, normalizes results, and writes result.json.
  - image_resize.py: resizes so the short side == 960px (default), converts to grayscale, and writes resized image.
  - 要件定義書.md: product goals and roadmap (Phase 1 focuses on extraction and human-in-the-loop template caching).
- Dataflow summary:
  - input image -> image_resize -> PaddleOCR -> normalize to [{text, confidence, box}] -> result.json
  - main.py already handles both dict-shaped and list-shaped PaddleOCR return values; use its normalization as canonical reference.

Key repo conventions and specifics
- CPU-first default: CUDA_VISIBLE_DEVICES="-1" in main.py (override to enable GPU).
- Language: PaddleOCR initialized with lang="japan".
- Image preprocessing: cv2.INTER_CUBIC used for resizing; images converted to grayscale before OCR.
- Default I/O path: base_dir = Path.home()/"Downloads"/"receipts". Create or change before running.
- Output naming: resized_gray_{original_name} and result.json.
- Formatting: use Black (line-length 119) before commits.
- No CI or lockfile present; add requirements.txt or lockfile and tests for reproducible dev environments.
- Future integrations: 要件定義書.md documents planned SQLite template cache and LLM-based clinic/name extraction — review before implementing those features.

Files to inspect first
- main.py (entrypoint and normalization logic)
- image_resize.py (preprocessing)
- pyproject.toml (python & deps)
- 要件定義書.md (design / roadmap)

AI assistant / agent configs
- This file centralizes Copilot guidance. No other assistant config files (CLAUDE.md, .cursorrules, AGENTS.md, etc.) were detected in the repo root.

Suggested small improvements to add later
- Example wrapper script to run the tool against a specified image path (env var or CLI arg).
- Short snippet showing how to re-enable GPU (unset CUDA_VISIBLE_DEVICES) and any PaddlePaddle GPU notes.
- A pytest test template and a requirements.txt or lockfile for repeatable installs.

If any of the suggested improvements should be added to this file or committed as extra files, reply and the change will be applied.
