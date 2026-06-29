# 2026-06-29-architecture.md

## Purpose
Issue #24 に基づき、OCR画像投入から構造化データ抽出、およびクリニックテンプレートを用いた座標近接検索による抽出補正機能を実装した。

## Overview
- **Pipeline Integration**: 画像投入、OCR処理（PaddleOCR）、構造化データ抽出（MockLLMClient）、DB保存をパイプライン化した。
- **Template-Based Extraction**: クリニックごとの座標テンプレート（`coords_corrections`）を利用し、OCR結果の座標とテンプレート座標が近い（しきい値 20px以内）場合に、抽出値をテンプレート値で上書きする機能を導入。

## Key Components Changed
- `app/watcher.py`: 処理パイプラインの拡張。
- `app/processor.py`: 単一画像処理フローの拡張。
- `app/structural_parser.py`: テンプレート連携ロジックの実装。
- `app/coord_search.py`: 座標近接検索関数（`search_by_proximity` 等）の実装。

## Dataflow
1. `process_image` (OCR) → `raw_data.json`
2. `process_input_json` (抽出)
3. (DB接続時) クリニック名よりテンプレートを取得
4. テンプレートの座標情報とOCR結果を `search_by_proximity_multi` で比較
5. 近接マッチした値を抽出値で上書きし、`structured_data.json` を保存。

## Key Design Decisions
- テンプレート連携は `MockLLMClient` 使用時のみ有効とし、`RealLLMClient` 利用時は LLM の判断を優先する。
- テンプレートのマッチングしきい値を `20.0px` と固定設定。

## Next Steps
- テンプレート座標の自動調整機能の検討。
- RealLLMClient 実装時のテンプレート活用方法の設計。

## Changed Files
- `app/coord_search.py`
- `app/structural_parser.py`
- `app/watcher.py`
- `app/processor.py`
- `main.py`
- `tests/test_coord_search.py`
- `tests/test_structural_parser.py` (New)
- `tests/test_watcher_integration.py`
