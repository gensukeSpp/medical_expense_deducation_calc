from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Protocol

from .file_repository import FileRepository
from .receipt_processor import ProcessorProtocol

LOG = logging.getLogger("file_monitor")


class FileMonitorProtocol(Protocol):
    """
    FileMonitor のインターフェースを定義するプロトコル。
    """

    async def start(self) -> None: ...

    def stop(self) -> None: ...


class PollingMonitor:
    """
    ポーリングメカニズムによるファイル監視。
    """

    def __init__(
        self,
        input_dir: Path,
        file_repository: FileRepository,
        processor: ProcessorProtocol,
        poll_interval: int = 10,
    ):
        self.input_dir = input_dir
        self.file_repository = file_repository
        self.processor = processor
        self.poll_interval = poll_interval
        self._running = False

    async def start(self) -> None:
        """監視ループを開始する。"""
        self._running = True
        LOG.info("Starting polling monitor on %s", self.input_dir)

        while self._running:
            try:
                await self._scan_and_process()
            except Exception:
                LOG.exception("Error during polling cycle")

            if not self._running:
                break
            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        """監視を停止する。"""
        self._running = False
        LOG.info("Stopping polling monitor")

    async def _scan_and_process(self) -> None:
        """ディレクトリをスキャンして新しいファイルを処理する。"""
        loop = asyncio.get_running_loop()
        candidates = await loop.run_in_executor(None, self._get_candidates)

        for p in candidates:
            if not self._running:
                break

            # self.processor.process(p)（ReceiptProcessor._sync_process）の内部でも全く同じ is_file_stable チェックが実行されています。
            # 安定性チェック (FileRepository を使用)
            # is_stable = await loop.run_in_executor(None, self.file_repository.is_file_stable, p)

            # if not is_stable:
            #     LOG.info("File %s is not stable, skipping", p)
            #     continue

            LOG.info("New file detected: %s", p)
            # 処理を実行 (非同期)
            success = await self.processor.process(p)
            if success:
                LOG.info("Successfully processed %s", p)
            else:
                LOG.error("Failed to process %s", p)

    def _get_candidates(self) -> list[Path]:
        """画像ファイルをスキャンして返す。"""
        return sorted([p for p in self.input_dir.iterdir() if self.file_repository.is_image_file(p)])
