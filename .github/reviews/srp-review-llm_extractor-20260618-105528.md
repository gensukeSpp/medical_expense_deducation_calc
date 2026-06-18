SRP Review: app/llm_extractor.py
Generated: 2026-06-18 10:55:28

1) Scope and responsibilities

- Module (app/llm_extractor.py): provides both a heuristic/mock extractor and a placeholder real client. Module-level responsibilities: interface provision, heuristics implementation, normalization utilities (inline), and placeholder integration.

- MockLLMClient:
  - Initialization (model_name storage)
  - extract_fields: aggregates OCR lines, normalizes text, and performs multiple field-specific heuristics (name, clinic, amount, date).

- RealLLMClient:
  - Holds credentials/config and declares the same extract_fields interface (Not implemented).

2) SRP violations found

- MockLLMClient.extract_fields (lines ~18-125): This single method performs multiple independent reasons to change:
  - Input normalization and line flattening (unicode normalization, joining)
  - Name extraction heuristics
  - Clinic extraction heuristics
  - Amount extraction heuristics (multiple formats and fallbacks)
  - Date extraction heuristics (multiple patterns and normalization)

Each of the above is a distinct responsibility: changes to name heuristics, amount parsing, or date formats would cause edits to this single large method.

- Module-level mixing: The module couples a heuristic implementation with the API placeholder; adding another extractor (e.g., external LLM wrapper) could add more responsibilities here.

3) Recommendations / Minimal refactors (examples in-place, non-breaking)

Goal: extract small pure functions for each responsibility and keep MockLLMClient.extract_fields orchestrating only.

A. Add pure helper functions (normalize, extract_name, extract_clinic, extract_amount, extract_date):

Example helpers to add in same file near top-level:

```py
import unicodedata

def normalize_lines(ocr_json: dict) -> list[str]:
    lines = ocr_json.get("text_lines") or []
    if not lines and "words" in ocr_json:
        lines = [w.get("text", "") for w in ocr_json.get("words", [])]
    return [unicodedata.normalize("NFKC", l) for l in lines]

def extract_name_from_lines(lines: list[str]) -> Optional[str]:
    for line in lines:
        if "様" in line:
            return line.split("様")[0].strip()
        if line.startswith("患者") or "患者:" in line or "患者：" in line:
            m = re.search(r"患者[:：]?\s*(.+)", line)
            if m:
                cand = m.group(1).replace("様", "").strip()
                if 1 < len(cand) <= 40:
                    return cand
    for line in lines:
        if re.search(r"^[\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\s]{2,40}$", line.strip()):
            return line.strip()
    return None
```

B. Extract amount and date parsing to focused helpers:

```py
def extract_amount_from_text(text: str) -> Optional[int]:
    m = re.search(r"([0-9,，]+)\s*円", text)
    if m:
        a = m.group(1).replace(",", "").replace("，", "")
        try:
            return int(a)
        except ValueError:
            return None
    m2 = re.search(r"([0-9]+)万", text)
    if m2:
        try:
            return int(m2.group(1)) * 10000
        except ValueError:
            return None
    mapping = {"一万二千": 12000, "一万": 10000, "二千": 2000}
    m3 = re.search(r"一万二千|一万|二千|三千|四千|五千", text)
    return mapping.get(m3.group(0)) if m3 else None


def extract_date_from_text(text: str) -> Optional[str]:
    m = re.search(r"(20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}日?)", text)
    if m:
        raw = m.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
        parts = raw.split("-")
        try:
            y = parts[0]
            mth = parts[1].zfill(2)
            d = parts[2].zfill(2)
            return f"{y}-{mth}-{d}"
        except Exception:
            return None
    m2 = re.search(r"(\d{1,2})/(\d{1,2})/(\d{1,2})", text)
    if m2:
        y_part, m_part, d_part = m2.groups()
        yy = int(y_part)
        if len(y_part) == 2:
            y = 2000 + yy if yy < 70 else 1900 + yy
        elif len(y_part) == 1:
            y = 2018 + yy
        else:
            y = yy
        return f"{y}-{int(m_part):02d}-{int(d_part):02d}"
    return None
```

C. Simplify MockLLMClient to orchestrator only (minimal change):

```py
class MockLLMClient:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or "mock"

    def extract_fields(self, ocr_json: Dict[str, Any]) -> Dict[str, Any]:
        lines = normalize_lines(ocr_json)
        text = "\n".join(lines)
        name = extract_name_from_lines(lines)
        clinic = None
        for l in lines:
            if re.search(r"クリニック|医院|診療所|薬局|調剤|clinic", l):
                clinic = l.strip(); break
        amount = extract_amount_from_text(text)
        date = extract_date_from_text(text)
        return {"name": name, "clinic": clinic, "amount": amount, "date": date}
```

4) Benefits

- Each helper can be tested independently (unit tests) and changed for different locales or improved heuristics without touching orchestration.
- Enables adding an external LLM-based extractor class that reuses helpers (normalization) and implements richer semantics.
- Improves readability and isolates parsing bugs.

5) Additional suggestions (non-mandatory)

- Add a small interface/protocol (e.g., LLMClientProtocol) to document extract_fields signature and allow duck-typing between Mock and Real clients.
- Move heuristics into a small `heuristic_extractor.py` module if more extractors are added.
- Add unit tests for each helper and edge cases for ambiguous date and amount forms.

---

Summary: Major SRP violation is the large extract_fields method mixing normalization and many field-specific parsing heuristics. Extracting pure helpers keeps behavior identical while decoupling reasons-to-change.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
