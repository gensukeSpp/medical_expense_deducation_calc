"""Trace which coordinate-resolution path OCRCoordinateService.process_feedback
uses for each field of IMG_20260929_104148_1790614680.

Runs against a COPY of verify-03.db so the real DB is not mutated.
Every search-strategy call and proximity fallback is logged.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ocr_coordinate_service import OCRCoordinateService

OUT_LOG = Path("logs/process_feedback_coords_trace.log")
IMAGE = "IMG_20260929_104148_1790614680"
DB_COPY = "/tmp/verify-03-demo.db"
OUTPUT_DIR = Path("output_json")


class LoggingTextStrategy:
    """Wraps TextSearchStrategy; logs each draw call."""

    def __init__(self, inner, log):
        self.inner = inner
        self.log = log

    def search(self, ocr_entries, query):
        box = self.inner.search(ocr_entries, query)
        if box is not None:
            print(f"  [TEXT] text-similarity HIT query={query!r} -> box={box}", file=self.log)
        else:
            print(f"  [TEXT] text-similarity MISS query={query!r}", file=self.log)
        return box


class LoggingMultiBoxStrategy:
    def __init__(self, inner, log):
        self.inner = inner
        self.log = log

    def search(self, ocr_entries, query):
        boxes = self.inner.search(ocr_entries, query)
        if boxes is not None:
            print(f"  [MULTI] multi-box HIT query={query!r} -> boxes={boxes}", file=self.log)
        else:
            print(f"  [MULTI] multi-box MISS query={query!r}", file=self.log)
        return boxes


def get_receipt_clinic_id(db_path: str, receipt_id: str):
    con = sqlite3.connect(db_path)
    row = con.execute("SELECT clinic_id FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
    con.close()
    return row[0] if row else None


def main() -> None:
    OUT_LOG.parent.mkdir(exist_ok=True)
    log = OUT_LOG.open("w", encoding="utf-8")
    print("=== process_feedback coordinate resolution trace ===", file=log)

    # The actual final correction saved for this receipt (2026-10-02 05:48).
    updates = {
        "name": "相原　学",
        "clinic": "なの花薬局札幌二十四軒店",
        "amount": 1450,
        "date": "2026-08-05",
    }

    strategies_mod = __import__(
        "app.services.ocr_search_strategies", fromlist=["TextSearchStrategy", "MultiBoxSubstringStrategy"]
    )
    strategies = [
        LoggingTextStrategy(strategies_mod.TextSearchStrategy(), log),
        LoggingMultiBoxStrategy(strategies_mod.MultiBoxSubstringStrategy(), log),
    ]

    service = OCRCoordinateService(
        repository=None,
        search_strategies=strategies,
        output_dir=OUTPUT_DIR,
        db_path=Path(DB_COPY),
    )

    # Intercept search_by_proximity_multi to log the center-distance fallback.
    import app.coord_search as coord_search
    import app.services.ocr_coordinate_service as coord_svc

    _orig_prox = coord_search.search_by_proximity_multi

    def _log_prox(ocr_entries, field_box_map, threshold=20.0):
        print(f"  [PROXIMITY] center-distance search threshold={threshold}", file=log)
        res = _orig_prox(ocr_entries, field_box_map, threshold)
        for fname, match in res.items():
            if match and match.get("box"):
                print(
                    f"  [PROXIMITY] {fname}: center-distance HIT box={match['box']} text={match.get('text')!r}",
                    file=log,
                )
            else:
                print(f"  [PROXIMITY] {fname}: center-distance MISS", file=log)
        return res

    coord_search.search_by_proximity_multi = _log_prox
    # _resolve_coord_results imports it locally via module attr, so patch at module level:
    coord_svc.search_by_proximity_multi = _log_prox


    file_path = OUTPUT_DIR / f"{IMAGE}-structured_data.json"
    old_data = json.loads(file_path.read_text(encoding="utf-8"))

    clinic_id = get_receipt_clinic_id(DB_COPY, IMAGE)
    template = service.repository.get_latest_template_by_clinic(clinic_id)
    print(f"receipt_clinic_id={clinic_id}", file=log)
    print(f"template coords_corrections={json.dumps(template['coords_corrections'], ensure_ascii=False)}", file=log)
    print(f"updates (->field_queries)= {updates}", file=log)
    print(f"low_confidence in old_data={old_data.get('low_confidence', False)}", file=log)
    print(f"--- calling process_feedback (search strategies first, then proximity) ---", file=log)

    result = service.process_feedback(
        file_stem=IMAGE,
        file_path=file_path,
        old_data=old_data,
        updates=updates,
        receipt_id=IMAGE,
        clinic_id=clinic_id,
    )
    print(f"\nCOORD_RESULTS final -> {json.dumps(result, ensure_ascii=False, indent=2)}", file=log)
    log.close()
    print("done ->", OUT_LOG.resolve())


if __name__ == "__main__":
    main()
