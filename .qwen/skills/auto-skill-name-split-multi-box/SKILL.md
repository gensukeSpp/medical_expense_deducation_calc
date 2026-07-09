---
name: auto-skill-name-split-multi-box
description: OCRで氏名が複数テキストボックスに分割された場合の自動検出・マルチボックス保存・テンプレート反映手順
source: auto-skill
extracted_at: '2026-07-07T01:31:38.034Z'
---

# 分割OCRテキストの自動マルチボックス対応

## 目的

OCR（PaddleOCR 等）が「山田」「太郎様」のように同一フィールド（特に氏名）を複数のテキストボックスに分割して検出するケースにおいて、テンプレート学習（Forward）とテンプレート抽出（Reverse）の両方向で正しく扱う。

## 前提

- `coords_corrections` は `Dict[str, Any]` として JSON TEXT で DB（`templates` テーブル）に保存される
- 値は単一box `List[List[int]]`（4点ポリゴン）またはマルチbox `List[List[List[int]]]`（複数ポリゴン）の両方を許容
- 判別条件: `isinstance(value[0][0], list)` → True = マルチ、False = 単一
- `search_by_proximity()`（中心点ユークリッド距離、20px閾値）と `search_coordinates()`（difflib類似度、0.7閾値）の2種類の検索が既に存在する

## 手順

### Step 1: マルチボックス検索ユーティリティの追加

`coord_search.py` に以下を追加:

#### 1-a. `_is_multi_box(value: Any) -> bool`

```python
def _is_multi_box(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    if not isinstance(value[0], list) or not value[0]:
        return False
    return isinstance(value[0][0], list)
```

#### 1-b. `search_fields_by_proximity(ocr_entries, field_box_map, threshold=20.0) -> Dict[str, Optional[str]]`

既存の `search_by_proximity_multi()` を拡張し、単一box/マルチbox両対応＋テキスト連結を行う。戻り値は `Dict[str, Optional[str]]`（テキスト文字列）であり、`search_by_proximity_multi` の `Dict[str, Optional[Dict]]`（OCRエントリ全体）とは異なるので注意:

```python
def search_fields_by_proximity(
    ocr_entries: List[Dict[str, Any]],
    field_box_map: Dict[str, Any],
    threshold: float = 20.0,
) -> Dict[str, Optional[str]]:
    result: Dict[str, Optional[str]] = {}
    for field_name, boxes in field_box_map.items():
        if boxes is None:
            result[field_name] = None
            continue

        if _is_multi_box(boxes):
            # Multi-box: search each box, concatenate texts in X order
            texts_with_x: List[tuple[str, float]] = []
            all_found = True
            for sub_box in boxes:
                match = search_by_proximity(ocr_entries, sub_box, threshold)
                if match and match.get("text"):
                    cx = _calculate_box_center(sub_box)
                    x_center = cx[0] if cx else 0.0
                    texts_with_x.append((match["text"], x_center))
                else:
                    all_found = False
                    break

            if all_found and texts_with_x:
                texts_with_x.sort(key=lambda t: t[1])  # sort by X-coordinate
                concat_text = "".join(t[0] for t in texts_with_x)
                concat_text = concat_text.rstrip("様")  # remove Japanese honorific
                result[field_name] = concat_text
            else:
                result[field_name] = None
        else:
            # Single box: use existing search_by_proximity
            match = search_by_proximity(ocr_entries, boxes, threshold)
            if match and match.get("text"):
                result[field_name] = match["text"]
            else:
                result[field_name] = None

    return result
```

**注意**: `search_by_proximity_multi()` は削除せず残す。`ocr_coordinate_service.py` の Bug B 近接検索パスで引き続き使用されている。

### Step 2: Reverse方向（テンプレート→抽出）の対応

`structural_parser.py::_apply_template_corrections()` で import と呼び出しを変更:

```python
# Before
from app.coord_search import search_by_proximity_multi
proximity_results = search_by_proximity_multi(ocr_entries, coords, threshold=...)
for field_name, match in proximity_results.items():
    if match and match.get("text") and field_name in extracted:
        extracted[field_name] = match["text"]

# After
from app.coord_search import search_fields_by_proximity
proximity_texts = search_fields_by_proximity(ocr_entries, coords, threshold=...)
for field_name, concat_text in proximity_texts.items():
    if concat_text and field_name in extracted:
        extracted[field_name] = concat_text
```

戻り値の型が変わった（`Dict[str, Optional[Dict]]` → `Dict[str, Optional[str]]`）ため、アクセス方法も `.get("text")` から直接テキスト値に変わる。

### Step 3: Forward方向（修正→テンプレート学習）の対応

`ocr_coordinate_service.py::process_feedback()` でテキスト検索が `None` を返した場合のフォールバック:

```python
# テキスト検索
coord_results: Dict[str, Any] = {}
for field_name, query in field_queries.items():
    coord_results[field_name] = search_coordinates(ocr_entries, query)

# フォールバック: サブストリングライン検出
for field_name, query in field_queries.items():
    if coord_results[field_name] is None:
        multi_boxes = self._find_multi_boxes_by_substring(ocr_entries, query)
        if multi_boxes is not None:
            coord_results[field_name] = multi_boxes  # マルチboxとして保存
```

ヘルパー関数は `@staticmethod` としてクラスに追加:

