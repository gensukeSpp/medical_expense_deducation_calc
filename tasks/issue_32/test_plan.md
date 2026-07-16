# Issue #32: テスト計画

## テスト戦略

- **フレームワーク**: pytest
- **新規テストファイル**: `tests/test_coord_normalizer.py` — 座標相対化の単体テスト
- **既存テスト拡張**: `tests/test_web.py` — low_confidence 結合テスト追加
- **テストデータ**: サンプル raw_data を模した OCR エントリリストを使用

## テストケース一覧

### Task 1: `tests/test_coord_normalizer.py` — 座標相対化

#### TC-01: 正常な座標相対化

| 項目 | 内容 |
|------|------|
| テスト名 | `test_normalize_coordinates_basic` |
| 概要 | 複数の OCR エントリがある場合、最上部(y最小)と最左部(x最小)が(0,0)になる |
| 準備 | 3つの OCR エントリ（confidence 0.9）を含む raw_data.json を tmp_path に作成 |
| 確認点 | 相対化後、全 box 座標から (min_x, min_y) が減算されていること |

#### TC-02: confidence < 0.8 でスキップ

| 項目 | 内容 |
|------|------|
| テスト名 | `test_normalize_coordinates_low_confidence` |
| 概要 | 最上部要素の confidence < 0.8 の場合、相対化がスキップされる |
| 準備 | 最上部要素の confidence が 0.5 の raw_data.json を作成 |
| 確認点 | 戻り値の `normalized=False`, `low_confidence=True`。ファイルが変更されていないこと |

#### TC-03: confidence = None でスキップ

| 項目 | 内容 |
|------|------|
| テスト名 | `test_normalize_coordinates_none_confidence` |
| 概要 | confidence が None の場合も low_confidence 扱いになる |
| 確認点 | 戻り値の `low_confidence=True` |

#### TC-04: 空リスト

| 項目 | 内容 |
|------|------|
| テスト名 | `test_normalize_coordinates_empty_list` |
| 概要 | OCR エントリが空リストの場合、エラーにならず正常終了 |
| 確認点 | 戻り値の `normalized=False` |

#### TC-05: 単一要素のみ

| 項目 | 内容 |
|------|------|
| テスト名 | `test_normalize_coordinates_single_entry` |
| 概要 | 1エントリのみの場合、min_x=min_y=0 で相対化（実質変化なし） |
| 確認点 | 戻り値の `normalized=True`, `offset_x=0`, `offset_y=0` |

#### TC-06: ファイル不存在

| 項目 | 内容 |
|------|------|
| テスト名 | `test_normalize_coordinates_file_not_found` |
| 概要 | 存在しないパスを渡すと FileNotFoundError |
| 確認点 | `FileNotFoundError` が送出されること |

#### TC-07: 不正な box 形式

| 項目 | 内容 |
|------|------|
| テスト名 | `test_normalize_coordinates_invalid_box` |
| 概要 | box が空リストや不正形式のエントリはスキップされる |
| 確認点 | 有効なエントリのみで相対化が行われること |

### Task 2: `tests/test_web.py` — 結合テスト

#### TC-08: 一覧ページに low_confidence 警告が表示される

| 項目 | 内容 |
|------|------|
| テスト名 | `test_index_shows_low_confidence_warning` |
| 概要 | structured_data に `low_confidence: true` がある場合、一覧ページに警告が表示される |
| 準備 | structured_data に `low_confidence: true` を含むファイルを作成 |
| 確認点 | HTML に「⚠ 読み取り不十分」が含まれること |

#### TC-09: low_confidence なしのレシートには警告が表示されない

| 項目 | 内容 |
|------|------|
| テスト名 | `test_index_no_warning_for_normal_receipt` |
| 概要 | low_confidence フラグがないレシートには警告が表示されない |
| 確認点 | HTML に「⚠ 読み取り不十分」が含まれないこと |

#### TC-10: low_confidence レシート修正でテンプレートが更新されない

| 項目 | 内容 |
|------|------|
| テスト名 | `test_correction_low_confidence_skips_template` |
| 概要 | low_confidence なレシートを修正しても templates テーブルが更新されない |
| 準備 | structured_data に `low_confidence: true` を含むファイル + raw_data + DB を準備 |
| 確認点 | 修正後、`templates` テーブルのレコード数が変化しないこと。`corrections` テーブルにはレコードが追加されること |

## エッジケース一覧

| ケース | 対応方針 |
|--------|---------|
| box 座標が 4点未満（3点等） | `_find_min_coords()` で `len(box) < 4` のエントリはスキップ |
| box 座標に負の値 | そのまま減算（負の値も許容） |
| 全エントリの confidence が None | `topmost_confidence=None` → `low_confidence=True` |
| 全エントリの box が不正 | `min_x=None` → `normalized=False` を返す |
| structured_data に既存の `low_confidence` キー | 上書き（既存値は無視） |
| パイプライン連鎖中に coord_normalizer が例外 | 例外をキャッチしログ記録、処理継続 |

## テスト実行方法

```bash
# 座標相対化の単体テスト
pytest tests/test_coord_normalizer.py -v

# Web UI 結合テスト
pytest tests/test_web.py -v

# 全テスト（既存テストとの互換性確認）
pytest tests/ -v

# フォーマット確認
black --check .
```