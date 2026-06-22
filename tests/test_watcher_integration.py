import cv2
import numpy as np
from pathlib import Path
import threading
import time
import json

from app.watcher import scan_and_process


class FakeOCR:
    def predict(self, img):
        # Return a simple list-shaped result matching pipeline expectations
        box = [[0, 0], [10, 0], [10, 10], [0, 10]]
        return [[[box, ["TEST_TEXT", 0.95]]]]


def test_scan_and_process_run_once(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    processed_dir = tmp_path / "processed"
    failed_dir = tmp_path / "failed"

    input_dir.mkdir()

    # create a small dummy image
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img_path = input_dir / "test.jpg"
    assert cv2.imwrite(str(img_path), img)

    ocr = FakeOCR()

    processed_count = scan_and_process(
        input_dir=input_dir,
        ocr=ocr,
        output_dir=output_dir,
        processed_dir=processed_dir,
        failed_dir=failed_dir,
        max_files=None,
        retries=0,
    )

    assert processed_count == 1

    # one JSON should be created
    outputs = list(output_dir.glob("*_raw_data.json")) + list(output_dir.glob("*.json"))
    assert len(outputs) == 1

    # original moved to processed
    assert (processed_dir / "test.jpg").exists()
    assert not (failed_dir / "test.jpg").exists()


def test_process_skips_file_still_writing(tmp_path):
    """Create a file that is being written while scan runs. First scan should skip, second should process."""
    input_dir = tmp_path / "input2"
    output_dir = tmp_path / "output2"
    processed_dir = tmp_path / "processed2"
    failed_dir = tmp_path / "failed2"

    input_dir.mkdir()

    img_path = input_dir / "inprogress.jpg"

    # write initial content
    with open(img_path, "wb") as f:
        f.write(b"0" * 1024)

    # background writer that appends data for ~2 seconds
    def writer(path: Path):
        for _ in range(6):
            time.sleep(0.3)
            with open(path, "ab") as f:
                f.write(b"x" * 512)

    t = threading.Thread(target=writer, args=(img_path,), daemon=True)
    t.start()

    ocr = FakeOCR()

    # First scan attempts processing but should skip because file is unstable
    processed_count = scan_and_process(
        input_dir=input_dir,
        ocr=ocr,
        output_dir=output_dir,
        processed_dir=processed_dir,
        failed_dir=failed_dir,
        max_files=None,
        retries=0,
    )
    assert processed_count == 0
    assert img_path.exists()

    # Wait for writer to finish
    t.join()

    # Second scan should process the now-stable file
    processed_count2 = scan_and_process(
        input_dir=input_dir,
        ocr=ocr,
        output_dir=output_dir,
        processed_dir=processed_dir,
        failed_dir=failed_dir,
        max_files=None,
        retries=0,
    )
    assert processed_count2 == 1
    # output created
    outputs = list(output_dir.glob("*_raw_data.json")) + list(output_dir.glob("*.json"))
    assert len(outputs) == 1
    # moved to processed
    assert (processed_dir / "inprogress.jpg").exists()


def test_scan_and_process_skips_when_output_exists(tmp_path):
    """If output JSON already exists for the image (based on mtime naming), scanner should move image to processed without calling OCR."""
    input_dir = tmp_path / "input3"
    output_dir = tmp_path / "output3"
    processed_dir = tmp_path / "processed3"
    failed_dir = tmp_path / "failed3"

    input_dir.mkdir()

    # create image
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    img_path = input_dir / "already.jpg"
    assert cv2.imwrite(str(img_path), img)

    # compute expected output name based on mtime
    mtime = int(img_path.stat().st_mtime)
    out_fname = f"{img_path.stem}_{mtime}-raw_data.json"
    out_path = output_dir / out_fname
    output_dir.mkdir()

    # create a pre-existing JSON file to simulate prior processing
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([{"text": "PREV", "confidence": 1.0, "box": []}], f)

    class RaisingOCR:
        def predict(self, img):
            raise RuntimeError("OCR should not be called when output exists")

    ocr = RaisingOCR()

    processed_count = scan_and_process(
        input_dir=input_dir,
        ocr=ocr,
        output_dir=output_dir,
        processed_dir=processed_dir,
        failed_dir=failed_dir,
        max_files=None,
        retries=0,
    )

    assert processed_count == 1
    assert (processed_dir / "already.jpg").exists()
    assert (out_path).exists()
