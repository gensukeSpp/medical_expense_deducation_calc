"""Normalization utilities for amount and date parsing."""

from __future__ import annotations
import re
from typing import Optional


def normalize_text(text: str) -> str:
    """Normalize text for comparison: fullwidth to halfwidth, lowercase, strip whitespace."""
    if not text:
        return ""
    
    # Fullwidth to halfwidth
    text = "".join(chr(ord(c) - 0xFEE0) if 0xFF10 <= ord(c) <= 0xFF19 else c for c in text)
    text = "".join(chr(ord(c) - 0xFEE0) if 0xFF21 <= ord(c) <= 0xFF3A else c for c in text)
    text = "".join(chr(ord(c) - 0xFEE0) if 0xFF41 <= ord(c) <= 0xFF5A else c for c in text)
    
    # Strip non-alphanumeric and lowercase
    text = re.sub(r"[^\w]", "", text).lower()
    return text


def parse_amount(text: str) -> Optional[int]:
    """Parse a Japanese-style amount string into integer JPY.
    Returns None if parsing fails.
    Examples: '3,800円' -> 3800, '一万二千円' -> 12000
    """
    if not text:
        return None

    # normalize fullwidth digits and punctuation to ascii
    def normalize_fw(s: str) -> str:
        res = []
        for ch in s:
            code = ord(ch)
            # fullwidth ０-９ -> 0-9
            if 0xFF10 <= code <= 0xFF19:
                res.append(chr(code - 0xFEE0))
            elif ch == "，" or ch == "、":
                res.append(",")
            elif ch == "．":
                res.append(".")
            else:
                res.append(ch)
        return "".join(res)

    t = normalize_fw(str(text))

    # direct numeric with yen
    m = re.search(r"([0-9,]+)\s*円", t)
    if m:
        s = m.group(1).replace(",", "")
        try:
            return int(s)
        except Exception:
            return None
    # 万円 style like '1万2千' or '1万' or '一万二千'
    m_wan = re.search(r"([0-9]+)万\s*(?:([0-9]+)(千)?)?", t)
    if m_wan:
        try:
            val = int(m_wan.group(1)) * 10000
            if m_wan.group(2):
                sub_val = int(m_wan.group(2))
                if m_wan.group(3) == "千":
                    sub_val *= 1000
                val += sub_val
            return val
        except Exception:
            return None

    # Kanji common mapping (limited)
    m_kanji = re.search(r"([一二三四五六七八九十百千万]+)\s*円", t)
    if m_kanji:
        kanji_str = m_kanji.group(1)
        kanji_digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        val, temp = 0, 0
        for char in kanji_str:
            if char in kanji_digits:
                temp = kanji_digits[char]
            elif char == "万":
                val += (temp or 1) * 10000
                temp = 0
            elif char == "千":
                val += (temp or 1) * 1000
                temp = 0
            elif char == "百":
                val += (temp or 1) * 100
                temp = 0
            elif char == "十":
                val += (temp or 1) * 10
                temp = 0
        val += temp
        return val

    return None


def parse_date(text: str) -> Optional[str]:
    """Parse various Japanese date formats and return ISO YYYY-MM-DD or None.
    Examples: '2026/01/15' -> '2026-01-15', '2026年1月15日' -> '2026-01-15', '1/5/26' -> '2026-01-05'
    """
    if not text:
        return None
    t = str(text).strip()
    # YYYY/MM/DD or YYYY-MM-DD or YYYY年M月D日
    m = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})日?", t)
    if m:
        y, mm, dd = m.groups()
        try:
            return f"{int(y):04d}-{int(mm):02d}-{int(dd):02d}"
        except Exception:
            return None
    # M/D/YY or M/D/YYYY
    m2 = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", t)
    if m2:
        a, b, c = m2.groups()
        try:
            if len(c) == 2:
                yy = int(c)
                y = 2000 + yy if yy < 70 else 1900 + yy
            else:
                y = int(c)
            return f"{y:04d}-{int(a):02d}-{int(b):02d}"
        except Exception:
            return None
    # YYYYMMDD compact
    m3 = re.search(r"(20\d{2})(\d{2})(\d{2})", t)
    if m3:
        y, mm, dd = m3.groups()
        try:
            return f"{int(y):04d}-{int(mm):02d}-{int(dd):02d}"
        except Exception:
            return None
    return None


def normalize_extracted(extracted: dict, ocr_json: dict) -> dict:
    """Normalize extracted fields (amount, date) from LLM output."""
    # amount
    amount = extracted.get("amount")
    # If amount already numeric, keep. If string, try to parse.
    if isinstance(amount, str):
        amount = parse_amount(amount)
    elif amount is None:
        # try to infer from OCR text_lines
        lines = ocr_json.get("text_lines") or [w.get("text") for w in ocr_json.get("words", []) if w.get("text")]
        # naive search
        for ln in lines:
            if "円" in ln or "万" in ln:
                amount = parse_amount(ln)
                if amount:
                    break
    # date
    date = extracted.get("date")
    if isinstance(date, str):
        norm_date = parse_date(date)
        date = norm_date
    elif date is None:
        lines = ocr_json.get("text_lines") or [w.get("text") for w in ocr_json.get("words", []) if w.get("text")]
        for ln in lines:
            if any(ch in ln for ch in ["年", "/", "-"]):
                d = parse_date(ln)
                if d:
                    date = d
                    break
    return {**extracted, "amount": amount, "date": date}