```python
@staticmethod
def _find_multi_boxes_by_substring(
    ocr_entries: List[Dict[str, Any]],
    full_query: str,
    line_tolerance: float = 20.0,
    similarity_threshold: float = 0.7,
) -> Optional[List[List[List[int]]]]:
    """
    サブストリング関係にあるOCRエントリをライン検出で収集し、
    連結テキストがfull_queryと類似すればマルチボックスリストを返す。
    """
    from collections import defaultdict
    import difflib

    if not ocr_entries or not full_query:
        return None

    # Step 1: Y中心でライン分割
    lines: Dict[float, List[dict]] = defaultdict(list)
    for entry in ocr_entries:
        box = entry.get("box")
        if not box or len(box) < 4:
            continue
        cy = (box[0][1] + box[2][1]) / 2.0
        assigned = False
        for key in sorted(lines.keys()):
            if abs(cy - key) <= line_tolerance:
                lines[key].append(entry)
                assigned = True
                break
        if not assigned:
            lines[cy].append(entry)

    # Step 2: 各ラインでサブストリングマッチ（相互: full_query in clean or clean in full_query）
    best_candidates: List[dict] = []
    best_similarity: float = 0.0
    for line_entries in lines.values():
        candidates = []
        for entry in line_entries:
            text = entry.get("text", "")
            if not text:
                continue
            clean_text = text.replace("様", "").strip()
            if full_query in clean_text or clean_text in full_query:
                candidates.append(entry)
        if not candidates:
            continue
        candidates.sort(key=lambda e: e["box"][0][0] if e.get("box") else 0)
        concat_text = "".join(
            c.get("text", "").replace("様", "").strip() for c in candidates
        )
        similarity = difflib.SequenceMatcher(None, concat_text, full_query).ratio()
        if similarity > best_similarity and similarity >= similarity_threshold:
            best_similarity = similarity
            best_candidates = candidates

    if not best_candidates:
        return None
    return [c["box"] for c in best_candidates]
```

### Step 4: 型ヒント更新

`template_feedback.py::process_correction_feedback()` の `field_coords_map` 引数型を更新:

```python
field_coords_map: Dict[str, Optional[List[List[int]] | List[List[List[int]]]]]
```

docstring にマルチbox形式の説明を追加:
```
        field_coords_map: Mapping of field names to box coordinates.
            - None: coordinate not found for this field.
            - List[List[int]]: single 4-point polygon (backward compatible).
            - List[List[List[int]]]: multi-box for split fields (e.g., split name).
```

## テスト戦略

### 既存テストの回帰防止

全タスク完了後、`pytest -q` で既存テストが変更前と同じ結果であることを確認する。変更前から失敗しているテスト（例: `test_feedback.py` 2件 + `test_web.py` 2件）は回帰とはみなさない。

### 新規テストケース（14件）

| ファイル | テスト数 | 内容 |
|---|---|---|
| `tests/test_coord_search.py` | 7 | `_is_multi_box` (3種) + `search_fields_by_proximity` (単一/マルチ/様除去/閾値) |
| `tests/test_structural_parser.py` | 3 | Reverse方向: マルチbox適用/単一box継続/テンプレートなし |
| `tests/test_coordinate_service.py` | 4 | Forward方向: フォールバック成功/不要/類似度不足/別ラインreject |

### テスト実装の注意点

**クリニックフィクスチャ**: `process_input_json` をテストする際、クリニックIDの取得には必ず `get_or_create_clinic()` を使うこと。

```python
# ❌ 間違い: 手動UUID + upsert_clinic
clinic_id = str(uuid.uuid4())
upsert_clinic(db, clinic_id, "クリニック名")
# → process_input_json 内の get_or_create_clinic() が別のIDを返す

# ✅ 正しい: get_or_create_clinic を使う
from app.db import get_or_create_clinic
clinic_id = get_or_create_clinic(db, "クリニック名")
```

これが重要な理由: `_apply_template_corrections()` は内部で `get_or_create_clinic(抽出されたクリニック名)` を呼び出してクリニックIDを解決する。フィクスチャ側で手動UUIDを使うと、テンプレートが別のクリニックIDに紐づき、テンプレートの適用に失敗する。

## 注意点

### 結合矩形（merged box）は非推奨
- 分割boxの単純な外接矩形を `coords_corrections` に格納する方式では、Reverse方向の近接検索（20px閾値）が機能しない
- 例: "山田" (中心X≈136) と "太郎" (中心X≈317) の結合矩形中心X≈226 は両方から約90px離れており、20px閾値を超過
- **常にマルチbox形式を採用し、各box個別に近接検索する**

### 後方互換性
- 既存の単一boxデータは変更不要。`_is_multi_box()` が False を返すため従来の `search_by_proximity()` が使用される
- DBスキーマ変更不要（`coords_corrections` は TEXT/JSON のまま）
- `search_by_proximity_multi()` は削除せず残す（`ocr_coordinate_service.py` の Bug B 近接検索パスで使用中）

### エッジケース
- 3つ以上に分割された場合もサブストリングマッチが全収集する
- "様" は連結後の `rstrip("様")` で除去（box個別ではなく連結後の1回のみ）
- テンプレート未学習の初回修正時は単一boxで保存され、次回修正でマルチ学習される
- 水平ギャップが大きい（極端に離れた）boxは同一ラインでも無関係として扱う — サブストリングマッチにより自動除外
- `search_coordinates` 内部で `normalize_text()` が呼ばれるため、クエリ文字列もNFKC正規化される（"山田太郎" の半角/全角の違いは吸収される）

### `search_by_proximity_multi` の残存用途
`ocr_coordinate_service.py` の `process_feedback()` 内で Bug B（既存テンプレートフィールドの保持）のために近接検索が実行される。このパスでは `search_by_proximity_multi` が引き続き使用されている。この関数はマルチボックス非対応だが、ここでの目的は「テンプレートに既に保存されているフィールドの座標を近接検索で維持する」ことであり、マルチボックスは既に Forward 方向で単一boxとしても保存されているため問題ない。