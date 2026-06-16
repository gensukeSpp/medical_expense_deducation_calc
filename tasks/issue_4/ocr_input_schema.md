# OCR input schema (expected)

This project expects OCR output JSON with at least one of these forms:

1) text_lines: an ordered list of OCR-extracted textual lines (strings)
2) words: a list of objects {"text": str, "confidence": float, "box": [x1,y1,x2,y2] (optional)}

Example:
{
  "text_lines": ["...line1...", "...line2..."],
  "words": [{"text":"...","confidence":0.95}]
}

The LLM extractor will use text_lines preferentially; words are provided for future coordinate-based features.
