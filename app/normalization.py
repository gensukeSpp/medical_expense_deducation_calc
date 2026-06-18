"""Normalization utilities for amount and date parsing."""
from __future__ import annotations
import re
from typing import Optional
from datetime import datetime


def parse_amount(text: str) -> Optional[int]:
    """Parse a Japanese-style amount string into integer JPY.
    Returns None if parsing fails.
    Examples: '3,800円' -> 3800, '一万二千円' -> 12000
    """
    if not text:
        return None
    t = str(text)
    # direct numeric with yen
    m = re.search(r"([0-9,，]+)\s*円", t)
    if m:
        s = m.group(1).replace(",", "").replace("，", "")
        try:
            return int(s)
        except Exception:
            return None
    # 万円 style like '1万2千' or '1万' or '一万二千'
    m_wan = re.search(r"([0-9]+)万", t)
    if m_wan:
        try:
            return int(m_wan.group(1)) * 10000
        except Exception:
            return None
    # Kanji common mapping (limited)
    mapping = {"一万二千": 12000, "一万": 10000, "二千": 2000, "三千": 3000, "四千": 4000, "五千": 5000}
    for k, v in mapping.items():
        if k in t:
            return v
    # normalize fullwidth digits and punctuation to ascii
    def normalize_fw(s: str) -> str:
        res = []
        for ch in s:
            code = ord(ch)
            # fullwidth ０-９ -> 0-9
            if 0xFF10 <= code <= 0xFF19:
                res.append(chr(code - 0xFEE0))
            elif ch == '，' or ch == '、':
                res.append(',')
            elif ch == '．':
                res.append('.')
            else:
                res.append(ch)
        return ''.join(res)

    norm = normalize_fw(t)
    m2 = re.search(r"([0-9,]+)\s*円", norm)
    if m2:
        s = m2.group(1).replace(",", "")
        try:
            return int(s)
        except Exception:
            return None
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
