# Architecture Snapshot: 2026-10-02 (PR #37 / Issue #36)

## Purpose
Document the implementation of OCR preprocessing and retry logic to improve extraction quality for low-confidence receipts (Issue #36).

## Overview
- **OCR Preprocessing Pipeline**: Introduced image preprocessing utilities (CLAHE local contrast enhancement and adaptive thresholding) to reduce low-confidence OCR outputs caused by photography shadows or uneven lighting.
- **Configurable Preprocessing Modes & Resize**: Added CLI arguments (`--preprocess-mode`, `--preprocess-force`, `--target-short-size`) to control preprocessing behavior and target image sizing.
- **Preprocessed Raw Data Preservation**: Retains original `*raw_data.json` files while saving preprocessed OCR outputs as `*raw_data.preprocessed.json` (and preprocessed images in `processed/` or output directory) for visual inspection and traceability.

## Key Components Changed
- `app/image_preprocessing.py` (New): Implements CLAHE (`apply_clahe`), adaptive thresholding (`apply_adaptive_threshold`), and preprocessing function factory (`build_preprocess_fn`).
- `app/coord_normalizer.py`: Added `get_topmost_confidence` for read-only confidence checking without modifying box coordinates.
- `app/ocr_pipeline.py`: Extended `process_image` to support optional `preprocess_fn`, `preprocess_output_path`, and `target_short_side`.
- `app/services/image_processing_service.py` & `app/services/receipt_processor.py`: Implemented 1-retry flow with image preprocessing when low confidence is detected (or when forced via `--preprocess-force`).
- `app/args.py`, `main.py`, `app/watcher.py`: Exposed new CLI options (`--preprocess-mode`, `--preprocess-force`, `--target-short-size`) through CLI, watcher, and service layers.

## Key Design Decisions
- **Non-destructive Raw Preservation**: Original raw OCR JSON is preserved; preprocessed attempts produce distinct `-raw_data.preprocessed.json` files.
- **Conditional Retry**: Automatically triggers preprocessing and re-OCR once if topmost element confidence is below 0.8 (or when `--preprocess-force` is specified).
- **Target Short Side Control**: Configurable target short-side sizing (default 960px) for flexible scaling during image resizing.

## Changed Files
- `app/args.py`
- `app/coord_normalizer.py`
- `app/image_preprocessing.py`
- `app/ocr_pipeline.py`
- `app/processor.py`
- `app/services/image_processing_service.py`
- `app/services/receipt_processor.py`
- `app/watcher.py`
- `main.py`
- `tests/test_coord_normalizer.py`
- `tests/test_image_preprocessing.py`
- `tests/test_image_processing_service.py`
- `tests/test_ocr_pipeline.py`

## Commits (origin/main..HEAD)
- b4fc009 fix #260929: ocr_pipeline 前処理時の 3ch/グレー取扱を修正
- 6d8ffc2 feat #260929: --preprocess-force で Confidence に関係なく前処理を強制適用可能に
- 5a87f04 feat #260929: watcher パスに前処理再試行を伝播
- d6eb945 feat #260929: CLI → サービスの前処理引数を伝播
- adcb98a feat #260929: --preprocess-mode / --target-short-side を追加
- 515750b feat #260929: 低Confidence時に前処理再試行を追加 (CLI パス)
- 351c2ff feat #260929: process_image に前処理・保存先・target_short_side を追加
- a7750b4 feat #260929: topmost Confidence の読み取り専用判定を追加
- 6143b2d feat #260929: 前処理 module (CLAHE, adaptiveThreshold) を追加
