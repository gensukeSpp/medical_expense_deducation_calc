# Issue #40: date 基準移行後の前方テンプレート補正の基底不一致修正

## 目的

Issue #39 で `templates.coord_basis` が `'date'` に移行済みの clinic に対し、**移行後の別レシート**を
画像OCR / watcher 経路で処理するとき、前方テンプレート補正
（`ExtractionService._apply_template_corrections()`）が topmost 基準の raw に対して
date 基準の `coords_corrections` を照合してしまう不整合を修正する。

## 参照

- [Issue #40](https://github.com/gensukeSpp/medical_expense_deducation_calc/issues/40)
- [Issue #39 実装](../../tasks/issue_39/overview.md) — date 基準正規化の導入
- [仕様](../../specs/2026-10-06-spec.md)「既知の課題（次 Issue #40）」
- `app/structural_parser.py` — `ExtractionService._apply_template_corrections()`（修正対象）
- `app/db.py` — `get_latest_template_by_clinic()` が `coord_basis` を返す（#39 実装済み）
- `app/services/image_processing_service.py` / `app/services/receipt_processor.py` — 処理経路
- `.hermes/rules/coordinate-normalization.md`

## スコープ

### 含むもの
- 移行済み（`coord_basis=='date'`）clinic の前方テンプレート補正で、
  `coords_corrections` を使った座標駆動処理をスキップ（粒度1）。
- 不整合の回帰テスト追加。
- 未移行 clinic（`coord_basis=='topmost'`）の挙動は変更しない。

### 含まないもの（後続 TODO）
- 案A（`_parse_structured` の前に date 化 → フル parse）は採択しない。
- 移行済み clinic の前方補正を「正しく効かせる」座標基準の同期は対象外（本 Issue は誤上書き防止のみ）。
- DB `ocr_json` の date 基準化・template 移行・date anchor 正規化は #39 のまま変更しない。

## 対応方針（確定: 案B・粒度1）

Issue #40 の設計メモにある **案B** を採択し、**粒度1だけ**を実施する。

> **案B（粒度1）**: 移行済み clinic（`coord_basis=='date'`）では、
> `_apply_template_corrections()` 内で `coords_corrections` を使う**座標駆動の処理を実行しない**。
> clinic 名の解決（完全一致/テキスト類似度）、clinic 名の正しい名への上書き、新規 clinic 作成は残す。

### 粒度の定義（案B の斟酌）

`_apply_template_corrections()` 内の処理を3つに分けて考える。

| 処理 | 説明 | coord 使用 | 案B粒度1での扱い |
|------|------|-----------|-----------------|
| ① clinic 特定（完全一致 / テキスト類似度） | `get_clinic_by_name` / `find_clinic_by_text_similarity` | 部分（レイアウト除く） | **残す** |
| ② **座標ベースのフィールド値上書き**（`search_fields_by_proximity`） | 各フィールド値を template 座標から引き直す | **あり** | **スキップ**（これが誤上書きの原因）|
| ③ clinic 名の正しい名への上書き | `matched_clinic_name` | なし | **残す** |
| ④ 新規 clinic 作成 | `get_or_create_clinic` | なし | **残す** |

※ ①のうち「レイアウトマッチング（`match_template_by_layout`）」は `coords_corrections` を使うため、
  移行済み clinic では実行しない（name 解決で template が見つからない場合のみ走る分岐のため、実質自然に回避される）。
  この点は実装メモに明記する。

### なぜ案Bか（案Aを採らない理由）

- **案A**（parse 前に date 化 → フル parse）は、date 解決に先立つ parse が必要という循環があり、
  オーケストレーションを広く変更する。加えて「date化を前へ動かす」ことは DB/出力へ波及し、回帰リスクが大きい。
- **案B**（座標上書きを止める）は誤上書きを**確実に**防ぐ最小変更で、値はテキスト抽出（LLM）にフォールバックするだけ。
  移行済み clinic の前方補正の機能低下は許容する（#40 の受入条件2「無効化で誤上書きを防ぐ」を満たす）。

## 受入条件

1. 移行済み clinic（`coord_basis=='date'`）のレシートで、前方補正による座標上書きが実行されない。
2. 誤上書きが起きない（レシート左上の見出し/クリニック名が金額・日付に混入しない）。
3. clinic 名の正しい名への上書きと新規 clinic 作成は従来どおり動作する。
4. 未移行 clinic（`coord_basis=='topmost'`）の挙動は変更されない。
5. 既存テストを壊さず、回帰テストを追加する。

## 未確定事項（実装時に決めない・現状維持）

- 閾値は既存のまま（本修正は閾値の導入を伴わない）。
- DB スキーマ・migration・`coord_basis` は #39 のまま変更しない。

## 使用する技術・制約

- 判定は `template.get("coord_basis") == "date"`（#39 で `get_latest_template_by_clinic` が返す）。
- 前方補正の座標スキップは `structural_parser.py` の `_apply_template_corrections()` 内で行う。
- 経路は画像OCR / watcher の両方（`process_input_json` 経由で共通の `ExtractionService` を呼ぶため、
  1箇所の修正で両経路に効く）。
- テストは `tests/test_structural_parser.py` を拡張（移行済み/未移行の分岐）。