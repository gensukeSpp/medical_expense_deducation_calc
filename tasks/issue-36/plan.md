# Issue #36 実装計画 — 抽出前の出力向上のための前処理

> 対象ブランチ: `feature/improve-ocr-quality/36`
> 実装タスク詳細: [tasks.md](./tasks.md)

## Goal

リサイズ → グレースケール → OCR の過程に、**低 Confidence（起点 text の Confidence < 0.8）のときのみ再試行可能な前処理** を追加し、出力 JSON の質を向上させる。加えて、前処理後の画像を `processed/` に保存して目視検証できるようにする。

## Architecture（方針）

現在のパイプラインは以下の通り（`docs/architecture/README.md` および各モジュール docstring に基づく）。

```
画像投入 -> リサイズ+グレースケール(resized_gray_*) -> OCR predict
        -> raw_data.json 出力 -> 座標正規化(normalize_coordinates)
        -> 構造化パース(process_input_json) -> structured_data.json
        -> (低Confidence時) low_confidence flag 付与 / テンプレート学習スキップ
```

`coord_normalizer.normalize_coordinates()` は最上部要素の Confidence を判定し、
**0.8 未満なら正規化をスキップして `low_confidence: True`** を返す（既存実装・そのまま活用する）。

今回の変更はこの「低 Confidence 時の分岐」を拡張し、**再出力（1回）** を行う。

```
入力画像
  -> リサイズ + グレースケール            (image_resize)
  -> OCR predict -> raw_data.json        (1回目 / 前処理なし)
  -> Confidence 判定 (topmost < 0.8 ?)   (coord_normalizer)
       └─ YES の場合のみ:
            CLAHE + 適応的二値化 -> 前処理済み画像を processed/ に保存
            -> 前処理済み画像で OCR 再実行 (2回目)
               -> raw_data.preprocessed.json を**別名で保存**（原本 raw_data.json は温存）
            -> 前処理済み raw で座標正規化・構造化パースを再実行
  -> 構造化パース -> structured_data.json
  -> (それでも低Confidenceなら) low_confidence flag 付与
```

### 採用する対策の判断（Issue の取捨選択項目）

| # | 対策                         | 採用判断 | 備考 |
|---|------------------------------|----------|------|
| 1 | リサイズ倍率の見直し (960→1200) | **一部採用** | `--target-short-side` を CLI オプション化し、ユーザーが手動調整可能にする。デフォルトは現状維持(960)推奨（Issue のユーザー希望「1 は手動調整可能に」に準拠） |
| 2 | CLAHE（局所コントラスト強調） | **採用**   | 低Confidence時のみ。目視検証の対象 |
| 3 | 適応的二値化 (Adaptive Threshold) | **採用** | 低Confidence時のみ。CLAHE の後に連結（レシートでも比較的安定する Gaussian + BINARY を採用） |
| 4 | サーバー用モデルへの切り替え   | **見送り** | 大規模変更・別 Issue 相当。Issue のユーザー希望「2,3試して効果薄なら→1→その後4」に沿って、まず 2,3 を実装し効果を検証する |

**実装対象スコープ**: 対策 2（CLAHE）+ 対策 3（適応的二値化）を低 Confidence 時の再試行として実装。
対策 1（`--target-short-side`）を CLI オプションとして追加。対策 4（モデル切替）は本 Issue では見送る。

### 主要設計判断

1. **前処理は「低 Confidence 時のみ」の再試行**。常時適用はしない（既存の出力順序・テンプレート学習を壊さない）。
2. **前処理関数は新モジュール `app/image_preprocessing.py` に分離**（SRP）。image_resize は「リサイズ+グレースケール」のみの責務を維持。
3. **再試行は `ocr_pipeline.process_image()` に前処理用パラメータを追加して実現**。CLI 層 (`processor.py`) にロジックを置かず、サービス層 (`ImageProcessingService`) と watcher (`ReceiptProcessor`) が調整役になる。
4. **前処理済み画像は `processed/` に保存**（`preprocessed_{ファイル名}`）。検証のため消さない。
5. **再試行は1回のみ。** 前処理なしの `raw_data.json` は温存し、再試行結果は `{stem}_{mtime}-raw_data.preprocessed.json` に**別名で保存**して両データを比較可能にする。それでも低 Confidence なら従来どおり `low_confidence: True` flag を付与し、テンプレート学習を見送る。後段の座標正規化・構造化パースは「前処理済み raw」を対象に実行する。

