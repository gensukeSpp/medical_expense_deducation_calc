# Tasks: 分割氏名の自動マルチボックス対応

## 重要: テスト回帰の遵守

**全タスクで以下のルールを厳守すること**:

1. 各タスク完了後、必ず `pytest -q` を実行し既存テストが通ることを確認する
2. 失敗があった場合は、**自分の変更が原因か** を確認するため `git stash` で退避して同一テストを実行する
3. 変更前から存在する失敗（現在: `tests/test_feedback.py` の2件 + `tests/test_web.py` の2件）は回帰とはみなさない
4. 既存のテストケース数を維持すること（78 passed が基準）

---

## Task 1: `coord_search.py` にマルチボックス検索ユーティリティ追加

**ファイル**: `app/coord_search.py`

**内容**:

以下の2関数を末尾に追加:

### 1-a. `_is_multi_box(value: Any) -> bool`

- `isinstance(value[0][0], list)` で判定
- `coord_search.py` と `structural_parser.py` の両方から利用されるため、ここで定義

### 1-b. `search_fields_by_proximity(ocr_entries, field_box_map, threshold=20.0) -> Dict[str, Optional[str]]`

- 既存の `search_by_proximity_multi()` と似ているが以下が異なる:
- `field_box_map` の各値が単一box or マルチbox を自動判定
- マルチboxの場合: 各boxに `search_by_proximity()` をループ実行
- 全ヒットのテキストをX座標順に連結
- 連結テキストから "様" サフィックスを除去（`rstrip("様")`）
- 戻り値は `Dict[str, Optional[str]]`（field_name → 連結テキスト or None）

**注意**:
- `search_by_proximity_multi()` は維持（後方互換のため削除しない）
- 単一boxの場合は `search_by_proximity_multi()` と同じ結果になること（戻り値型は異なる）
- `_calculate_box_center()` と `search_by_proximity()` は既存のものを利用

**確認**: `pytest -q` で 78 passed（既存の4 failures は許容）

---

## Task 2: `structural_parser.py` で Reverse方向 マルチボックス対応

**ファイル**: `app/structural_parser.py`

**内容**:

`_apply_template_corrections()` 内の近接検索呼び出しを変更:

```python
# 変更前
from app.coord_search import search_by_proximity_multi

proximity_results = search_by_proximity_multi(ocr_entries, coords, threshold=...)
for field_name, match in proximity_results.items():
    if match and match.get("text") and field_name in extracted:
        extracted[field_name] = match["text"]
```

```python
# 変更後
from app.coord_search import search_fields_by_proximity

proximity_texts = search_fields_by_proximity(ocr_entries, coords, threshold=...)
for field_name, concat_text in proximity_texts.items():
    if concat_text and field_name in extracted:
        extracted[field_name] = concat_text
```

**注意**:
- `search_by_proximity_multi` の import を `search_fields_by_proximity` に置き換え
- `DEFAULT_PROXIMITY_THRESHOLD` の値は変更なし
- 単一boxテンプレートの場合も `search_fields_by_proximity` が同じ結果を返すこと
- 戻り値の型が `Dict[str, Optional[Dict]]` から `Dict[str, Optional[str]]` に変わることに注意

**確認**: `pytest -q` で 78 passed

---

## Task 3: `ocr_coordinate_service.py` で Forward方向 サブストリングフォールバック追加

**ファイル**: `app/services/ocr_coordinate_service.py`

**内容**:

`process_feedback()` のテキスト検索セクションにフォールバックを追加:

```python
# テキスト検索が None を返した場合のフォールバック
for field_name, query in field_queries.items():
    coord_results[field_name] = search_coordinates(ocr_entries, query)

    # フォールバック: サブストリングライン検出
    if coord_results[field_name] is None:
        multi_boxes = _find_multi_boxes_by_substring(ocr_entries, query)
        if multi_boxes is not None:
            coord_results[field_name] = multi_boxes  # マルチboxとして保存
```

新規ヘルパー関数 `_find_multi_boxes_by_substring()`:

```python
def _find_multi_boxes_by_substring(
    ocr_entries: List[dict],
    full_query: str,
    line_tolerance: float = 20.0,
    similarity_threshold: float = 0.7,
) -> Optional[List[List[List[int]]]]:
    """
    サブストリング関係にあるOCRエントリをライン検出+水平近接で収集し、
    連結テキストがfull_queryと類似すればマルチボックスリストを返す。
    """
    # Step 1: Y中心でライン分割
    from collections import defaultdict
    lines: Dict[int, List[dict]] = defaultdict(list)
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

    # Step 2: 各ラインでサブストリングマッチ
    best_candidates = []
    best_similarity = 0.0
    for line_y, entries in lines.items():
        candidates = []
        for entry in entries:
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
        import difflib
        similarity = difflib.SequenceMatcher(None, concat_text, full_query).ratio()
        if similarity > best_similarity and similarity >= similarity_threshold:
            best_similarity = similarity
            best_candidates = candidates

    if not best_candidates:
        return None

    # Step 3: マルチボックスリスト構築
    boxes = [c["box"] for c in best_candidates]
    return boxes
```

**注意**:
- ヘルパー関数は `OCRCoordinateService` のクラスメソッドとして追加するか、モジュールレベル関数として配置する（クラスメソッド推奨）
- テキスト検索が成功した場合はフォールバック不要
- 連結テキストとfull_queryの類似度が0.7未満の場合はフォールバックを採用しない

**確認**: `pytest -q` で 78 passed

---

## Task 4: `template_feedback.py` でマルチボックス保存対応（型ヒントのみ）

**ファイル**: `app/template_feedback.py`

**内容**:

`process_correction_feedback()` の引数型ヒントとdocstringを更新:

```python
def process_correction_feedback(
    db_path: str | Path,
    clinic_id: str,
    field_coords_map: Dict[str, Optional[List[List[int]] | List[List[List[int]]]]],
    receipt_id: str | None = None,
) -> Dict[str, Any]:
```

docstring に以下を追加:
```
        field_coords_map: Mapping of field names to box coordinates.
            - None: coordinate not found for this field
            - List[List[int]]: single 4-point polygon (backward compatible)
            - List[List[List[int]]]: multi-box for split fields (e.g., split name)
```

**注意**: 実動作に変更はない。型ヒントとdocstringの更新のみ。

**確認**: `pytest -q` で 78 passed

---

## タスク実行順序

```
Task 1: coord_search.py にユーティリティ追加
    ↓
pytest -q 確認（78 passed）
    ↓
Task 2: structural_parser.py で Reverse 方向対応
    ↓
pytest -q 確認（78 passed）
    ↓
Task 3: ocr_coordinate_service.py で Forward 方向対応
    ↓
pytest -q 確認（78 passed）
    ↓
Task 4: template_feedback.py の docstring更新
    ↓
pytest -q 確認（78 passed）
    ↓
テスト追加（test_plan.md 参照）
```