"""Run end-to-end processing for all OCR sample files and store structured outputs in tasks/issue_4/results."""

from __future__ import annotations
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.structural_parser import process_input_json

BASE = Path(__file__).resolve().parents[0]
SAMPLES = BASE.glob("ocr_sample_*.json")
RESULTS = BASE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


def main():
    for s in SAMPLES:
        out = process_input_json(s, model="mock", output_dir=RESULTS)
        if out is None:
            print(f"Failed: {s}")
        else:
            print(f"Processed {s} -> {RESULTS / (s.stem + '-structured_data.json')}")


if __name__ == "__main__":
    main()