## Requirements（要件の要点・Issue 36 より）

- `output_json/*-raw.json` の起点点 text の Confidence が 0.8 を下回る場合（`templates` への反映が見送られる対象画像）にのみ適用する。
- 一度出力した後、起点点の Confidence を検索し、条件に合えば前処理を加えて **再出力を1回** 試みる。
- 目視確認のため、リサイズ・グレースケール・前処理適用後の画像を **`processed/` に保存する**。
- 必ずしも 0.8 を超えることを期待するものではない（効果検証が主目的。別対策は次 Issue で）。

## Tech Stack / 依存

- Python >= 3.11, OpenCV (`cv2` — 既に `app/image_resize.py`, `app/ocr_pipeline.py` で使用済み、追加依存なし)
- `numpy`（前処理の型・テストで使用。`cv2` が暗黙依存、既存テストでも `import numpy` 済み）
- black (line-length=119) / pytest

## Files 変更対象

| ファイル | 変更種別 | 内容 |
|----------|----------|------|
| `app/image_preprocessing.py` | **新規** | `apply_clahe()`, `apply_adaptive_threshold()`, `build_preprocess_fn()` |
| `app/ocr_pipeline.py` | 修正 | `process_image()` に `preprocess_fn` / `preprocess_output_path` / `target_short_side` を追加 |
| `app/services/image_processing_service.py` | 修正 | `process()` に低Confidence時の前処理再試行フロー。原本 `raw_data.json` は温存し、前処理済みは `raw_data.preprocessed.json` に別名保存 |
| `app/coord_normalizer.py` | 修正 | 読み取り専用で topmost Confidence を返す `get_topmost_confidence()` を追加 |
| `app/services/receipt_processor.py` | 修正 | watcher パスにも同等の前処理再試行を追加 |
| `app/watcher.py` | 修正 | `process_one` / `scan_and_process` / `run_loop` / `run_watchdog` に新引数を伝播 |
| `app/args.py` | 修正 | `--preprocess-mode` / `--target-short-side` を追加 |
| `main.py`, `app/processor.py` | 修正 | CLI → サービスへの新引数伝播 |
| `tests/test_image_preprocessing.py` | **新規** | 前処理関数の単体テスト |
| `tests/test_image_processing_service.py` | 修正 | 前処理再試行フローの結合テスト追加 |
| `tests/test_coord_normalizer.py` | 修正 | `get_topmost_confidence()` のテスト追加 |
| `tests/test_image_resize.py` | 修正 | `target_short_side` 動作確認追加（既存パターン流用） |

## Implementation Steps（概要 — 詳細は tasks.md）

1. **前処理モジュール新設** — CLAHE / 適応的二値化 / 組み合わせビルダー。純関数・入力は単チャネル uint8 グレースケール。
2. **coord_normalizer に読み取り専用判定を追加** — `get_topmost_confidence(raw_path) -> (low_confidence, topmost_confidence)`。
3. **ocr_pipeline.process_image 拡張** — `preprocess_fn`（グレースケール後に適用）、`preprocess_output_path`（処理後画像の保存先）、`target_short_side` を渡せるようにする。
4. **ImageProcessingService に前処理再試行を追加** — 1回目OCR → Confidence判定 → 低なら前処理再試行1回 → 再正規化 → パース → flag。
5. **watcher パス（ReceiptProcessor / watcher.py）にも同等実装**。
6. **CLI オプション追加と伝播** — `--preprocess-mode` / `--target-short-side`。main→processor→service。
7. **テスト追加・修正**（TDD: 各タスク冒頭で失敗テスト→実装→成功確認）。
8. **black 整形 + 全テスト実行 + 目視検証**（サンプル領収書で前処理後画像を `processed/` で確認）。

## Tests / Validation

