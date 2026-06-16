Review: app/llm_extractor.py

Summary:
Good, deterministic mock extractor useful for offline testing. Clear heuristics and reasonable fallbacks.

Recommendations:
- Move `import unicodedata` to module top.
- Add precise return typing and docstrings for public API.
- Avoid bare `except Exception`; catch specific errors when parsing ints/dates.
- Precompile common regexes and reduce repeated full-text scans.
- Normalize/clean extracted name (strip punctuation, honorifics) and clinic (short name).
- Add unit tests for edge cases (multi-line names, various date formats, kanji numerals).
- Implement or stub RealLLMClient with same interface or raise clearer error.

Severity: low

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>