# Architecture: 分割氏名の自動マルチボックス対応

## データ構造

### `coords_corrections` の型拡張

現在: `Dict[str, List[List[int]]]` — 単一4点ポリゴン

```python
{"name": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]}
```

拡張後: 単一box / マルチbox の両方を許容

```python
# 単一box（既存、後方互換）
{"name": [[100,100],[140,100],[140,140],[100,140]]}

# マルチbox（新形式）
{
  "name": [
    [[67,126],[205,130],[203,198],[65,194]],    # "山田"
    [[255,126],[379,135],[374,209],[250,200]]   # "太郎様"
  ]
}
```

**判別条件**: `isinstance(value[0][0], list)` → True = マルチ、False = 単一

## Forward方向: 修正→テンプレート学習フロー

### 現状のフロー

```
User修正 → process_feedback()
  → field_queries 構築
  → search_coordinates(ocr_entries, "山田太郎")  ★ 失敗 → None
  → coord_results["name"] = None
  → process_correction_feedback() で name は not_found
```

### 拡張後のフロー

```
User修正 → process_feedback()
  → field_queries 構築
  → search_coordinates(ocr_entries, "山田太郎")  ★ 失敗 → None
  → **フォールバック: サブストリングライン検出**
      Step 1: OCRエントリをY中心でライングルーピング (tolerance=20px)
      Step 2: full_query "山田太郎" との相互サブストリングマッチ
              - "山田" ∈ "山田太郎" ✓
              - "太郎" ∈ "太郎様"（"様"除去後）→ "太郎" ∈ "山田太郎" ✓
      Step 3: X座標でソート → テキスト連結 "山田太郎"
      Step 4: 連結結果とfull_queryの類似度検証 (threshold≥0.7)
      Step 5: 検証OK → マルチボックス形式で保存
  → coord_results["name"] = [box1, box2]  ← マルチ
  → process_correction_feedback() で name がマルチとして保存
```

### サブストリングマッチの詳細

```python
def _find_multi_boxes_by_substring(
    ocr_entries: List[dict],
    full_query: str,
    line_tolerance: float = 20.0,
    similarity_threshold: float = 0.7,
) -> Optional[List[List[List[int]]]]:
    """
    1. OCRエントリをY中心でライン分割
    2. 各ライン内で full_query とサブストリング関係にあるエントリを抽出
    3. X座標でソート
    4. 連結テキストと full_query の類似度を検証
    5. 検証OKならマルチボックスリストを返す
    """
```

## Reverse方向: テンプレート→抽出フロー

### 現状のフロー

```
_apply_template_corrections()
  → search_by_proximity_multi(ocr_entries, coords)
  → coords["name"] が単一box → search_by_proximity() × 1
  → matched["text"] = "山田" or "太郎" (片方のみ)
  → extracted["name"] = "山田" (不正確)
```

### 拡張後のフロー

```
_apply_template_corrections()
  → search_fields_by_proximity(ocr_entries, coords)
      ↓
      field "name":
        coords["name"] がマルチbox → search_by_proximity() × N
          → match1: text="山田", box=box1
          → match2: text="太郎様", box=box2
        → X座標でソート → 連結 → "山田太郎様"
        → "様" サフィックス除去 → "山田太郎"
      ↓
  → extracted["name"] = "山田太郎"
```

## 非機能要件

### 後方互換性

- 既存の単一box形式データは修正不要
- DBの `coords_corrections` TEXT値は変更なし（形式が拡張されるのみ）
- `template_history` テーブルも同様に影響なし

### エッジケース

| ケース | 動作 |
|---|---|
| 全く別のテキストがサブストリング一致 | 類似度検証で reject（threshold<0.7） |
| 3つ以上に分割 | サブストリングマッチが全収集 → Xソート → 連結 |
| 「様」を含むboxと含まないbox | 連結後「様」サフィックス除去（`rstrip("様")`） |
| サブストリングが別ライン | ラインを跨ぐサブストリングは reject（同一ラインのみ許容） |
| テンプレート未学習（初回） | 単一boxとして保存 → 次回修正時にマルチ学習 |