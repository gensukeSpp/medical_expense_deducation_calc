from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Protocol

from .file_repository import FileRepository

LOG = logging.getLogger("receipt_processor")


class ProcessorProtocol(Protocol):
    """
    ReceiptProcessor のインターフェースを定義するプロトコル。
    DI (Dependency Injection) を容易にする。
    """

    async def process(self, image_path: Path) -> bool: ...


class ReceiptProcessor:
    """
    ビジネスロジック: OCRから解析までを担当するクラス。
    """

    def __init__(
        self,
        ocr,
        file_repository: FileRepository,
        output_dir: Path,
        model: str = "mock",
        db_path: Path | str | None = None,
        retries: int = 1,
    ):
        self.ocr = ocr
        self.file_repository = file_repository
        self.output_dir = output_dir
        self.model = model
        self.db_path = db_path
        self.retries = retries

    async def process(self, image_path: Path) -> bool:
        """
        単一の画像を処理する。
        """
        import asyncio

        # from concurrent.futures import ThreadPoolExecutor

        loop = asyncio.get_running_loop()
        # process メソッドが呼び出されるたびに ThreadPoolExecutor を新規作成して破棄しているため、
        # パフォーマンス低下やリソースの無駄遣いにつながります。
        # with ThreadPoolExecutor() as pool:
        #     return await loop.run_in_executor(pool, self._sync_process, image_path)
        return await loop.run_in_executor(None, self._sync_process, image_path)

    def _sync_process(self, image_path: Path) -> bool:
        """
        同期的に画像を処理する (process_one のロジックを移植)。
        """
        from app.ocr_pipeline import process_image
        from app.structural_parser import process_input_json

        output_dir = self.output_dir

        # deterministic output name based on file mtime to enable idempotency
        try:
            mtime = int(image_path.stat().st_mtime)
        except Exception:
            mtime = int(time.time())
        out_fname = f"{image_path.stem}_{mtime}-raw_data.json"
        output_json_path = output_dir / out_fname

        # if output already exists, treat as already processed
        if output_json_path.exists():
            LOG.info("Output already exists for %s -> %s, skipping", image_path, output_json_path)
            return True

        # skip files that are still being written
        if not self.file_repository.is_file_stable(image_path):
            LOG.info("File appears unstable (still being written), skipping for now: %s", image_path)
            return False

        attempt = 0
        resized_path = None
        while attempt <= self.retries:
            try:
                LOG.info("Processing %s (attempt %d)", image_path, attempt + 1)
                structured = process_image(
                    image_path,
                    output_dir=output_dir,
                    output_json_path=output_json_path,
                    ocr=self.ocr,
                )

                resized_path = output_dir / f"resized_gray_{image_path.name}"

                LOG.info("Processed %s -> %s (%d items)", image_path, output_json_path, len(structured))

                # Coordinate normalization: convert absolute coords to relative
                low_confidence = False
                try:
                    from app.coord_normalizer import normalize_coordinates

                    norm_result = normalize_coordinates(output_json_path)
                    low_confidence = norm_result.get("low_confidence", False)
                    if norm_result.get("normalized"):
                        LOG.info(
                            "Normalized coordinates for %s (offset_x=%d, offset_y=%d)",
                            output_json_path,
                            norm_result["offset_x"],
                            norm_result["offset_y"],
                        )
                    elif low_confidence:
                        LOG.info(
                            "Skipped coordinate normalization for %s (topmost confidence=%.3f < 0.8)",
                            output_json_path,
                            norm_result.get("topmost_confidence", 0),
                        )
                except Exception:
                    LOG.exception("Coordinate normalization failed for %s", output_json_path)

                # Generate structured data from OCR raw data
                try:
                    process_input_json(
                        output_json_path,
                        model=self.model,
                        output_dir=output_dir,
                        db_path=self.db_path,
                    )
                    LOG.info("Structured data generated for %s", output_json_path)
                except Exception:
                    LOG.exception("Failed to generate structured data for %s", output_json_path)

                # Set low_confidence flag in structured data if needed
                if low_confidence:
                    try:
                        from app.input import read_json
                        from app.output import write_json_atomic

                        structured_data_path = output_dir / f"{image_path.stem}_{mtime}-structured_data.json"
                        if structured_data_path.exists():
                            sd = read_json(structured_data_path)
                            sd["low_confidence"] = True
                            write_json_atomic(structured_data_path, sd)
                            LOG.info("Set low_confidence flag in %s", structured_data_path)
                    except Exception:
                        LOG.exception("Failed to set low_confidence flag for %s", output_json_path)

                # Cleanup resized image
                if resized_path and resized_path.exists():
                    self.file_repository.cleanup_file(resized_path)

                return True
            except Exception as e:
                LOG.exception("Failed processing %s: %s", image_path, e)
                attempt += 1
                time.sleep(1)

        # Cleanup resized image on failure
        if resized_path and resized_path.exists():
            self.file_repository.cleanup_file(resized_path)

        # All attempts failed; copy to failed_dir
        self.file_repository.move_to_failed(image_path)
        return False
