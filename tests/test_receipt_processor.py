"""Tests for app/services/receipt_processor.py — ReceiptProcessor class."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.receipt_processor import ReceiptProcessor
from app.services.file_repository import FileRepository


@pytest.fixture
def file_repo(tmp_path: Path) -> FileRepository:
    return FileRepository(
        output_dir=tmp_path / "output",
        processed_dir=tmp_path / "processed",
        failed_dir=tmp_path / "failed",
    )


@pytest.fixture
def processor(tmp_path: Path, file_repo: FileRepository) -> ReceiptProcessor:
    return ReceiptProcessor(
        ocr=MagicMock(),
        file_repository=file_repo,
        output_dir=tmp_path / "output",
        model="mock",
        db_path=None,
        retries=1,
    )


@pytest.fixture
def image_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.jpg"
    p.write_text("fake-image-data")
    return p


class TestInit:
    def test_initializes_with_dependencies(self, tmp_path: Path, file_repo: FileRepository):
        ocr = MagicMock()
        proc = ReceiptProcessor(
            ocr=ocr,
            file_repository=file_repo,
            output_dir=tmp_path / "output",
            model="test-model",
            db_path="/tmp/test.db",
            retries=3,
        )
        assert proc.ocr is ocr
        assert proc.model == "test-model"
        assert proc.db_path == "/tmp/test.db"
        assert proc.retries == 3


class TestSyncProcess:
    def test_returns_true_when_output_already_exists(self, processor: ReceiptProcessor, image_path: Path):
        # Create output JSON to simulate prior processing
        output_dir = processor.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        mtime = int(image_path.stat().st_mtime)
        out_fname = f"{image_path.stem}_{mtime}-raw_data.json"
        (output_dir / out_fname).write_text("[]")

        result = processor._sync_process(image_path)
        assert result is True

    def test_returns_false_when_file_unstable(self, processor: ReceiptProcessor, image_path: Path):
        # Make the file appear to be growing by using a short interval
        # and modifying the file during the check
        import threading
        import time

        def grow():
            time.sleep(0.1)
            image_path.write_text("more-data")

        t = threading.Thread(target=grow, daemon=True)
        t.start()

        result = processor._sync_process(image_path)
        assert result is False

    @patch("app.ocr_pipeline.process_image")
    @patch("app.structural_parser.process_input_json")
    def test_returns_true_on_success(
        self,
        mock_process_input_json,
        mock_process_image,
        processor: ReceiptProcessor,
        image_path: Path,
    ):
        mock_process_image.return_value = [{"text": "test", "confidence": 0.95}]
        # Ensure output dir exists
        processor.output_dir.mkdir(parents=True, exist_ok=True)

        result = processor._sync_process(image_path)

        assert result is True
        mock_process_image.assert_called_once()
        mock_process_input_json.assert_called_once()

    @patch("app.ocr_pipeline.process_image")
    def test_returns_false_on_all_retries_exhausted(
        self,
        mock_process_image,
        processor: ReceiptProcessor,
        image_path: Path,
    ):
        mock_process_image.side_effect = RuntimeError("OCR failed")
        processor.output_dir.mkdir(parents=True, exist_ok=True)

        result = processor._sync_process(image_path)

        assert result is False
        # Should have been copied to failed dir
        failed_files = list(processor.file_repository.failed_dir.glob("*"))
        assert len(failed_files) >= 1


class TestAsyncProcess:
    @pytest.mark.asyncio
    async def test_process_delegates_to_sync(self, processor: ReceiptProcessor, image_path: Path):
        # Create output JSON to simulate prior processing
        processor.output_dir.mkdir(parents=True, exist_ok=True)
        mtime = int(image_path.stat().st_mtime)
        out_fname = f"{image_path.stem}_{mtime}-raw_data.json"
        (processor.output_dir / out_fname).write_text("[]")

        result = await processor.process(image_path)
        assert result is True
