# タスク 05: black チェック修正

## 課題概要

改善提案: 新設した `tests/test_coord_normalizer.py` は black `--check` で既存周辺行の整形差分が検出された

## 目的

`tests/test_coord_normalizer.py` において、black `--check` が成功するようにファイルを整形する。diff上、追加箇所だけでなく既存テスト行の整形も出るため、既存差分と今回追加行を区別して整形確認する。

## 計画

1. `tests/test_coord_normalizer.py` に対して `black --check --target-version py311` を実行し、変更不要ファイルを特定
2. 必要に応じて `black` 実行でファイルを整形
3. テスト実行: `black --check --target-version py311 tests/test_coord_normalizer.py` が成功することを確認

## タスク

- [ ] `black --check --target-version py311 tests/test_coord_normalizer.py` を実行し、整形差分を確認
- [ ] 差分が `tests/test_coord_normalizer.py` のみであることを確認
- [ ] 必要に応じて `black tests/test_coord_normalizer.py` を実行してファイルを整形
- [ ] `black --check --target-version py311 tests/test_coord_normalizer.py` が成功することを確認
- [ ] テスト実行: `pytest tests/test_coord_normalizer.py -v` が既存通り成功することを確認

## 実装方針

```bash
# 現在の状態確認
uv run --python 3.11 black --check --target-version py311 tests/test_coord_normalizer.py

# 整形実行（必要に応じて）
uv run --python 3.11 black --target-version py311 tests/test_coord_normalizer.py

# 再確認
uv run --python 3.11 black --check --target-version py311 tests/test_coord_normalizer.py
```

## 影響範囲

- `tests/test_coord_normalizer.py`: black整形

## 検証方法

- `black --check --target-version py311 tests/test_coord_normalizer.py` が成功することを確認
- `pytest tests/test_coord_normalizer.py -v` が既存通り成功することを確認
