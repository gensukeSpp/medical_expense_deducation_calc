# Issue #40: テスト計画 — 前方テンプレート補正の基底不一致修正

## テスト戦略

- **フレームワーク**: pytest / conftest.py（`PYTHONPATH=.` 有効化）
- **主対象**: `tests/test_structural_parser.py`（`_apply_template_corrections()` の中枢である
  `process_input_json` / `ExtractionService` を検証）
- **方針**: `coord_basis` の値（`'date'` / `'topmost'` / None）による前方補正の分岐を直接テスト。
- **新規 commit しない**: テスト追加は既存 `test_structural_parser.py` への追記で行う（新規ファイル不要）。

## テストケース一覧

### Task 2: 移行済み（date 基準）でスキップ

#### TC-01: date 基準 template では座標上書きがスキップされる

| 項目 | 内容 |
|------|------|
| テスト名 | `test_template_based_extraction_skipped_when_date_basis` |
| 概要 | `coord_basis='date'` の template を持つ clinic で `process_input_json` を実行 |
| 準備 | clinic + template 作成後、`UPDATE templates SET coord_basis='date'` で移行済みを模擬。raw_data は既存 SAMPLE を使用 |
| 確認点 | `result["amount"]` が座標上書きされず、テキスト抽出（mock）の値のまま |
| 検証方法 | ① 誤上書きし得る座標配置で「上書きされない」ことを確認、または ② `search_fields_by_proximity` をモックして「date 基準時は呼ばれない」ことを直接断言 |

#### TC-02: date 基準 template で誤上書きが起きない（具体配置）

| 項目 | 内容 |
|------|------|
| テスト名 | `test_date_basis_template_no_false_overwrite` |
| 概要 | date 基準 template の座標が raw の「別フィールド位置」に近い配置でも、金額・日付が誤上書きされない |
| 準備 | template 座標を raw の別フィールド付近に置き `coord_basis='date'` にする |
| 確認点 | 上書きされない（見出し/他フィールドの値が金額・日付に混入しない）|

### Task 3: 未移行（topmost 基準）の従来動作

#### TC-03: topmost（未移行）では従来どおり座標上書きが動作

| 項目 | 内容 |
|------|------|
| テスト名 | `test_template_based_extraction_works_for_topmost_basis` |
| 概要 | `coord_basis='topmost'`（デフォルト）の template で従来どおり上書きされる |
| 準備 | 既存 `seed_clinic_with_template` / `test_template_based_extraction_override` を流用 |
| 確認点 | amount が template 座標で上書きされる |
| 備考 | 既存 `test_template_based_extraction_override`（amount→9999）が実質カバー。重複なら最小追加のみ |

#### TC-04: coord_basis が None（旧データ）でも従来動作

| 項目 | 内容 |
|------|------|
| テスト名 | `test_template_based_extraction_when_coord_basis_none` |
| 概要 | `coord_basis` が未設定（None）の旧 template でも `or "topmost"` により従来どおり動作 |
| 準備 | template を `coord_basis` 未設定のまま挿入（#39 前の旧データを模擬） |
| 確認点 | 座標上書きが従来どおり働く |

### Task 4: 回帰・全体

#### TC-05: clinic 名上書きと新規 creation は date 基準でも維持

| 項目 | 内容 |
|------|------|
| テスト名 | `test_date_basis_still_fixes_clinic_name` |
| 概要 | 移行済み clinic であっても ③（clinic 名の正しい名へ上書き）と ④（新規作成）が動く |
| 準備 | 類似 clinic 名で template マッチ、または未登録 clinic |
| 確認点 | clinic 名が正しい名に補正される / 新規 clinic が作成される |

## エッジケース一覧

| ケース | 対応方針 |
|--------|---------|
| `coord_basis` が None（旧データ） | `or "topmost"` → 従来動作 |
| 移行済みでの複数フィールド | 全フィールドの座標上書きをスキップ |
| レイアウトマッチング（`match_template_by_layout`） | name 解決が見つからない場合のみ走る分岐。date 基準でも実質回避。完全排他ならガードを追加（今回は対象外として記録）|
| 既存 SAMPLE を使う場合の期待値 | seed fixture の coords 内容に応じて固定（実装時に正確化）|
| 前・後両経路 | `process_input_json` 共通のため 1 箇所で両方に効く（経路別テストは既存の sufficient）|

## テスト実行方法

```bash
# 対象単体
uv run pytest tests/test_structural_parser.py -v

# 全テスト（既存 + 追加）
uv run pytest tests/ -q

# 整形
uv run black --check app/structural_parser.py tests/test_structural_parser.py
```

## 既知の事前テスト失敗（本修正と無関係）

- `test_image_processing_service.py::TestRunOcr::test_calls_process_image_and_logs` —
  base でも同様に失敗する既知の失敗（`caplog` が INFO ログを捕捉せず `"Saved 1 item to"` が空）。
  本修正で直さない。色テストの失敗はないことを確認する。