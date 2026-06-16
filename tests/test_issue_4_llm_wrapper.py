import sys
from pathlib import Path
# Ensure project root is on sys.path for tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm_extractor import MockLLMClient
import json


def load_sample(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_mock_extractor_normal():
    client = MockLLMClient()
    ocr = load_sample('tasks/issue_4/ocr_sample_normal.json')
    out = client.extract_fields(ocr)
    assert out['clinic'] is not None
    assert out['name'] in ('山田 太郎', '山田 太郎 ' , '山田 太郎')
    assert out['amount'] == 3800
    assert out['date'] == '2026-01-15'


def test_mock_extractor_missing_labels():
    client = MockLLMClient()
    ocr = load_sample('tasks/issue_4/ocr_sample_missing_labels.json')
    out = client.extract_fields(ocr)
    assert out['clinic'] == '青葉薬局'
    assert out['amount'] == 4200
    assert out['date'] == '2026-01-10'


def test_mock_extractor_noisy():
    client = MockLLMClient()
    ocr = load_sample('tasks/issue_4/ocr_sample_noisy.json')
    out = client.extract_fields(ocr)
    assert out['amount'] == 12000
    assert out['name'] in ('山田太郎','山田 太郎', '山田太郎')
