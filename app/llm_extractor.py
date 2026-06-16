"""
Simple LLM extractor wrapper with a Mock client for local testing.
- MockLLMClient.extract_fields(ocr_json) returns a best-effort extraction using heuristics.
- Real client placeholder (not implemented) should follow same interface.
"""

from __future__ import annotations
import re
from typing import Dict, Any, Optional


class MockLLMClient:
    """A deterministic, local heuristic-based extractor used for tests and offline runs."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or "mock"

    def extract_fields(self, ocr_json: Dict[str, Any]) -> Dict[str, Any]:
        import unicodedata

        lines = ocr_json.get("text_lines") or []
        # flatten words if present
        if not lines and "words" in ocr_json:
            lines = [w.get("text", "") for w in ocr_json.get("words", [])]
        # Normalize to NFKC to convert full-width alphanumeric characters to half-width
        lines = [unicodedata.normalize("NFKC", line) for line in lines]
        text = "\n".join(lines)

        # name heuristic: look for '様' or lines starting with 患者
        name = None
        # Prefer line-wise extraction to avoid greedy cross-line matches
        for line in lines:
            if "様" in line:
                # take text before 様
                name = line.split("様")[0].strip()
                break
            if line.startswith("患者") or "患者:" in line or "患者：" in line:
                m2 = re.search(r"患者[:：]?\s*(.+)", line)
                if m2:
                    candidate = m2.group(1).strip()
                    candidate = candidate.replace("様", "").strip()
                    if 1 < len(candidate) <= 40:
                        name = candidate
                        break
        # fallback: look for lines that look like a personal name (two or three kanji/space)
        if not name:
            for line in lines:
                if re.search(r"^[\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\s]{2,40}$", line.strip()):
                    name = line.strip()
                    break

        # clinic heuristic: look for lines containing クリニック|医院|診療所|薬局|調剤
        clinic = None
        for line in lines:
            if re.search(r"クリニック|医院|診療所|薬局|調剤|clinic", line):
                clinic = line.strip()
                break

        # amount heuristic: numbers with yen or 万 (simple)
        amount = None
        # try common patterns
        m_amount = re.search(r"([0-9,，]+)\s*円", text)
        if m_amount:
            amt = m_amount.group(1)
            amt = amt.replace(",", "").replace("，", "")
            try:
                amount = int(amt)
            except Exception:
                amount = None
        else:
            # 万円形式
            m_wan = re.search(r"([0-9]+)万", text)
            if m_wan:
                try:
                    amount = int(m_wan.group(1)) * 10000
                except Exception:
                    amount = None
            else:
                # kanji numbers fallback (basic)
                m_kanji = re.search(r"一万二千|一万|二千|三千|四千|五千", text)
                if m_kanji:
                    # crude mapping for common tokens used in samples
                    mapping = {
                        "一万二千": 12000,
                        "一万": 10000,
                        "二千": 2000,
                        "三千": 3000,
                        "四千": 4000,
                        "五千": 5000,
                    }
                    amount = mapping.get(m_kanji.group(0))

        # date heuristic: YYYY/MM/DD or YYYY年M月D日 or YY/MM/DD or M/D/YY
        date = None
        m_date = re.search(r"(20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}日?)", text)
        if m_date:
            raw = m_date.group(1)
            # normalize
            raw = raw.replace("年", "-").replace("月", "-").replace("日", "")
            raw = raw.replace("/", "-")
            parts = raw.split("-")
            try:
                y = parts[0]
                mth = parts[1].zfill(2)
                d = parts[2].zfill(2)
                date = f"{y}-{mth}-{d}"
            except Exception:
                date = None
        else:
            # small YY forms like 26/1/5 or 26/01/15 => assume YY/MM/DD where YY is 2-digit year
            m2 = re.search(r"(\d{1,2})/(\d{1,2})/(\d{1,2})", text)
            if m2:
                y_part, m_part, d_part = m2.groups()
                if len(y_part) == 2:
                    yy = int(y_part)
                    y = 2000 + yy if yy < 70 else 1900 + yy
                elif len(y_part) == 1:
                    # Fallback for single-digit era year (e.g. Reiwa 1 = 2019)
                    yy = int(y_part)
                    y = 2018 + yy
                else:
                    y = int(y_part)
                date = f"{y}-{int(m_part):02d}-{int(d_part):02d}"

        return {"name": name, "clinic": clinic, "amount": amount, "date": date}


# Placeholder for a real LLM client interface
class RealLLMClient:
    def __init__(self, model_name: str, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key

    def extract_fields(self, ocr_json: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Real client not implemented in this branch")
