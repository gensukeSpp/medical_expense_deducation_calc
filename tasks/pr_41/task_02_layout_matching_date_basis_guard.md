# タスク 02: layout matching 経由での date-basis template 誤上書き防止

## 課題概要

[P1] layout matching経由ではIssue #40のdate-basisガードが適用されず、誤上書き可能

## 目的

layout matching経路において、date基準のtemplateがtopmost rawに誤って座標上書きしないようにする。clinic名のOCR誤り等でname matchingが失敗した場面でも、#40が防ぐべきdate/topmostの誤上書きが発生しないようにし、PR本文・仕様の「date基準では座標駆動処理をスキップ」を満たす。

## 計画

1. `app/db.py` の `get_all_templates_with_names()` 関数で `coord_basis` カラムを返すように修正
2. `app/structural_parser.py` の `_apply_template_corrections()` において、layout matching前にdate-basis templatesを除外するか、候補選定時と最終適用時の双方でcoord_basisガードを行う
3. layout経由でdate templateがフィールド補正へ渡らない回帰テストを追加

## タスク

- [ ] `app/db.py:get_all_templates_with_names()` のSELECTクエリに `t.coord_basis` を追加
- [ ] 戻り値dictに `coord_basis` キーが含まれることを確認
- [ ] `app/structural_parser.py:_apply_template_corrections()` のStep 3（layout matching）で、`get_all_templates_with_names()` から返されるtemplateリストをフィルタし、`coord_basis == "date"` のtemplateを除外
- [ ] または、`match_template_by_layout()` 呼び出し前にdate-basis templateを除外するフィルタロジックを追加
- [ ] 最終適用時にもcoord_basisガードを再確認（二重ガード防止）
- [ ] `app/coord_search.py:match_template_by_layout()` のテストにおいて、date-basis templateが選択されないことを検証するテスト追加
- [ ] テスト実行: `pytest tests/test_structural_parser.py tests/test_coord_search.py -v`

## 実装方針

```python
# app/db.py: get_all_templates_with_names() の修正
# 変更前:
# SELECT t.id, t.clinic_id, t.version, t.coords_corrections,
#        t.created_at, c.name as clinic_name
# FROM templates t ...
#
# 変更後:
# SELECT t.id, t.clinic_id, t.version, t.coords_corrections,
#        t.created_at, c.name as clinic_name, t.coord_basis
# FROM templates t ...

# app/structural_parser.py: _apply_template_corrections() Step 3 の修正
# 変更前:
# all_templates = get_all_templates_with_names(self.db_path)
# matched = match_template_by_layout(ocr_entries, all_templates, ...)
#
# 変更後:
# all_templates = get_all_templates_with_names(self.db_path)
# # date-basis template は layout matching から除外（topmost raw に照合できない）
# topmost_templates = [t for t in all_templates if (t.get("coord_basis") or "topmost") == "topmost"]
# matched = match_template_by_layout(ocr_entries, topmost_templates, ...)
```

## 影響範囲

- `app/db.py`: `get_all_templates_with_names()` 関数のSELECTクエリと戻り値
- `app/structural_parser.py`: `ExtractionService._apply_template_corrections()` のStep 3
- `app/coord_search.py`: `match_template_by_layout()` のテスト
- `tests/test_structural_parser.py`: layout matching関連テスト
- `tests/test_coord_search.py`: `match_template_by_layout()` テスト

## 検証方法

- clinic名のOCR誤り等でname matchingが失敗した場面でのlayout fallback動作を確認
- date-basis templateがlayout matchingで選択されないことを検証
- topmost-basis templateは正常にlayout matchingで選択されることを確認
- 既存テスト `tests/test_structural_parser.py` 全テストパス確認
