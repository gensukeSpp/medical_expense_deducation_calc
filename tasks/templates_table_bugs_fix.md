# 問題点のまとめ
## Issue #28 参照

---


1. templates.coords_corrections に修正が反映されない（根本原因：3つのバグ）

**バグA**: 空文字の old_value を座標検索クエリに使う

receipt_updater.py の _process_coordinate_feedback にあるコード:

```python
 1 old_value = old_data.get(field_name)
 2 query_val = old_value if old_value is not None else new_value
```

old_data.get("name") が "" (空文字) の場合、"" は None ではないため query_val = "" になる。その後 search_coordinates(ocr_entries, "") が呼ばれるが、if not query: で True になり即座に None を返す。

→ 初期抽出で未検出のフィールド（name, clinic, date）をユーザーが修正しても、座標検索クエリが空文字のため常に失敗する。

該当ファイル: app/services/receipt_updater.py — _process_coordinate_feedback メソッド

**バグB**: 既存テンプレートがある場合、新規修正フィールドのテキスト検索が行われない

```python
 1 if template_coords and ocr_entries:
 2     # 近接検索 — テンプレートに既存のキーしか検索しない！
 3     proximity_results = search_by_proximity_multi(ocr_entries, template_coords)
 4     ...
 5 else:
 6     # テキスト検索 — field_queries (修正フィールド) で検索
 7     ...
```

既存テンプレートが存在する（例：amount のみ）と、if 分岐に入り 近接検索のみ 実行される。この時、新規修正フィールド（name, clinic, date）はテンプレートにないため近接検索の対象外となり、テキスト検索（else 分岐）も実行されない。

→ coord_results にはテンプレート既存フィールドの座標しか入らず、新規修正フィールドの座標は常に欠落する。

該当ファイル: app/services/receipt_updater.py — _process_coordinate_feedback メソッド

**バグC**: corrections テーブルの2回目以降の挿入が失敗する

db.py の add_correction にある競合チェック:

```python
 1 current_value = norm_data.get(field_name)
 2 if str(current_value) != str(old_value):
 3     raise ValueError(f"Conflict: field '{field_name}' has changed...")
```

2回目以降の修正で normalized_json の値が既に更新済みの場合、current_value と old_value が一致せず、バリューエラーが発生する。これにより corrections テーブルへの2回目の挿入が失敗する（ユーザー報告: 「2回目以降『修正』ボタンクリックしても挿入されない」）。

該当ファイル: app/db.py — add_correction 関数

---

1. 元号（令和）の日付がパースされない

normalization.py の parse_date() は以下の形式のみ対応:

 - YYYY/MM/DD, YYYY-MM-DD, YYYY年M月D日
 - M/D/YY, M/D/YYYY
 - YYYYMMDD (コンパクト)

未対応の元号形式:
 - 令和7年3月15日
 - R7.3.15
 - 令和7年3月15日

該当ファイル: app/normalization.py — parse_date 関数

---

1. サーバー再起動後の動作不良（上記バグの結果論）

テンプレートに正しく座標が保存されていないため、再起動後に読み込んでも前回の修正が反映されていない状態になる。個別の永続化バグで
はなく、バグA/Bの結果として自然に発生する症状。

---

調査結果の関係図

  1 ユーザーが Web UI で修正
  2         │
  3         ▼
  4 receipt_updater.update_receipt()
  5         │
  6         ├─ 1. corrections テーブル → バグC (2回目以降失敗)
  7         ├─ 2. receipts.normalized_json → OK
  8         ├─ 3. structured_data.json  → OK
  9         └─ 4. _process_coordinate_feedback()
 10                 │
 11                 ├─ バグA: old_value="" → 座標検索クエリ空文字
 12                 ├─ バグB: テンプレート存在 → 新規フィールド未検索
 13                 │
 14                 ▼
 15            templates.coords_corrections → 未更新（または部分的）