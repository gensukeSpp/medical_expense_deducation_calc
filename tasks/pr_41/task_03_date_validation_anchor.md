# タスク 03: date anchor 採用時の暦妥当性検証

## 課題概要

[P2] `parse_date()`は暦として無効な値も日付として採用する

## 目的

date anchor採用時に、暦として無効な日付（例: 2026-99-99）がanchorとして使用されないようにする。`datetime.date.fromisoformat()`等で実日付として検証し、不正な日付の場合は従来方式（topmost正規化）にfallbackするようにする。これにより、Issue #39の「信頼できる候補のみanchor」の前提を保ち、座標データを誤移行しないようにする。

## 計画

1. `app/date_anchor.py` の `find_date_candidates()` 関数において、`parse_date()` の戻り値を `datetime.date.fromisoformat()` で検証
2. 無効な日付の場合は候補から除外し、従来方式にfallback
3. テスト追加: 無効な日付（2026-99-99、うるう日、月日境界）の場合にanchorが採用されないことを検証

## タスク

- [ ] `app/date_anchor.py:find_date_candidates()` 関数で、`parse_date()` の戻り値を `datetime.date.fromisoformat()` で検証するロジックを追加
- [ ] 無効な日付の場合は候補リストから除外
- [ ] テスト追加: 無効な日付（2026-99-99）の場合にanchorが採用されないことを検証
- [ ] テスト追加: うるう日（2024-02-29 は有効、2023-02-29 は無効）の検証
- [ ] テスト追加: 月日境界（2026-13-01、2026-00-15、2026-01-00、2026-01-32）の検証
- [ ] テスト実行: `pytest tests/test_date_anchor.py -v`

## 実装方針

```python
# app/date_anchor.py: find_date_candidates() の修正
from datetime import date

def find_date_candidates(
    ocr_entries: List[Dict[str, Any]],
    structured_date: str,
) -> List[Dict[str, Any]]:
    if not structured_date:
        return []
    target = parse_date(structured_date)
    if target is None:
        return []

    # 暦妥当性検証を追加
    try:
        date.fromisoformat(target)  # 無効な日付なら ValueError
    except ValueError:
        return []  # 無効な日付 → 候補なし（従来方式にfallback）

    candidates = []
    for entry in ocr_entries:
        if not isinstance(entry, dict):
            continue
        text = entry.get("text")
        box = entry.get("box")
        if not text or not box:
            continue
        parsed = parse_date(text)
        if parsed is None:
            continue
        # 暦妥当性検証
        try:
            date.fromisoformat(parsed)
        except ValueError:
            continue  # 無効な日付 → 候補から除外
        if parsed == target:
            candidates.append(entry)
    return candidates
```

## 影響範囲

- `app/date_anchor.py`: `find_date_candidates()` 関数
- `tests/test_date_anchor.py`: 日付検証テスト追加

## 検証方法

- 無効な日付（2026-99-99）の場合にanchorが採用されないことを検証
- うるう日（2024-02-29 は有効、2023-02-29 は無効）の検証
- 月日境界（2026-13-01、2026-00-15等）の検証
- 有効な日付（2026-01-15等）が正常にanchorとして採用されることを確認
- 既存テスト `tests/test_date_anchor.py` 全テストパス確認
