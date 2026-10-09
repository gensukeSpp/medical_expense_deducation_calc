# タスク 01: 初回 anchor の offset 座標系修正

## 課題概要

[P1] 初回anchorのoffsetがtopmost正規化後の座標から計算され、template座標変換が誤る

## 目的

初回date anchor移行時に、template座標を正しいdate基準へ変換し、anchor boxが(0,0)に揃うようにする。これにより、移行後のtemplate feedback・近傍検索・座標マッチングが継続して正しく動作し、Issue #39の受入条件#39-4（移行後も近傍検索継続）を満たす。

## 計画

1. `app/date_anchor.py` の `apply_date_anchor_normalization()` 関数におけるtemplate座標変換ロジックを修正
2. 現在、topmost正規化済みの座標系から計算されたoffsetでtemplateをシフトしているのを、元の絶対座標系に対するdate anchor offsetへ修正
3. integration testを追加: date-templateの基準点が必ず(0,0)になるテスト（anchor位置がtopmost原点と一致しない値で検証）

## タスク

- [ ] `app/date_anchor.py:191-203` の実装を再調査し、offset計算の根本原因を特定
- [ ] templateがtopmost基準の場合、rawと同じtopmost原点で引き算するため、offset差分（rawでanchorが持つtopmost座標）を正しく座標変換へ適用するよう修正
- [ ] `shift_template_coords()` の呼び出し箇所において、offsetパラメータが絶対座標系に基づく値になるよう修正
- [ ] integration test追加: anchor位置がtopmost原点と一致しない値（例: date位置(80,120)、template位置(50,100)）で、移行後date box左上が(0,0)になることを検証
- [ ] テスト実行: `pytest tests/test_date_anchor.py -v`

## 実装方針

```python
# 現在（誤り）:
# offset_x, offset_y は topmost 座標系での date 位置
# topmost 正規化済み raw の anchor box は既に topmost offset が差し引かれている
# この offset で template をシフトすると、座標系不一致で誤った位置になる

# 修正後:
# template が topmost 基準の場合、元の絶対座標系に対する offset を計算
# offset = (anchor_box絶対x - template_date_box絶対x, anchor_box絶対y - template_date_box絶対y)
# または、topmost offset 差分を正しく適用

# 具体的には:
# 1. raw_path の OCR entries から anchor box の絶対座標を復元（必要なら）
# 2. template_date_box の絶対座標と比較して正しい offset を計算
# 3. shift_template_coords() に正しい offset を渡す
```

## 影響範囲

- `app/date_anchor.py`: `apply_date_anchor_normalization()` 関数
- `tests/test_date_anchor.py`: integration test追加

## 検証方法

- 実データ同等の入力で検証: anchor raw左上が(0,0)、template date左上が(0,0)になることを確認
- 既存テスト `tests/test_date_anchor.py` 全テストパス確認
- integration testでanchor位置がtopmost原点と一致しないケースを追加検証
