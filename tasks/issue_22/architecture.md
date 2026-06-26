# Issue #22 アーキテクチャ決定事項

## データ構造

### template_history テーブル（新規）

```sql
CREATE TABLE IF NOT EXISTS template_history (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    clinic_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    coords_corrections TEXT,       -- 更新前のスナップショット
    changed_fields TEXT,           -- 変更されたフィールド名のJSON配列
    change_reason TEXT DEFAULT 'user_correction',
    receipt_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE,
    FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
    FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE SET NULL
);
```

### templates.coords_corrections の形式

box4点座標をフィールド名をキーとして保存:

```json
{
  "amount": [[400, 300], [480, 300], [480, 340], [400, 340]],
  "date": [[50, 50], [200, 50], [200, 80], [50, 80]]
}
```

## モジュール構成

### 新規モジュール

| モジュール | 責務 | 主要関数 |
|-----------|------|---------|
| `app/coord_search.py` | OCRテキストからの座標検索 | `search_coordinates()`, `search_coordinates_multi()` |
| `app/template_feedback.py` | テンプレート更新の調整 | `process_correction_feedback()` |

### 変更モジュール

| モジュール | 追加内容 |
|-----------|---------|
| `app/db.py` | `get_receipt_by_source_path()`, `get_latest_template_by_clinic()`, `insert_template_history()` |
| `app/web/server.py` | PUT更新時に座標FBルーチンを追加 |

## 座標検索アルゴリズム

- **方式**: `difflib.SequenceMatcher.ratio()` — 文字列類似度（Unicode対応、外部依存不要）
- **デフォルト閾値**: 0.7（70%以上の一致で採用）
- **検索対象**: `receipts.ocr_json` カラム（OCR生データ、box座標付き）
- **フォールバック**: ocr_json がない場合はスキップ（エラーログ出力）

## クリニックテンプレート更新フロー

1. `search_coordinates()` で各修正フィールドの old_value を OCR テキストから検索
2. 座標が見つかったフィールドのみ `field_coords_map` に含める
3. `get_latest_template_by_clinic()` で既存テンプレート取得（なければ新規 UUID）
4. `upsert_template()` で coords_corrections をマージ更新
5. `insert_template_history()` で更新前のスナップショットを保存

## エラーハンドリング

- 座標FB全体を `try/except` で保護 → 失敗しても修正処理は継続
- 座標未検出フィールドはレスポンスで報告 → `coord_error.html` 表示
- エラー詳細は `errors.log` に JSON Lines 形式で記録

## 既存コードとの整合性

- 既存の `test_web.py` の10テストケースは無修正でパス
- `server.py` の `update_item` は内部構造を維持したまま座標FBを追加
- DBスキーマは後方互換性を維持（テーブル追加のみ）
- `add_correction()` の競合検出（old_value チェック）はそのまま活用