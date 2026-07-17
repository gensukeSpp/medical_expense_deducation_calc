# Issue #34 問題点2: 一覧表示に file_stem を追加

## 目的
一覧ページの表示項目「{クリニック(調剤薬局)名}-{日付}」だけでは修正対象がわかりにくい問題を解決する。

## 変更内容
`display_name` に `file_stem`（元画像ファイル名ベースの識別子）を追記し、同じクリニック名・同じ日付のレシートが複数ある場合でも区別できるようにする。

### 表示形式（変更後）
```
{クリニック名}-{日付} [{file_stem}]
```

例: `ABCクリニック-2026-01-15 [IMG_20260115_xxx_12345]`

## 変更ファイル

### 1. `app/services/receipt_service.py`
`get_all_receipts()` 内の `display_name` 生成を変更:
```python
# 変更前
display_name = f"{clinic}-{date}"
# 変更後
display_name = f"{clinic}-{date} [{file_stem}]"
```

### 2. `app/web/templates/index.html`（必要に応じて）
`display_name` に file_stem が含まれるため、テンプレート自体の変更は原則不要。
file_stem 部分を視覚的に小さく表示したい場合は、service層で分割して渡す方式に変更する。

## 検証方法
```bash
# 一覧表示の確認
uv run main.py --serve --db-path data/db.sqlite3
# → ブラウザで localhost:8000 にアクセス、表示名に [{file_stem}] が付いていることを確認

# 既存テストの互換性確認
pytest tests/ -v

# フォーマット
black .
```