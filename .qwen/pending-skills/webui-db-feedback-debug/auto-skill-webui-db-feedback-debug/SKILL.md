---
name: webui-db-feedback-debug
description: Web UI 修正が DB の座標フィードバック / テンプレート / corrections に反映されない問題の調査手順と修正パターン
source: auto-skill
extracted_at: '2026-07-06T01:59:14.319Z'
---

# Web UI 修正 → DB フィードバック不具合の調査・修正手順

## 目的

Web UI でユーザーが修正した値が `templates.coords_corrections` や `corrections` テーブルに正しく反映されない問題を、コードトレースと原因特定から修正する。

## 手順

### 1. Issue の内容把握

- `gh issue view <number>` で詳細を取得
- 「OK動作」と「NG動作」を分離（何が動いて何が動いていないか）
- 受け入れ要件（Acceptance Criteria）を抽出し、テストケースとの対応を考える

### 2. データフローの全体像を把握

以下の階層を順に読み、修正のデータフローを追跡する:

| 階層 | ファイル | 確認ポイント |
|------|---------|------------|
| Web UI | `app/web/server.py` の `PUT /{file_stem}` | `updates` の構築、`service.update_receipt()` 呼び出し |
| Service | `app/services/receipt_service.py` | `ReceiptUpdater` への委譲 |
| Updater | `app/services/receipt_updater.py` | 更新の5ステップ（load → normalize → DB → coordinate feedback → save） |
| DB | `app/db.py` の `add_correction()` | 競合チェック、`normalized_json` 更新 |
| Coordinate | `app/services/receipt_updater.py` の `_process_coordinate_feedback()` | 座標検索ロジック（近接 vs テキスト） |
| Template | `app/template_feedback.py` の `process_correction_feedback()` | テンプレート更新と履歴保存 |
| Normalization | `app/normalization.py` の `parse_date()` / `parse_amount()` | 入力値の正規化（元号対応など） |

### 3. バグパターン別の診断ポイント

#### パターンA: `templates.coords_corrections` に一部フィールドしか反映されない

**原因1: 近接検索とテキスト検索が排他になっている**
- `receipt_updater.py:_process_coordinate_feedback` で、`if template_coords:` の分岐が `else` と排他になっている
- テンプレートが存在すると**近接検索のみ**実行され、新規修正フィールドのテキスト検索がスキップされる
- **修正**: 両方の検索を実行し結果をマージする

**原因2: old_value が空文字で座標検索がスキップされる**
- 同じく `_process_coordinate_feedback` 内で `query_val = old_value if old_value is not None else new_value`
- `old_value` が `""`（空文字）の場合、`""` は `None` ではないので `query_val = ""` となる
- `search_coordinates()` は空文字を受け取ると即座に `None` を返す
- **修正**: `query_val = old_value or new_value` に変更（`""` は falsy として扱う）

#### パターンB: `corrections` テーブルに2回目以降の修正が挿入されない

**原因: `add_correction()` の競合チェックが厳しすぎる**
- `db.py:add_correction()` で `str(current_value) != str(old_value)` の比較
- `normalized_json` の `None` → `str(None)` = `"None"`
- `structured_data.json` の `""` → `str("")` = `""`
- `"None"` ≠ `""` で `ValueError` 発生
- **修正**: `ValueError` の代わりに `current_value` を `old_value` として使う

#### パターンC: 日付が `null` になる（元号未対応）

**原因: `parse_date()` が元号形式（令和）をパースできない**
- `normalization.py:parse_date()` に「令和N年M月D日」や「R{N}.M.D」のパターンがない
- 令和短縮形（`R6/3/15`）は既存の `M/D/YY` パターンに先にマッチするため、**令和パターンを `M/D/YY` より前に配置**する必要がある
- **修正**: 令和パターンを追加し、短縮形は `M/D/YY` より前に配置

### 4. 修正の適用順序

推奨される修正順序（依存関係順）:

1. **`add_correction` 競合チェック緩和** — 影響範囲が最小、DB 操作の基盤
2. **`parse_date` 令和対応** — 独立した修正、normalization レイヤー
3. **`_process_coordinate_feedback` 空文字対策** — 小修正
4. **`_process_coordinate_feedback` 近接+テキスト両立** — 中核修正、最後に適用

### 5. テスト戦略

| テスト対象 | ファイル | テスト内容 |
|-----------|---------|-----------|
| 令和 date パース | `tests/test_normalization.py` | 全形式（長形式・短形式・元年）の正常系 |
| 同一フィールド2回目修正 | `tests/test_db.py` | `add_correction` を同一フィールドに2回連続実行 |
| 新規フィールド追加 + テンプレート反映 | `tests/test_feedback.py` | 既存テンプレートに `amount` がある状態で `name` を修正 → 両方反映 |
| 空文字 old_value 座標検索 | `tests/test_feedback.py` | structured_data に空文字フィールドがある状態で修正 |

### 6. 検証

```bash
pytest -q --tb=short  # 全テスト通過
black --target-version py311 . --check  # フォーマットOK
```

## 注意点（経験則）

### 令和短縮形のパターン順序
- `R6/3/15` は `M/D/YY` パターン（`(\d{1,2})/(\d{1,2})/(\d{2,4})`）に先にマッチする
- 令和短縮形の正規表現は `M/D/YY` より**前に**配置する必要がある
- 逆にドット区切り `R6.3.15` は `M/D/YY` にマッチしないので順序は任意

### old_value の型の多様性
- `structured_data.json` の `null` は Python では `None` になる
- `normalized_json` の `null` も `None` になるが、**一度修正が入ると文字列に変わる**
- `str(None)` = `"None"` という Python の仕様が原因で、`None` と `""` の比較が予期せず失敗する
- **old_value の比較は `str()` 変換ではなく、`None` と `""` を同値として扱うロジックが必要**

### 座標検索の2方式は両方実行すべき
- 近接検索（proximity）とテキスト検索（text similarity）は独立した検索軸
- テンプレート既存フィールドは近接検索（高精度）、新規修正フィールドはテキスト検索（唯一の手段）
- 両方実行し、近接検索の結果を優先（テキストより座標の方が信頼性が高い）
- 近接検索で見つかったフィールドは、テキスト検索結果を上書きする
- 近接検索で見つからなかったフィールドは、テキスト検索結果を維持する

### テストデータの注意点
- `parse_amount()` は `"3,800"` ではなく `"3,800円"` などアノテーション付きの文字列を期待
- `parse_date()` の M/D/YY パターンは `YY >= 70` で 1900年代、`YY < 70` で 2000年代と解釈
- テストの raw_data JSON ファイル名は `{stem}*-raw_data.json` パターンで glob 検索される