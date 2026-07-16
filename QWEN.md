# Project: Medical Expense Deduction Calculator

自動OCR + LLM により医療費領収書からデータを抽出し、税控除申告を支援するアプリケーション。
「Human-in-the-Loop」設計で、ユーザー修正を学習しクリニック固有のレイアウト精度を向上させる。

## Architecture & Technologies

```
Language: Python (>=3.11)
OCR:      PaddleOCR (text + coordinate extraction)
Image:    OpenCV (resize, grayscale via cv2.INTER_CUBIC)
LLM:      Structural LLM + Naming Extractor LLM (structured JSON 化)
DB:       SQLite (data/db.sqlite3)
Web:      FastAPI + uvicorn + Jinja2 + htmx
Lint:     Black (line-length 119)
```

### Dataflow

```
input image → image_resize (short side = 960px, grayscale)
            → PaddleOCR (lang="japan")
            → coord_normalizer (絶対座標→相対座標, confidence < 0.8 でスキップ)
            → process_input_json (auto via watcher/processor)
                → MockLLMClient or LLM extraction (heuristic / structured LLM)
                → (optional) template proximity search (50px, Mock only)
                    → 3段階フォールバック:
                      1. クリニック名 完全一致
                      2. テキスト類似度 (difflib, 閾値0.6)
                      3. 座標レイアウトマッチング (50px, マッチ率60%)
                → normalization (date, amount, clinic name)
            → output *-structured_data.json + SQLite persistence
            → Web UI (confirm/correct via FastAPI + htmx)
                → low_confidence レシートは一覧に警告表示、修正時テンプレート更新抑止
```

### Progress Check (サブエージェント)

実装着手前に現在の進捗を確認するには、`auto-skill-arch-progress` スキルを呼び出す:

```bash
skill("auto-skill-arch-progress")
```

このスキルは以下を自動実行する:
1. `docs/architecture/README.md` から最新スナップショットを特定
2. 最新スナップショットの全文読み取り
3. `QWEN.md` の Current Progress セクション確認
4. `git log --oneline -10` で直近のコミット状況確認
5. コンパクトな進捗サマリを出力

読み取り専用であり、いかなるファイルも変更しない。

## Key Files & Directories

| Path | Purpose |
|---|---|
| `main.py` | Entrypoint: CLI dispatch, watcher, single-image, Web server |
| `app/args.py` | Argument parsing, CUDA env setup (`CUDA_VISIBLE_DEVICES=-1` default) |
| `app/ocr_pipeline.py` | PaddleOCR text + coordinate extraction |
| `app/image_resize.py` | Image preprocessing (resize, grayscale) |
| `app/structural_parser.py` | LLM / mock structural output parsing |
| `app/normalization.py` | Text, amount, date, clinic name normalization |
| `app/llm_extractor.py` | LLM API interface for extraction |
| `app/watcher.py` | Directory watcher (watchdog observer / polling loop) |
| `app/processor.py` | Single-image processing pipeline orchestrator |
| `app/db.py` | SQLite CRUD: receipts, corrections, clinic templates |
| `app/error_logging.py` | Centralized error logging |
| `app/coord_search.py` | Coordinate search: text similarity + box proximity (50px) + hybrid layout matching (`find_clinic_by_text_similarity`, `match_template_by_layout`) |
| `app/coord_normalizer.py` | Coordinate normalization: absolute → relative, confidence gating |
| `app/template_feedback.py` | User feedback → template learning |
| `app/prompts.py` | LLM prompt templates |
| `app/services/receipt_service.py` | Service layer: business logic orchestration |
| `app/web/server.py` | FastAPI Web UI (review/correct extracted data) |
| `app/web/templates/` | Jinja2 templates for Web UI |
| `tests/` | Unit + integration + E2E test suites (12 test files) |
| `tasks/issue_N/` | Issue-specific task plans and E2E runners |
| `.gemini/agents/` | Subagent definitions (e.g., `implementation_leak_checker.md`) |
| `.qwen/skills/` | Local Qwen Code skills (e.g., `auto-skill-issue-plan`) |
| `docs/` | Architecture docs, schema definitions (`schema.sql`) |
| `pyproject.toml` | Project config, dependencies, Black config |
| `要件定義書.md` | Core requirements and functional spec (Japanese) |

## Environment / Run / Test / Lint

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
uv add --editable .
```

Dependencies are managed in `pyproject.toml` (no lockfile). Key deps:
- `paddleocr[doc-parser]>=3.6.0`, `paddlepaddle>=3.3.1`
- `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart`, `httpx2`
- `watchdog>=6.0.0`, `pytest>=9.0.3`, `black>=26.5.1`

### Run

```bash
# Directory watcher (watchdog mode — inotify)
uv run main.py --watch --use-watchdog

# Directory watcher (polling mode, every 10 s)
uv run main.py --watch

# Process a single OCR JSON → structured output
uv run main.py --input-json <path> --output-dir <dir>

# Process a single image by name from ~/Downloads/receipts/
uv run main.py --image-name IMG_20260101_xxx.jpg

# Start Web UI (review/correct extracted data)
uv run main.py --serve --db-path data/db.sqlite3

# Combine: watch + Web UI + DB persistence
uv run main.py --watch --use-watchdog --serve --db-path data/db.sqlite3
```

> **CPU-first default:** `app/args.py` sets `CUDA_VISIBLE_DEVICES="-1"` unless overridden.
> To use GPU: `CUDA_VISIBLE_DEVICES=0 uv run main.py ...`

### Test

```bash
# All tests
pytest -q

