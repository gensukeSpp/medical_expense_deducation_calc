import sys
from pathlib import Path
import json

# ensure project root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.structural_parser import process_input_json

BASE = Path("tasks/issue_4")
SAMPLES = [
    ("ocr_sample_normal.json", "expected/expected_normal.json"),
    ("ocr_sample_missing_labels.json", "expected/expected_missing_labels.json"),
    ("ocr_sample_noisy.json", "expected/expected_noisy.json"),
]


def test_e2e_samples(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    for s, expected in SAMPLES:
        sample_path = BASE / s
        out = process_input_json(sample_path, model="mock", output_dir=results_dir)
        assert out is not None
        # load expected
        exp = json.load(open(BASE / expected, "r", encoding="utf-8"))

        # Basic assertions: keys equal and amount/date normalized
        def norm(s):
            if s is None:
                return None
            return " ".join(str(s).replace("\u3000", " ").split())

        assert norm(out["clinic"]) == norm(exp["clinic"])
        assert out["amount"] == exp["amount"]
        assert out["date"] == exp["date"]
