# Prompt templates for LLM-based extraction

SIMPLE_EXTRACT_PROMPT = '''
You are given OCR-extracted text lines from a Japanese medical receipt. Extract the following fields as JSON: name (patient), clinic (clinic or pharmacy), amount (numeric JPY), date (ISO YYYY-MM-DD). If a field is not present, use null.

Example input:
{input_text}

Return strictly JSON with keys: name, clinic, amount, date.
'''
