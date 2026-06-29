from pathlib import Path
import glob
from typing import List, Dict, Any, Optional

from app.input import read_json
from app.output import write_json_atomic
from app.normalization import normalize_extracted
from app.db import insert_receipt, get_receipt, add_correction, get_receipt_by_source_path, get_or_create_clinic
from app.error_logging import append_error
from app.coord_search import search_coordinates
from app.template_feedback import process_correction_feedback


class ReceiptService:
    def __init__(self, output_dir: Path, db_path: Optional[Path]):
        self.output_dir = output_dir
        self.db_path = db_path

    def get_all_receipts(self) -> List[Dict[str, Any]]:
        """一覧表示用のデータを取得・整形する。"""
        files = glob.glob(str(self.output_dir / "*-structured_data.json"))
        items = []
        for file_path in files:
            try:
                data = read_json(Path(file_path))
                file_stem = Path(file_path).stem.replace("-structured_data", "")
                clinic = data.get("clinic")
                date = data.get("date")
                if clinic and date:
                    display_name = f"{clinic}-{date}"
                else:
                    display_name = file_stem
                items.append({"file_stem": file_stem, "display_name": display_name, "clinic": clinic, "date": date})
            except Exception as e:
                append_error(self.output_dir, file_path, str(e), "read_index", {})
                continue
        return items

    def get_receipt_detail(self, file_stem: str) -> Dict[str, Any]:
        """詳細表示用のデータを取得し、表示用フィールドに整形する。"""
        file_path = self.output_dir / f"{file_stem}-structured_data.json"
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        data = read_json(file_path)
        fields = [
            ("name", {"label": "氏名", "value": data.get("name", "")}),
            ("clinic", {"label": "クリニック名(調剤薬局名)", "value": data.get("clinic", "")}),
            ("amount", {"label": "支払い金額", "value": data.get("amount", "")}),
            ("date", {"label": "発行日", "value": data.get("date", "")}),
        ]
        return {"file_stem": file_stem, "fields": fields, "data": data}

    def update_receipt(self, file_stem: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        メインのビジネスロジック:
        1. JSON ファイルの読み込み。
        2. データの正規化。
        3. DB への修正記録と更新。
        4. 座標フィードバック処理。
        5. JSON ファイルの更新。
        """
        file_path = self.output_dir / f"{file_stem}-structured_data.json"
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        old_data = read_json(file_path)
        updated_data = {**old_data, **updates}
        updated_data = normalize_extracted(updated_data, old_data)

        receipt_id_for_feedback: Optional[str] = None
        clinic_id_for_feedback: Optional[str] = None
        feedback_result = None

        if self.db_path:
            try:
                # DB 処理
                receipt = get_receipt(self.db_path, file_stem)
                if receipt:
                    receipt_id_for_feedback = receipt["id"]
                    clinic_id_for_feedback = receipt.get("clinic_id")
                else:
                    receipt_id_for_feedback = file_stem
                    insert_receipt(self.db_path, receipt_id_for_feedback, str(file_path), None, old_data)

                for field_name, new_value in updates.items():
                    old_value = old_data.get(field_name)
                    add_correction(
                        self.db_path,
                        receipt_id_for_feedback,
                        field_name,
                        old_value,
                        new_value,
                    )

                # 座標フィードバック処理
                try:
                    raw_data_json_path = self.output_dir / f"{file_stem}.json"
                    receipt_with_ocr = get_receipt_by_source_path(self.db_path, str(raw_data_json_path))
                    if receipt_with_ocr is None:
                        receipt_with_ocr = get_receipt(self.db_path, receipt_id_for_feedback)

                    # 再取得: 更新されたクリニック名があればそれを使用
                    current_clinic = updated_data.get("clinic")
                    if clinic_id_for_feedback is None and current_clinic:
                        clinic_id_for_feedback = get_or_create_clinic(self.db_path, str(current_clinic))

                    ocr_entries = None
                    if receipt_with_ocr:
                        ocr_json = receipt_with_ocr.get("ocr_json")
                        if isinstance(ocr_json, list):
                            ocr_entries = ocr_json
                        elif isinstance(ocr_json, dict) and "words" in ocr_json:
                            ocr_entries = ocr_json.get("words", [])
                        elif isinstance(ocr_json, dict) and "text_lines" in ocr_json:
                            ocr_entries = [{"text": t} for t in ocr_json["text_lines"]]

                    if ocr_entries and updates:
                        field_queries = {}
                        for field_name, new_value in updates.items():
                            """
                            ユーザーが新規に入力した値（updates[field_name]）をクエリとして使用することで、欠落していたフィールドの座標も新しく学習できる。\n
                            """
                            old_value = old_data.get(field_name)
                            query_val = old_value if old_value is not None else new_value
                            if query_val is not None:
                                field_queries[field_name] = str(query_val)

                        coord_results = {}
                        for field_name, query in field_queries.items():
                            coord_results[field_name] = search_coordinates(ocr_entries, query)

                        if clinic_id_for_feedback:
                            feedback_result = process_correction_feedback(
                                db_path=self.db_path,
                                clinic_id=clinic_id_for_feedback,
                                field_coords_map=coord_results,
                                receipt_id=receipt_id_for_feedback,
                            )
                except Exception as e:
                    append_error(self.output_dir, str(file_path), str(e), "coordinate_feedback", {"updates": updates})
                    feedback_result = None

            except Exception as e:
                append_error(self.output_dir, str(file_path), str(e), "update_item_db", {})
                # DB エラーが発生しても JSON 更新は試みる

        # JSON ファイル更新
        write_json_atomic(file_path, updated_data)

        coord_errors = []
        if feedback_result and feedback_result.get("not_found_fields"):
            coord_errors = feedback_result["not_found_fields"]

        return {
            "status": "updated",
            "data": updated_data,
            "coord_errors": coord_errors,
            "feedback_result": feedback_result,
        }
