# Issue #22: 修正値検知・座標補正フィードバック

## 目的

ユーザーが Web UI で修正した値を検知し、クリニック毎のテンプレートの座標値を更新するフィードバック機構を実装する。

参照: [要件定義書](../../要件定義書.md) 「5. ロジックフロー 5」「6. 実装ステップ ステップ4」

## スコープ

### 含むもの
- ユーザー修正（PUT /{file_stem}）の検知
- `receipts.ocr_json` からの座標検索（類似度マッチング）
- クリニックテンプレート（`templates.coords_corrections`）の更新
- テンプレート更新履歴の保存（`template_history` テーブル）
- 座標未検出時のエラーページ表示
- 単体テスト・結合テスト

### 含まないもの（次回タスク）
- しきい値による補正値更新の精緻化（受入条件にあるが本タスクでは未使用）
- ロールバック UI（履歴保存のみ）
- 命名抽出LLM（RealLLMClient）の実装

## 受入条件

1. 修正時に `receipts.ocr_json` から該当テキストを類似度検索できること
2. 座標が見つかった場合、`templates.coords_corrections` が更新されること
3. 座標が見つからなかった場合、エラーページが表示されること
4. テンプレート更新前に `template_history` にスナップショットが保存されること
5. DB未接続時も通常の修正処理が継続すること
6. 既存テスト（test_web.py）が全てパスすること

## 設計判断

| 項目 | 決定 | 理由 |
|------|------|------|
| 座標保存形式 | box4点座標 `[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]` | OCR生データと同一形式、補正時にbox全体を利用可能 |
| 検索戦略 | difflib.SequenceMatcher 類似度マッチング | 軽量、外部依存不要、日本語（Unicode）対応 |
| 検索対象 | `receipts.ocr_json` を優先 | パイプライン処理時に座標付きで保存済み |
| しきい値 | デフォルト 0.7、テスト用に調整可能 | 第1フェーズでは固定値、次回タスクで調整機構を検討 |
| ロールバック | `template_history` テーブルに履歴保存のみ | UIは次回タスク、保存のみで基盤構築 |
| テンプレートFK制約 | upsert → history の順で実行 | 新規テンプレート作成時の外部キー制約違反を防止 |

## データフロー（追加分）

```mermaid
flowchart TD
    A[PUT /{file_stem}] --> B[既存: corrections保存 + JSON更新]
    B --> C[get_receipt_by_source_path で ocr_json 取得]
    C --> D[coord_search.search_coordinates]
    D --> E{old_value と一致?}
    E -->|Yes| F[template_feedback: upsert_template]
    F --> G[template_history 保存]
    E -->|No| H[coord_error.html 応答]
    G --> I[成功応答]
```