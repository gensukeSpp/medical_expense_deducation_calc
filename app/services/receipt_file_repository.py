"""Receipt file repository: handles JSON file I/O operations."""

from pathlib import Path
import glob
from typing import Dict, Any, List, Optional

from app.input import read_json
from app.output import write_json_atomic
from app.error_logging import append_error


class ReceiptFileRepository:
    """Repository for handling file system operations related to receipts."""

    def __init__(self, output_dir: Path):
        """
        Initialize the repository.

        Args:
            output_dir: Directory where JSON files are stored.
        """
        self.output_dir = output_dir

    def find_all_receipt_files(self) -> List[Path]:
        """
        Find all receipt JSON files in the output directory.

        Returns:
            List of Path objects for receipt files.
        """
        pattern = str(self.output_dir / "*-structured_data.json")
        return [Path(f) for f in glob.glob(pattern)]

    def load_receipt(self, file_stem: str) -> Dict[str, Any]:
        """
        Load a receipt JSON file.

        Args:
            file_stem: The stem of the file to load (without -structured_data suffix).

        Returns:
            Parsed JSON data as a dictionary.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        file_path = self.output_dir / f"{file_stem}-structured_data.json"
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return read_json(file_path)

    def save_receipt(self, file_stem: str, data: Dict[str, Any]) -> None:
        """
        Save a receipt JSON file atomically.

        Args:
            file_stem: The stem of the file to save (without -structured_data suffix).
            data: The data to write as JSON.
        """
        file_path = self.output_dir / f"{file_stem}-structured_data.json"
        write_json_atomic(file_path, data)

    def load_raw_data(self, file_stem: str) -> Optional[Dict[str, Any]]:
        """
        Load raw OCR data from a JSON file.

        Args:
            file_stem: The stem of the file to load.

        Returns:
            Parsed JSON data or None if no file matches.
        """
        # Try both patterns: *-raw_data.json and *-structured_data.json (without -structured_data)
        patterns = [
            str(self.output_dir / f"{file_stem}*-raw_data.json"),
            str(self.output_dir / f"{file_stem}.json"),
        ]
        for pattern in patterns:
            raw_data_matches = sorted(glob.glob(pattern))
            if raw_data_matches:
                try:
                    return read_json(Path(raw_data_matches[-1]))
                except Exception as e:
                    append_error(
                        self.output_dir,
                        str(raw_data_matches[-1]),
                        str(e),
                        "raw_data_load",
                        {"file_stem": file_stem},
                    )
        return None

    def get_ocr_entries(self, file_stem: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get OCR entries from raw data file.

        Args:
            file_stem: The stem of the file to load.

        Returns:
            List of OCR entry dictionaries or None if not available.
        """
        raw_data = self.load_raw_data(file_stem)
        if raw_data is None:
            return None

        if isinstance(raw_data, list):
            return raw_data
        elif isinstance(raw_data, dict):
            if "words" in raw_data:
                return raw_data["words"]
            elif "text_lines" in raw_data:
                return [{"text": t} for t in raw_data["text_lines"]]
        return None
