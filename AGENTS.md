# medical-exp-deducation-calc

医療費控除用領収書 OCR アプリ。確定申告のためのデータ入力簡略化が目的。
Phase 1（読み込み、抽出、修正、キャッシュ）のみを実装。計算（Phase 2）は未着手。

---

## ディレクトリ構成

```
.
├── main.py                    # CLI エントリポイント (argparse)
├── pyproject.toml             # uv + 依存定義 (black)
├── uv.lock
│
├── app/                       # 本体コード
│   ├── args.py                # CLI 引数定義・ディレクトリ初期化
│   ├── db.py                  # SQLite ヘルパー (全テーブル CRUD)
│   ├── db_migrations.py       # スキーママイグレーション
│   ├── schema.sql             # 最終的な SQL スキーマ (source of truth)
│   ├── coord_normalizer.py    # 座標正規化 (offset 除去)
│   ├── coord_search.py        # 座標ベースのフィールド検索
│   ├── image_resize.py        # OCR 向け画像リサイズ
│   ├── input.py               # JSON 読み込みヘルパー
│   ├── llm_extractor.py       # LLM クライアント抽象 + Mock 実装
│   ├── normalization.py       # 金額/日付の正規化
│   ├── ocr_pipeline.py        # PaddleOCR エンジン (resize -> predict -> normalize)
│   ├── output.py              # Atomic JSON 書き出し
│   ├── processor.py           # 単一画像処理 (CLI layer)
│   ├── prompts.py             # LLM プロンプト定義
│   ├── structural_parser.py   # 構造化パーサー (ExtractionService, ReceiptProcessingService)
│   ├── template_feedback.py   # クリニックテンプレート学習 (フィードバックループ)
│   ├── watcher.py             # フォルダ監視 (polling / watchdog)
│   ├── error_logging.py       # エラーログ出力
│   │
│   ├── services/              # 分離されたサービス層 (SRP)
│   │   ├── image_processing_service.py  # 画像処理オーケストレーター
│   │   ├── receipt_processor.py          # ビジネスロジック (OCR -> 解析)
│   │   ├── file_repository.py            # ファイルシステム操作
│   │   │
│   │   ├── receipt_service.py            # Web UI 用receipt操作用オーケストレーター
│   │   ├── receipt_file_repository.py    # receipt ファイル I/O
│   │   ├── receipt_database_repository.py # receipt DB操作
│   │   ├── receipt_normalizer.py         # receipt データ正規化
│   │   ├── ocr_coordinate_service.py     # 座標検索・フィードバック
│   │   ├── receipt_updater.py            # receipt 更新オーケストレーター
│   │
│   └── web/                   # Web UI (FastAPI + Jinja2)
│       ├── server.py          # FastAPI アプリ作成
│       └── templates/         # HTML テンプレート
│
├── docs/
│   ├── DEVELOPMENT.md         # 開発環境セットアップ
│   ├── schema.sql             # DB スキーマ
│   └── architecture/          #  dated architecture snapshots
│
├── tests/                     # pytest テスト
│   ├── conftest.py
│   ├── test_*.py
│
├── output_json/               # 処理済み JSON 出力先 (gitignore)
├── processed/                 # 処理済み画像 (gitignore)
├── failed/                    # 失敗画像 (gitignore)
├── data/                      # SQLite データベース (gitignore)
└── logs/                      # ログ (gitignore)
```

## 技術スタック

- **言語**: Python >= 3.11
- **管理**: uv (`uv run python main.py ...`)
- **OCR**: PaddleOCR (`paddleocr[doc-parser]`, lang=japan)
- **LLM**: 構造化 LLM (JSON 整形) + 命名抽出 LLM (クリニック名特定)
  - 現在は `--model=mock` でヒューリスティック実装のみ
- **Web**: FastAPI + uvicorn + Jinja2
- **DB**: SQLite (FK 有効化必須: `PRAGMA foreign_keys = ON`)
- **監視**: watchdog (inotify) / polling fallback
- **テスト**: pytest
- **整形**: black (line-length=119)

## DB スキーマ

source of truth: `docs/schema.sql`

| テーブル          | 役割                           |
| ----------------- | ------------------------------ |
| `users`           | ユーザー                       |
| `clinics`         | クリニックマスタ (name UNIQUE) |
| `receipts`        | 領収書レコード                 |
| `templates`       | クリニック別座標テンプレート   |
| `template_history`| テンプレート変更履歴           |
| `corrections`     | ユーザー修正履歴               |

マイグレーション:
```bash
python -m app.db_migrations init --db-path data/db.sqlite3
```

## 主要アーキテクチャパターン

### 1. 「座標逆引き」モデル (requirements 5 参照)

領収書解析の根幹となるロジック:

```
画像投入 -> OCR(テキスト+座標) -> クリニック名特定 ->
DBから過去テンプレート取得 -> 座標補正値適用 ->
ラベル・値リスト化 -> UI提示 -> ユーザー修正 ->
修正値をDBに学習(座標オフセット更新)
```

### 2. Hybrid Template Key Matching (3-stage fallback)

`app/structural_parser.py` の `ExtractionService._apply_template_corrections()`:

1. **Exact Name Match** - クリニック名で完全一致
2. **Text Similarity** - `difflib` (閾値 0.6)
3. **Layout-based Matching** - 50px 近接 + 60% フィールド一致

### 3. 2 つの processing パス

**パス A: 画像 -> 構造データ (CLI / Watcher)**
```
main.py -> processor.py -> ImageProcessingService
  -> ocr_pipeline.process_image()
  -> coord_normalizer.normalize_coordinates()
  -> structural_parser.process_input_json()
    -> ExtractionService.extract()
    -> DataNormalizationService.normalize()
    -> ReceiptRepository.save()
    -> OutputWriter.write()
```

