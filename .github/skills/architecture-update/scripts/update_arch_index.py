#!/usr/bin/env python3
"""Update docs/architecture/README.md index table from dated architecture files.

Usage: python scripts/update_arch_index.py

This script scans docs/architecture for *.md (excluding README.md), extracts a Date: YYYY-MM-DD
line or falls back to file mtime, and extracts a short summary from the top of each file.
It then writes docs/architecture/README.md with a table of entries sorted by date (desc).
"""
from pathlib import Path
import re
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
ARCH_DIR = ROOT / "docs" / "architecture"
README = ARCH_DIR / "README.md"

DATE_RE = re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})", flags=re.IGNORECASE | re.MULTILINE)


def extract_date_and_summary(path: Path):
    text = path.read_text(encoding="utf-8")
    m = DATE_RE.search(text)
    if m:
        date_str = m.group(1)
        try:
            date = datetime.fromisoformat(date_str).date()
        except Exception:
            date = datetime.fromtimestamp(path.stat().st_mtime).date()
    else:
        date = datetime.fromtimestamp(path.stat().st_mtime).date()

    # summary: first non-empty line that is not a heading
    summary = ""
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        # take up to 120 chars
        summary = s
        break
    if not summary:
        summary = "(no summary)"
    if len(summary) > 120:
        summary = summary[:117] + "..."
    return date.isoformat(), summary


def build_index():
    if not ARCH_DIR.exists():
        print(f"No architecture dir at {ARCH_DIR}")
        return
    entries = []
    for p in ARCH_DIR.glob("*.md"):
        if p.name == "README.md":
            continue
        date, summary = extract_date_and_summary(p)
        entries.append((date, summary, p.name))

    # sort desc by date
    entries.sort(key=lambda x: x[0], reverse=True)

    header = """# Architecture snapshots

This directory contains dated snapshots of the project's high-level architecture. Each file documents the major components, dataflow, and key design decisions at the time of the snapshot.

| Date | Summary | File |
| --- | --- | --- |
"""

    rows = []
    for date, summary, name in entries:
        file_link = f"{name}"
        rows.append(f"| {date} | {summary} | [{file_link}]({file_link}) |")

    # If README exists and already contains a table, preserve existing rows and append only new entries
    if README.exists():
        text = README.read_text(encoding="utf-8")
        table_header = "| Date | Summary | File |"
        if table_header in text:
            # find start of table header
            start_idx = text.index(table_header)
            # find end of table: look for the first blank line after the header/separator
            after_table = text[start_idx:]
            lines_after = after_table.splitlines()
            # header line + separator line consumed, rows start at index 2
            existing_rows = []
            for ln in lines_after[2:]:
                if ln.strip() == "":
                    break
                existing_rows.append(ln)
            # extract filenames already present
            import re as _re

            existing_files = set()
            for ln in existing_rows:
                m = _re.search(r"\]\(([^)]+)\)", ln)
                if m:
                    existing_files.add(m.group(1))

            # keep existing rows and append only rows with new filenames
            new_rows = []
            for r in rows:
                m = _re.search(r"\]\(([^)]+)\)", r)
                fname = m.group(1) if m else None
                if fname and fname not in existing_files:
                    new_rows.append(r)

            if not new_rows:
                print(f"No new architecture entries to add to {README}")
                return

            # rebuild README: keep content up to end of existing table, then append new rows and the rest
            # find end position of existing table in original text
            # find index after existing rows
            # compute number of lines to skip: header + separator + len(existing_rows)
            orig_lines = text.splitlines()
            # find header line index
            hdr_idx = next(i for i, ln in enumerate(orig_lines) if ln.strip() == table_header)
            end_idx = hdr_idx + 2 + len(existing_rows)
            before = "\n".join(orig_lines[:end_idx])
            after = "\n".join(orig_lines[end_idx:])
            combined = before + "\n" + "\n".join(new_rows) + ("\n" + after if after else "\n")
            README.write_text(combined, encoding="utf-8")
            print(f"Appended {len(new_rows)} new entries to {README}")
            return

    # default: write full content (no existing table found)
    content = header + "\n".join(rows) + "\n"
    README.write_text(content, encoding="utf-8")
    print(f"Updated {README} with {len(entries)} entries")


if __name__ == "__main__":
    build_index()