# Single test
pytest tests/test_file.py::test_name
pytest -k <expr>

# E2E test
uv run tasks/issue_4/run_e2e.py
```

### Lint

```bash
black .                          # format all
black path/to/file.py            # format single file
```

Convention: run Black before committing. Config in `pyproject.toml` (line-length 119).

## Development Conventions

- **Type Safety**: Use type hints (`from __future__ import annotations` for forward refs).
- **Code Style**: PEP 8 + Black (line-length 119).
- **Docstrings**: Google-style with `Args:` / `Returns:`.
- **Imports**: Standard lib → third-party → local; absolute imports preferred.
- **Modularity**: Clean separation between OCR, LLM, normalization, persistence, and Web layers.
- **Service Layer**: Cross-module business logic lives in `app/services/`.
- **Testing**: pytest. Prefer integration tests with real DB/fixtures over mocks.
- **Security**: No hardcoded secrets. Use env vars for configuration.
- **Implementation Leak Check (PR作成前)**: `.gemini/agents/implementation_leak_checker.md`
  サブエージェントを用いて実装漏れを検証する。チェック時は QWEN.md・`docs/` の該当設計書・`tasks/issue_N/`
  の全ファイルをコンテキストとして引き渡す。検証観点は「テキスト正規化の必要性」「空間的制約」「エッジケース処理」「例外安全
  性」「後方互換性」の5つ。チェック→修正→再チェックのサイクルですべて「問題なし」になるまでループする。手順詳細は
  `auto-skill-issue-plan` スキルのStep 10を参照。



## Current Progress

### Implemented
- OCR → LLM extraction → normalization pipeline (fully integrated)
- CLI: `--watch`, `--use-watchdog`, `--input-json`, `--image-name`, `--model`, `--serve`
- Normalization: dates, clinic names, monetary values (robust)
- Web UI: FastAPI + htmx for review/correction
- DB persistence: SQLite with receipts, corrections, clinic templates
- Service layer: `app/services/receipt_service.py`
- Coordinate correction + user feedback loop
- E2E testing framework
- **Pipeline integration**: watcher / single-image auto-generates structured data from OCR raw data
- **Coordinate proximity threshold** (50px): template-based extraction for MockLLMClient
- **Coordinate feedback dual-search**: proximity + text search merged for template learning (Bug B fix)
- **Empty old_value fallback**: coordinate search uses new_value when old_value is empty (Bug A fix)
- **Sequential correction support**: `add_correction` auto-resolves old_value conflicts (Bug C fix)
- **元号 (Reiwa) date parsing**: `令和N年M月D日`, `R{N}.M.D`, `令{N}/M/D` → ISO date
- **Split-name multi-box auto-detection**: OCR で氏名が複数テキストボックスに分割されたケース（例: "山田"+"太郎様"）を自動検出し、Forward（修正→テンプレート学習）・Reverse（テンプレート→抽出）の両方向でマルチボックス対応。`tasks/name_separated_coords/` 全14テスト通過。
  - Forward: `_find_multi_boxes_by_substring()` — ライン検出 + サブストリングマッチ + 類似度検証
  - Reverse: `search_fields_by_proximity()` — 各boxの近接検索 → X順連結 → "様"除去
  - 後方互換: 単一box (`List[List[int]]`) とマルチbox (`List[List[List[int]]]`) の自動判別
- **Coordinate normalization (relative coords)**: OCR 出力後、全 box 座標から最上部(y最小)・最左部(x最小)のオフセットを減算し相対座標に変換。同一クリニック内の撮影ズレを吸収。`app/coord_normalizer.py` 新規。
  - 最上部要素の confidence < 0.8 の場合は相対化をスキップし、`low_confidence` フラグを structured_data に設定
  - Web UI 一覧ページで `⚠ 読み取り不十分` 警告表示
  - low_confidence レシートの修正時は templates テーブル更新を抑止（corrections は通常通り反映）
- **Proximity threshold 20px → 50px**: サンプル分析に基づき、相対化後の残差(~63px)をカバーするため 50px に引き上げ
- **Hybrid template key matching (Issue #34)**: テンプレートマッチングのキーをクリニック名のみから、テキスト類似度+座標レイアウトの3段階フォールバックに拡張。OCRでクリニック名に文字欠けが発生してもテンプレートが適用される。
  - Step1: クリニック名 完全一致（`get_clinic_by_name()`、従来動作）
  - Step2: テキスト類似度マッチング（`find_clinic_by_text_similarity()`、`difflib.SequenceMatcher`、閾値0.6）
  - Step3: 座標レイアウトマッチング（`match_template_by_layout()`、各フィールド座標の50px以内にOCRエントリがあるか、マッチ率60%以上で同レイアウト判定）
  - マッチ時は `extracted["clinic"]` を正しい名前に上書きし、後続のDB操作が正しい既存クリニックを参照する
  - `app/db.py` に `get_all_clinics()`, `get_all_templates_with_names()` 追加
  - `app/coord_search.py` に `find_clinic_by_text_similarity()`, `match_template_by_layout()` 追加
  - `app/structural_parser.py` の `_apply_template_corrections()` に3段階フォールバック実装
  - `tasks/issue_34/` に計画文書 + テスト20ケース追加（全71テスト通過）

### In Progress / Upcoming
- Template correction value learning (real-world data)
- RealLLMClient integration