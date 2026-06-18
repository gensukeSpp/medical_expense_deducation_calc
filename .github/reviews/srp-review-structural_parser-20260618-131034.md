# SRPレビュー: app/structural_parser.py

レビュー日: 2026-06-18 13:10:34
対象: app/structural_parser.py (単一トップレベル関数: process_input_json)

## 1) 責務の特定
process_input_json が担っている責務（変更理由ごとに列挙）
- 入力読み込み: ファイルパスから OCR JSON を読み込む（I/O）
- LLM 呼び出しの選択と実行: モデル選択（mock/real）と extract_fields の実行
- 正規化処理: amount/date の解析と補完ロジック
- エラー記録: append_error を使って各種ステップのエラーをログに残す
- 出力書き出し: structured JSON を output_dir に保存する

これらはそれぞれ別個の変更理由（例: I/O エラー処理の変更、LLM の差し替え、正規化ロジックの拡張、ログのフォーマット変更、出力先の変更）を持つため、単一責務ではありません。

## 2) SRP違反の指摘（箇所: 関数名・行範囲）
- process_input_json (ファイル全体、約行 1–85)
  - 入力読み込み: try/except around json.load (行 13–18相当)
  - LLM 呼び出し: client 選択と extract_fields 呼び出し (行 20–30相当)
  - 正規化: amount/date の補完ロジック一式 (行 32–66相当)
  - 出力書込: JSON dump とファイル書き込み (行 68–79相当)
  - 例外ハンドリング/ログ: 各ブロックで append_error を直接呼ぶ（散在）

これにより、以下のような変更が同一関数内で混在します:
- 仕様変更: "出力フォーマットを変える" と "LLM クライアントを入れ替える" の両方が同じ関数を変える必要がある。

## 3) 改善案（最小リファクタ例）
方針: 各責務を小さな関数またはクラスに分割し、依存注入（LLM クライアント、エラーロガー、正規化器）を行う。

1) ヘルパ関数抽出（入出力）
```py
from pathlib import Path
import json

def read_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
```

2) LLM 呼び出しを分離（ファクトリ）
```py
def get_llm_client(model_name: str):
    if model_name == 'mock':
        return MockLLMClient()
    return RealLLMClient(model_name)
```

3) 正規化ロジックを関数化
```py
def normalize_extracted(extracted, ocr_json):
    amount = extracted.get('amount')
    if isinstance(amount, str):
        amount = parse_amount(amount)
    # ... date 正規化など
    return {**extracted, 'amount': amount, 'date': date}
```

4) 最終的な process_input_json を薄くする
```py
def process_input_json(input_path, model='mock', output_dir='output_json'):
    try:
        ocr = read_json(input_path)
    except Exception as e:
        logger.append(...)
        return None
    client = get_llm_client(model)
    extracted = client.extract_fields(ocr)
    structured = normalize_extracted(extracted, ocr)
    write_json(Path(output_dir)/f"{Path(input_path).stem}-structured_data.json", structured)
    return structured
```

5) オブジェクト化（より推奨）
```py
class StructuralParser:
    def __init__(self, client, normalizer, error_logger):
        self.client = client
        self.normalizer = normalizer
        self.logger = error_logger
    def process(self, input_path, output_dir):
        ocr = read_json(input_path)
        extracted = self.client.extract_fields(ocr)
        structured = self.normalizer(extracted, ocr)
        write_json(...)
        return structured
```
利点: テスト容易性が向上（モック注入）、責務分離、可読性向上。

---
結論: 現行の process_input_json は SRP に違反しています。小さな関数と依存注入に分割するリファクタを推奨します。上のコード片は最小の変更で移行可能です。
