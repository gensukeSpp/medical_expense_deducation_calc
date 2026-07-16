# Issue #34: アーキテクチャ設計 — ハイブリッドキーマッチング

## 全体データフロー

```mermaid
graph TD
    subgraph "従来フロー（変更なし）"
        OCR[OCR JSON] --> MOCK[MockLLMClient<br/>抽出]
        MOCK --> EXTRACTED[extracted dict<br/>name, clinic, amount, date]
    end

    subgraph "ハイブリッドテンプレートマッチング（新規）"
        EXTRACTED --> STEP1{Step1:<br/>完全一致}
        STEP1 -->|get_clinic_by_name| FOUND1[テンプレート適用]
        STEP1 -->|None| STEP2

        STEP2[Step2: テキスト類似度] --> SIM[find_clinic_by_text_similarity]
        SIM -->|difflib ≥ 0.6| FOUND2[テンプレート適用]
        SIM -->|None| STEP3

        STEP3[Step3: 座標レイアウト] --> LAYOUT[match_template_by_layout]
        LAYOUT -->|近接マッチ率 ≥ 0.6| FOUND3[テンプレート適用]
        LAYOUT -->|None| NO_MATCH[新規クリニック作成<br/>従来の抽出結果維持]
    end

    subgraph "後処理"
        FOUND1 --> OVERRIDE[extracted[clinic] を<br/>正しい名前に上書き]
        FOUND2 --> OVERRIDE
        FOUND3 --> OVERRIDE
        OVERRIDE --> PROX[search_fields_by_proximity<br/>座標近接補正]
        NO_MATCH --> NORM
        PROX --> NORM[normalize_extracted → 出力]
    end
```

## モジュール構成

### 変更モジュール

| モジュール | 変更内容 |
|-----------|---------|
| `app/db.py` | `get_all_clinics()` / `get_all_templates_with_names()` を追加 |
| `app/coord_search.py` | `find_clinic_by_text_similarity()` / `match_template_by_layout()` を追加 |
| `app/structural_parser.py` | `_apply_template_corrections()` に2段階のフォールバックを追加、`_get_ocr_entries()` ヘルパーを抽出 |

### 変更しないモジュール

| モジュール | 理由 |
|-----------|------|
| `app/template_feedback.py` | テンプレート保存ロジックは変更不要 |
| `app/web/server.py` | Web UI の修正処理は変更不要 |
| `app/services/receipt_updater.py` | 修正時の座標フィードバックは変更不要 |
| `app/watcher.py` / `app/processor.py` | パイプライン呼び出しは変更不要 |
| `docs/schema.sql` | スキーマ変更不要 |
| `app/coord_normalizer.py` | 座標正規化処理は変更不要 |

## データ構造

### テキスト類似度マッチング アルゴリズム

```
入力:
  - extracted_clinic_name: str (例: "BCクリニック")
  - clinics: List[{id, name}] (全既存クリニック)

処理:
  1. normalize_text() で両者を正規化（全角→半角、英字小文字、非英数字除去）
  2. difflib.SequenceMatcher(None, norm_query, norm_name).ratio() を計算
  3. 最大類似度が threshold (0.6) 以上 → 該当クリニックを返す
  4. 該当なし → None を返す

出力:
  - clinic dict (id, name) または None
```

### 座標レイアウトマッチング アルゴリズム

```
入力:
  - ocr_entries: [{text, confidence, box: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]}, ...]
  - templates: [{id, clinic_id, clinic_name, coords_corrections: {field: box, ...}}]
  - proximity_threshold: 50px (DEFAULT_PROXIMITY_THRESHOLD)
  - match_ratio: 0.6

処理:
  各テンプレートについて:
    1. coords_corrections の各フィールド座標を取得
    2. 各フィールド座標の中心点から、最も近い OCR エントリまでの距離を計算
    3. 距離が proximity_threshold 以内のフィールド数をカウント
    4. match_rate = カウント / 全フィールド数
    5. match_rate ≥ match_ratio → マッチ！

  最大 match_rate を持つテンプレートを返す（該当なし → None）

出力:
  - template dict (id, clinic_id, clinic_name, coords_corrections) または None
```

### テンプレート適用フロー（`_apply_template_corrections` 修正後）

```
1. extracted["clinic"] から clinic_name 取得
2. Step1: get_clinic_by_name(clinic_name) → 完全一致
   └→ 見つかった場合は従来通りテンプレート取得・適用
3. Step2: find_clinic_by_text_similarity(clinic_name, all_clinics)
   └→ 見つかった場合はそのテンプレートを取得・適用
4. Step3: match_template_by_layout(ocr_entries, all_templates)
   └→ 見つかった場合はそのテンプレートを取得・適用
5. いずれも見つからなかった場合 → 従来の get_or_create_clinic で新規作成
6. Step2/3 でマッチした場合 → extracted["clinic"] を正しい名前に上書き
7. テンプレートの coords_corrections で search_fields_by_proximity を実行
```

## エラーハンドリング

| シナリオ | 対応 |
|---------|------|
| Step2 テキスト類似度マッチング失敗 | エラーログに記録し、Step3 へフォールバック |
| Step3 座標レイアウトマッチング失敗 | エラーログに記録し、従来フロー（新規クリニック作成）へフォールバック |
| 全テンプレートが空（DBにテンプレートなし） | 従来フローを維持 |
| OCRエントリが空 | 座標レイアウトマッチングをスキップ |
| 新規DB関数のエラー | 既存の `try/except` ブロック内でキャッチ、`append_error()` で記録 |