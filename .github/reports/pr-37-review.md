# PR #37 Review — OCR 前処理

## 参照資料・前提
- PR: #37「feat: 読み取りの質向上のための OCR 前処理」。本文・変更ファイル・ブランチを確認。目的はIssue #36に基づくOCR前処理と、前処理前後の出力を比較できる再試行フローの追加。
- Issue: #36を確認。低Confidence（topmost文字 < 0.8）のとき1回再試行し、処理画像を`processed/`に保存する要件。resize調整は手動で可能にし、CLAHE/適応的二値化の効果を検証する意図。
- タスク計画: `tasks/issue-36/plan.md`、`tasks/issue-36/tasks.md`を確認。タスク1〜8の大枠は実装に対応。手動の目視検証はユーザー画像が必要としており、PR本文にも検証結果・懸念が記載されている。
- 仕様: `specs/2026-09-29-spec.md`（作業ツリー上のローカル資料）を確認。
- 関連アーキテクチャ: `docs/architecture/2026-10-02-architecture.md`、背景として`docs/architecture/2026-07-16-architecture.md`を確認。前者はローカルの未追跡資料。
- 実装ルール: `.hermes/rules/ocr-preprocessing.md`を確認（ローカルで追加された資料）。
- 該当する`overview.md` / `architecture.md` / `test-plan.md`は`tasks/issue-36/`には存在せず、計画は`plan.md`と`tasks.md`。Issue #36のPR本文にある`processed/`未保存の懸念は、現HEADの単一画像パスでは保存処理が実装されており、記載が古い可能性がある。
- 比較対象: `main`ブランチがローカルにないため`origin/main`と比較（PRのbaseは`main`）。ローカル作業ツリーにはレビュー対象外の変更・未追跡ファイルがあり、レビューはPR差分を基準に実施。

## 総評
Issue #36の意図に沿い、前処理関数を分離し、通常OCR結果を保持したまま再試行結果を別ファイルに保存する構成は妥当です。一方、再試行結果から生成する構造化JSONの命名が既存の出力規則と合わず、通常の構造化JSONとして扱われない可能性が高いです。また、resizeオプションの適用範囲とwatcherへのforce伝播に仕様との不整合があります。以下の指摘を解消してからマージするのが望ましいです。

## 良い点
- CLAHE/適応的二値化を`app/image_preprocessing.py`に分け、モード選択を明示している。
- 読み取り専用のConfidence判定を追加し、前処理前のraw JSONを保持する設計は、比較・再現性の要件に合っている。
- 前処理時にグレースケールからBGR 3chへ戻してOCRへ渡す処理と、その形状を検証するテストがある。
- 低Confidenceの場合に一度だけ再試行する主要フローに、単体・サービス・watcherのテストが追加されている。

## 指摘事項

### [P1] 前処理済みrawから作る構造化JSONの名前が既存規則から外れる
- 箇所: `app/services/image_processing_service.py:91-92`、`app/services/receipt_processor.py:190-197`（出力名生成は`app/structural_parser.py:216-225`）
- 前処理済みrawのファイル名は`...-raw_data.preprocessed.json`です。`OutputWriter.write()`は末尾が`-raw_data`の場合だけその部分を除去するため、前処理済みrawを入力すると`...-raw_data.preprocessed-structured_data.json`を生成します。通常の`...-structured_data.json`と異なる名前になり、`_apply_low_confidence_flag()`が参照する通常名にも一致しません。さらに一覧取得は`*-structured_data.json`を対象とするため、再試行したレシートが別レコードとして表示・永続化される懸念があります。
- 影響: 前処理再試行のたびに構造化出力の命名・表示・Confidence flag適用が不整合になります。
- 改善: 構造化出力名を原本rawと同じレシートIDに明示的に対応付ける（例: writerに出力先名を渡す、またはraw suffixの除去処理を`.preprocessed`にも対応させる）。前処理あり/なし双方で同じ構造化JSONが更新されるテストを追加してください。

### [P2] `--target-short-side`が初回OCRに反映されない
- 箇所: `app/services/image_processing_service.py:72`、`app/services/image_processing_service.py:167-175`
- `target_short_side`は再試行の`_preprocess_and_retry()`から呼ぶ`process_image()`にしか渡されず、初回OCRの`_run_ocr()`は常に`process_image()`既定値960を使います。従って`--target-short-side`指定値は初回Confidence判定に反映されず、前処理が実行されない場合には全く適用されません。
- 影響: Issue #36の手動リサイズ調整が通常読み込みや初回判定で効かず、比較条件も意図したサイズになりません。
- 改善: 初回OCRにも`target_short_side`を伝播してください。前処理前rawを必ず960pxで残す設計が意図的なら、その仕様を明記し、CLIのresize指定が適用される経路・されない経路をテストで固定してください。

### [P2] `--preprocess-force`がwatcher経路に伝播せず、指定しても無視される
- 箇所: `main.py:28-54`、`app/watcher.py:73-95, 141-170, 179-214`、`app/services/receipt_processor.py:35-47, 177-180`
- 単一画像経路では`preprocess_force`をサービスへ渡しますが、watcherの`run_loop`/`run_watchdog`および`ReceiptProcessor`には引数がなく、判定は低Confidenceのみです。`--watch --preprocess-force`を指定してConfidenceが高い画像を処理しても、前処理されません。
- 影響: PRが導入した強制適用オプションがwatcherでは機能せず、CLIの実行モードで挙動が変わります。
- 改善: watcherの全呼び出し経路と`ReceiptProcessor`へbooleanを伝播し、強制時の高Confidence画像で前処理されるテストを追加してください。watcherでのforceをスコープ外とするなら、その制約をCLI help・仕様・PR本文に明記してください。

## 改善提案
- `build_preprocess_fn()`は既知の3モード以外をすべてcombined扱いにします。CLI経由では`choices`により制限されますが、サービス/API直接利用時の誤ったモード指定を黙って受理します。未知モードでは`ValueError`にするのが安全です。
- PRにはOCR前処理以外にCopilot指示書の大幅な整理、エージェント/スキル追加・削除が含まれています。レビュー容易性と変更目的の追跡のため、独立した文書・開発環境変更は別PRに分割することを検討してください。

## 検証結果
- `git diff origin/main --check`: 成功。
- `uv run pytest -q`: 183 passed / 1 failed。失敗は`tests/test_image_processing_service.py::TestRunOcr::test_calls_process_image_and_logs`で、`caplog`がINFOログを捕捉できず、`Saved 1 item to`が空になる既存テスト失敗と確認。PR本文・タスク資料も同じ失敗を既存扱いとして記載。
- 目視OCR品質検証は領収書サンプルが必要なため、本レビューでは実施していない。PR本文に実サンプルでの試行結果と回転の懸念が記載されている。
- 知識グラフは影響範囲の参考に使用。ソースとテストで内容を確認した。

## 優先度まとめ
1. P1: 前処理済みraw由来の構造化JSON命名・出力先の不整合
2. P2: `--target-short-side`が初回OCRに適用されない
3. P2: watcher経路で`--preprocess-force`が無視される
4. P3: モード値の防御的検証、PRスコープ分割

---

> 2026-10-02 レビュー記録
> 比較対象: `origin/main`（ローカル`main`なし）
> ローカル作業ツリーに既存の変更・未追跡資料があり、PR #37の差分以外の変更はレビュー対象外。
> 詳細は本文の「参照資料・前提」を参照。
> 