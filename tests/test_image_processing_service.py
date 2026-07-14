"""Tests for app/services/image_processing_service.py — ImageProcessingService orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.image_processing_service import ImageProcessingService

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_ocr_engine() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(mock_ocr_engine: MagicMock) -> ImageProcessingService:
    return ImageProcessingService(ocr_engine=mock_ocr_engine)


@pytest.fixture
def image_path(tmp_path: Path) -> Path:
    p = tmp_path / "receipt-001.jpg"
    p.write_text("fake-image-data")
    return p


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "output_json"
    d.mkdir()
    return d


# ------------------------------------------------------------------
# _get_mtime
# ------------------------------------------------------------------


class TestGetMtime:
    def test_returns_mtime_when_file_exists(self, image_path: Path):
        mtime = ImageProcessingService._get_mtime(image_path)
        assert isinstance(mtime, int)
        assert mtime > 0

    def test_fallback_when_file_does_not_exist(self, tmp_path: Path):
        missing = tmp_path / "nope.jpg"
        mtime = ImageProcessingService._get_mtime(missing)
        assert isinstance(mtime, int)
        assert mtime > 0


# ------------------------------------------------------------------
# _make_output_path
# ------------------------------------------------------------------


class TestMakeOutputPath:
    def test_returns_correct_path(self, image_path: Path, output_dir: Path):
        mtime = 1234567890
        result = ImageProcessingService._make_output_path(image_path, output_dir, mtime)
        assert result == output_dir / "receipt-001_1234567890-raw_data.json"
        assert result.parent == output_dir


# ------------------------------------------------------------------
# _run_ocr
# ------------------------------------------------------------------


class TestRunOcr:
    def test_calls_process_image_and_logs(
        self, service: ImageProcessingService, image_path: Path, output_dir: Path, caplog: pytest.LogCaptureFixture
    ):
        output_json_path = output_dir / "receipt-001_12345-raw_data.json"
        with patch("app.services.image_processing_service.process_image", return_value=[{"text": "hello"}]) as mock_pi:
            service._run_ocr(image_path, output_dir, output_json_path)
            mock_pi.assert_called_once_with(
                image_path,
                output_dir=output_dir,
                output_json_path=output_json_path,
                ocr=service.ocr_engine,
            )
        assert "Saved 1 item to" in caplog.text

    def test_logs_warning_when_none(
        self, service: ImageProcessingService, image_path: Path, output_dir: Path, caplog: pytest.LogCaptureFixture
    ):
        output_json_path = output_dir / "receipt-001_12345-raw_data.json"
        with patch("app.services.image_processing_service.process_image", return_value=None):
            service._run_ocr(image_path, output_dir, output_json_path)
        assert "process_image returned None" in caplog.text

    def test_raises_on_exception(self, service: ImageProcessingService, image_path: Path, output_dir: Path):
        output_json_path = output_dir / "receipt-001_12345-raw_data.json"
        with patch("app.services.image_processing_service.process_image", side_effect=ValueError("ocr failed")):
            with pytest.raises(ValueError, match="ocr failed"):
                service._run_ocr(image_path, output_dir, output_json_path)


# ------------------------------------------------------------------
# _normalize_coords
# ------------------------------------------------------------------


class TestNormalizeCoords:
    def test_returns_false_when_normalized(self, service: ImageProcessingService, output_dir: Path):
        output_json_path = output_dir / "test.json"
        output_json_path.write_text("[]")
        with patch(
            "app.services.image_processing_service.normalize_coordinates",
            return_value={
                "normalized": True,
                "offset_x": 10,
                "offset_y": 20,
            },
        ):
            result = service._normalize_coords(output_json_path)
        assert result is False

    def test_returns_true_when_low_confidence(self, service: ImageProcessingService, output_dir: Path):
        output_json_path = output_dir / "test.json"
        output_json_path.write_text("[]")
        with patch(
            "app.services.image_processing_service.normalize_coordinates",
            return_value={
                "normalized": False,
                "low_confidence": True,
                "topmost_confidence": 0.5,
            },
        ):
            result = service._normalize_coords(output_json_path)
        assert result is True

    def test_returns_false_on_exception(
        self, service: ImageProcessingService, output_dir: Path, caplog: pytest.LogCaptureFixture
    ):
        output_json_path = output_dir / "test.json"
        output_json_path.write_text("[]")
        with patch("app.services.image_processing_service.normalize_coordinates", side_effect=RuntimeError("boom")):
            result = service._normalize_coords(output_json_path)
        assert result is False
        assert "Coordinate normalization failed" in caplog.text


# ------------------------------------------------------------------
# _parse_structured
# ------------------------------------------------------------------


class TestParseStructured:
    def test_calls_process_input_json(self, service: ImageProcessingService, output_dir: Path):
        output_json_path = output_dir / "test.json"
        output_json_path.write_text("[]")
        with patch("app.services.image_processing_service.process_input_json") as mock_pij:
            service._parse_structured(output_json_path, model="mock", output_dir=output_dir, db_path=None)
            mock_pij.assert_called_once_with(
                output_json_path,
                model="mock",
                output_dir=output_dir,
                db_path=None,
            )

    def test_raises_on_exception(self, service: ImageProcessingService, output_dir: Path):
        output_json_path = output_dir / "test.json"
        output_json_path.write_text("[]")
        with patch("app.services.image_processing_service.process_input_json", side_effect=ValueError("parse failed")):
            with pytest.raises(ValueError, match="parse failed"):
                service._parse_structured(output_json_path, model="mock", output_dir=output_dir, db_path=None)


# ------------------------------------------------------------------
# _apply_low_confidence_flag
# ------------------------------------------------------------------


class TestApplyLowConfidenceFlag:
    def test_sets_flag_when_structured_file_exists(
        self, service: ImageProcessingService, image_path: Path, output_dir: Path
    ):
        mtime = 12345
        structured_path = output_dir / f"{image_path.stem}_{mtime}-structured_data.json"
        structured_path.write_text(json.dumps({"clinic_name": "test"}))

        service._apply_low_confidence_flag(image_path, output_dir, mtime)

        data = json.loads(structured_path.read_text())
        assert data["low_confidence"] is True

    def test_skips_when_structured_file_missing(
        self, service: ImageProcessingService, image_path: Path, output_dir: Path, caplog: pytest.LogCaptureFixture
    ):
        service._apply_low_confidence_flag(image_path, output_dir, 99999)
        # No error should be raised; just skipped silently
        assert len(caplog.records) == 0 or all(r.levelno < 40 for r in caplog.records)


# ------------------------------------------------------------------
# process (full orchestration)
# ------------------------------------------------------------------


class TestProcess:
    def test_happy_path(self, service: ImageProcessingService, image_path: Path, output_dir: Path):
        mtime = int(image_path.stat().st_mtime)
        raw_path = output_dir / f"receipt-001_{mtime}-raw_data.json"
        structured_path = output_dir / f"receipt-001_{mtime}-structured_data.json"

        with (
            patch.object(service, "_run_ocr") as mock_ocr,
            patch.object(service, "_normalize_coords", return_value=False) as mock_norm,
            patch.object(service, "_parse_structured") as mock_parse,
            patch.object(service, "_apply_low_confidence_flag") as mock_aug,
        ):
            service.process(image_path, output_dir, model="mock", db_path=None)

        mock_ocr.assert_called_once_with(image_path, output_dir, raw_path)
        mock_norm.assert_called_once_with(raw_path)
        mock_parse.assert_called_once_with(raw_path, model="mock", output_dir=output_dir, db_path=None)
        mock_aug.assert_not_called()

    def test_low_confidence_triggers_augmentation(
        self, service: ImageProcessingService, image_path: Path, output_dir: Path
    ):
        mtime = int(image_path.stat().st_mtime)
        raw_path = output_dir / f"receipt-001_{mtime}-raw_data.json"

        with (
            patch.object(service, "_run_ocr"),
            patch.object(service, "_normalize_coords", return_value=True),
            patch.object(service, "_parse_structured"),
            patch.object(service, "_apply_low_confidence_flag") as mock_aug,
        ):
            service.process(image_path, output_dir, model="mock", db_path=None)

        mock_aug.assert_called_once_with(image_path, output_dir, mtime)

    def test_ocr_failure_propagates(self, service: ImageProcessingService, image_path: Path, output_dir: Path):
        with patch.object(service, "_run_ocr", side_effect=ValueError("ocr failed")):
            with pytest.raises(ValueError, match="ocr failed"):
                service.process(image_path, output_dir, model="mock", db_path=None)

    def test_parse_failure_propagates(self, service: ImageProcessingService, image_path: Path, output_dir: Path):
        with (
            patch.object(service, "_run_ocr"),
            patch.object(service, "_normalize_coords", return_value=False),
            patch.object(service, "_parse_structured", side_effect=ValueError("parse failed")),
        ):
            with pytest.raises(ValueError, match="parse failed"):
                service.process(image_path, output_dir, model="mock", db_path=None)
