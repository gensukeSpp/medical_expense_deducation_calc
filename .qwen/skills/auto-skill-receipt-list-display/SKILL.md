---
name: receipt-list-display
description: 一覧ページの表示名を改善する手順 — display_name 生成ロジックの分析・修正・テスト
source: auto-skill
extracted_at: '2026-07-17T01:23:32.482Z'
---

# 一覧ページ表示名改善手順

## 目的
一覧ページの表示名（`display_name`）が修正対象の識別に不十分な場合、改善策を検討・実装する。

## 手順

### 1. 問題の正確な把握

- `gh issue view <番号>` で Issue 本文を取得し、問題の本質を読み解く
- 問題点が「一覧表示の項目だけでは修正対象がわかりにくい」というUX問題か確認する
- 現状の表示形式: `{clinic}-{date}` で、同一クリニック名が複数並ぶと区別がつかない

### 2. 現状のコード調査

以下のファイルを読み、表示名の生成フローを把握する:

- `app/services/receipt_service.py` — `get_all_receipts()` 内の `display_name` 生成
- `app/web/templates/index.html` — テンプレートの表示箇所
- `tests/test_web.py` — 既存テストの表示名アサーション

確認ポイント:
- `display_name` は service 層で生成される文字列か、テンプレートで組み立てているか
- 各レシートに `file_stem`（元画像ファイル名ベースの識別子）は渡されているか
- `low_confidence` 警告のような既存の付加情報はあるか

### 3. 改善候補の検討

以下の観点で候補を列挙し、トレードオフを比較する:

| 候補 | 実装容易さ | システム負荷 | 問題解決度 |
|------|-----------|-------------|-----------|
| `file_stem` 追加 | 高（数行の変更） | 低（既存データ流用） | 中（一意の識別子） |
| `created_at` 時間追加 | 高（既存カラム流用） | 低 | 中（時間差で区別） |
| 「未修正」フラグ | 中（DBクエリ追加） | 中（N+1問題） | 低（区別にならない） |
| 元画像ファイル名表示 | 高（既存データ流用） | 低 | 高（一意の識別子） |

### 4. 実装

**変更ファイル**:
- `app/services/receipt_service.py` — `get_all_receipts()` の `display_name` フォーマット変更
  ```python
  # 変更前
  display_name = f"{clinic}-{date}"
  # 変更後（例: file_stem 追加）
  display_name = f"{clinic}-{date} [{file_stem}]"
  ```
- `app/web/templates/index.html` — `display_name` が文字列の場合は変更不要。分割して渡す場合はテンプレート修正
- `tests/test_web.py` — 新フォーマットを検証するテスト追加

### 5. 検証

```bash
# Web テストの実行
pytest tests/test_web.py -v

# 全テストの互換性確認
pytest tests/ -v

# フォーマット
black .
```

## 注意点
- `display_name` は部分文字列チェック（`"キーワード" in response.text`）でテストされているため、既存テストは新しいフォーマットでも自動的にパスする（部分文字列として含まれるため）
- DBスキーマ変更は不要（既存データの再利用で対応可能）
- テンプレート変更が不要な設計（service層で完結）が望ましい