**パス B: JSON -> 構造データ (既存 OCR JSON 処理)**
```
main.py -> structural_parser.process_input_json()
  -> 同上 ExtractionService / Normalizer / Repository / Writer
```

### 4. Service Layer (SRP)

`app/services/` は Single Responsibility Principle に基づく分離:

- `ReceiptService` - Web UI 操作用オーケストレーター
- `ReceiptUpdater` - 更新フローの調整役
- `ReceiptFileRepository` / `ReceiptDatabaseRepository` - 分離されたリポジトリ
- `ReceiptNormalizer` - データ正規化
- `OCRCoordinateService` - 座標検索・フィードバック

## CLI 使い方

```bash
# 単一画像処理
uv run python main.py --input-dir ~/Downloads/receipts --image-name IMG_001.jpg

# 既存 OCR JSON から構造データ生成
uv run python main.py --input-json output_json/IMG-raw_data.json --db-path data/db.sqlite3

# フォルダ監視 (polling)
uv run python main.py --watch --input-dir ~/Downloads/receipts --poll-interval 10

# フォルダ監視 (watchdog inotify)
uv run python main.py --watch --use-watchdog --input-dir ~/Downloads/receipts

# Web UI 起動
uv run python main.py --serve --port 8000 --db-path data/db.sqlite3
```

引数一覧:

| 引数              | 説明                                        | デフォルト                  |
| ----------------- | ------------------------------------------- | --------------------------- |
| `--input-dir`     | 入力画像ディレクトリ                        | `~/Downloads/receipts`      |
| `--image-name`    | 単一画像処理 (ファイル名)                   | None                        |
| `--output-dir`    | JSON 出力先                                 | `output_json`               |
| `--input-json`    | 既存 OCR JSON 処理                          | None                        |
| `--model`         | LLM モデル名 or `mock`                      | `mock`                      |
| `--watch`         | フォルダ監視モード                          | False                       |
| `--use-watchdog`  | watchdog(inotify) 使用                      | False                       |
| `--processed-dir` | 処理済み画像先                              | `processed`                 |
| `--failed-dir`    | 失敗画像先                                  | `failed`                    |
| `--poll-interval` | ポーリング間隔 (秒)                         | 10                          |
| `--run-once`      | 1回スキャンして終了                         | False                       |
| `--retries`       | 失敗時のリトライ回数                        | 1                           |
| `--db-path`       | SQLite パス                                 | None                        |
| `--serve`         | Web UI サーバー起動                         | False                       |
| `--host`          | Web サーバーホスト                          | `127.0.0.1`                 |
| `--port`          | Web サーバーポート                          | 8000                        |

## 開発規約

### コーディング規約

- `black` で整形: `black .` (pyproject.toml 設定に従う)
- 型注釈を付ける (Python 3.11 型ヒント: `X | Y` 構法)
- docstring は Google style (クラス/メソッド毎)
- 各モジュールに SRP を明示する docstring を付ける
- `from __future__ import annotations` をモジュール冒頭に付ける

### モジュール設計ルール

1. **CLI layer (`processor.py`, `args.py`)** - 引数検証、sys.exit、エラー表示のみ。ビジネスロジックを含まない
2. **Service layer (`services/`)** - 各クラスが単一責任を持つ。オーケストレーターはコンポーネントを調整するのみ
3. **Repository pattern** - データアクセスはリポジトリに閉じ込める
4. **Dependency Injection** - サービス間の結合はプロトコル/インターフェース経由

### テスト

```bash
# 全テスト
pytest

# 単一ファイル
pytest tests/test_db.py -v

# フィクスチャ利用 (conftest.py 参照)
pytest tests/test_feedback.py -v
```

テストファイルは `test_*.py` として `tests/` 配下に配置。
`pytest` 実行時は `PYTHONPATH=.` を有効化 (pyproject.toml で自動設定される場合あり)。

### ブランチ命名規則

```
feature/<issue-number>-<short-description>
fix/<issue-number>-<short-description>
docs/<issue-number>-<short-description>
refactor/<issue-number>-<short-description>
```

例: `feature/34-hybrid-template`, `fix/260716-layout-matching`

コミットメッセージ:
```
feat #<issue>: <description>
fix #<issue>: <description>
docs #<issue>: <description>
refactor #<issue>: <description>
```

### git workflow

- `main` が安定ブランチ
- 開発は `hermes-setting` など feature ブランチから PR 経由で merge
- 直接 main への push は避ける

## 重要な設計判断

### PaddleOCR は CPU デフォルト

`app/args.py` の `setup_args()` で `CUDA_VISIBLE_DEVICES=-1` を強制。
GPU なし環境でも動作する前提。

### Low Confidence Flag

座標正規化で最上部文字の confidence が 0.8 未満の場合:
- 正規化をスキップし `low_confidence: True` フラグを structured JSON に付与
- このフラグがある場合、テンプレート学習をスキップ (`receipt_updater.py` 行 98-108)

### 出力ファイル命名

- raw JSON: `{image_stem}_{mtime}-raw_data.json`
- structured JSON: `{image_stem}_{mtime}-structured_data.json`

### ファイル安定性チェック

`watcher.py` / `file_repository.py` の `is_file_stable()`:
- ファイルサイズを 0.5秒間隔で 3 回チェック
- サイズが変動中なら処理をスキップ
- 書き込み完了を確実に判定

## 関連ファイル

- 要件定義書: `要件定義書.md`
- 開発環境: `docs/DEVELOPMENT.md`
- スキーマ: `docs/schema.sql`
- アーキテクチャスナップショット: `docs/architecture/` 配下