- 単体: `pytest tests/test_image_preprocessing.py tests/test_coord_normalizer.py tests/test_image_resize.py -v`
- 結合: `pytest tests/test_image_processing_service.py -v`
- 全件: `pytest`
- 整形: `black .`
- 目視検証（企業内で実施）:
  ```bash
  uv run python main.py --input-dir ~/Downloads/receipts --image-name <低Confidenceな領収書> \
      --preprocess-mode clahe+adaptive --target-short-side 960
  ```
  期待: `processed/preprocessed_<画像>.jpg` が生成され、文字が CLAHE/二値化で強調されているのを目視。加えて `output_json/` に `{stem}_{mtime}-raw_data.json`（前処理なし）と `{stem}_{mtime}-raw_data.preprocessed.json`（前処理済み）の**2ファイル**が生成され、topmost Confidence が改善しているか比較。

## Risks / Tradeoffs / Open Questions

- **適応的二値化の過強調リスク**: レシートの薄い罫線・背景ノイズまで二値化して潰す恐れ。→ CLAHE→adaptive の順で適用し、`--preprocess-mode` で `clahe` / `adaptive` / `clahe+adaptive` / `none` を切替可能にして比較検証する。
- **2回目OCRのコスト**: 低Confidence時のみの再試行なので通常フローへの影響は限定的。
- **raw_data の2ファイル保存**: 再試行時、前処理なしは `{stem}_{mtime}-raw_data.json` に温存、前処理済みは `{stem}_{mtime}-raw_data.preprocessed.json` に**別名保存**する（再出力は1回でOK）。後段の正規化・パースは前処理済み raw を対象とする。両方を目視/JSON比較して効果を検証する（要件の「比較データ残存」要望に対応）。
- **watcher と CLI の二重実装**: 両パスで同じ前処理フローを持つ。ロジックは `image_preprocessing` + `ocr_pipeline` に集中させ、サービス層の重複を最小化する。
- **未確定事項（実装後に確認）**:
  - CLAHE の `clipLimit` / `tileGridSize` と adaptiveThreshold の `blockSize` / `C` の最適値 → デフォルトを Issue 例（2.0 / (8,8) / 11 / 2）で据え、検証結果で調整。
  - 対策4（モデル切替）は本 Issue スコープ外として別 Issue で扱うか。
  - デフォルト `--target-short-side` を 960 のままにするか 1200 に上げるか → 検証後に判断。

  ## PR #37 レビュー対応計画（2026-10-02）

  ### 目的

  PR #37 レビューで見つかった再試行フローの不整合を解消し、CLI・watcher・直接サービス利用で前処理設定が一貫して動作するようにする。既存の原本 raw JSON と前処理済み raw JSON を両方残す設計は維持する。

  ### 対応方針

  1. `OutputWriter` が `-raw_data.preprocessed.json` も認識し、通常 raw と前処理済み raw のどちらから構造化しても同じ `{stem}_{mtime}-structured_data.json` に出力する。
  2. `target_short_side` を初回 OCR にも渡す。再試行時だけでなく、通常 OCR と初回 Confidence 判定も指定サイズで実行する。
  3. `preprocess_force` を `main.py` から polling / watchdog、各 watcher 呼び出し、`ReceiptProcessor` まで伝播し、高 Confidence でも指定モードで再試行する。
  4. `build_preprocess_fn()` は明示された4モード（`none` / `clahe` / `adaptive` / `clahe+adaptive`）以外を `ValueError` とする。CLI choices による検証に加え、直接サービス/API利用時も不正値を黙認しない。

  ### スコープ外

  - PRスコープ分割の提案は、現在の作業ツリーにある既存の文書・指示ファイル変更を改変せず、この修正では扱わない。
  - OCRアルゴリズム、前処理パラメーター、ユーザー画像を用いた目視品質評価は変更しない。

  ### 検証方針

  - 前処理済み raw 由来でも通常 raw と同じ構造化出力名になることをテストする。
  - `target_short_side` が通常 OCR の `process_image()` に渡ることをサービス単体・watcher側で確認する。
  - force が polling と watchdog の委譲先まで伝播し、高 Confidence 入力にも前処理を適用することをテストする。
  - 既知4モードの既存動作を維持し、未知モードで `ValueError` となることをテストする。
  - 変更箇所に対応する pytest を実行し、関連ファイルを Black で確認する。
