#!/usr/bin/env python3
"""
Tactical Breach Wizards — localization patcher

Files:
  translations.txt       original localization file
  corrections.json       exact English-key -> corrected Russian translation
  glossary.json           terminology/reference glossary

Usage:
  python patch_localization.py
  python patch_localization.py --input translations.txt --corrections corrections.json
  python patch_localization.py --check-only

Output:
  translations_fixed.txt
  translations_backup.txt
  changes_report.txt

The script ONLY changes the Russian side of exact English=Russian entries.
It never invents translations and never rewrites unmatched lines.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path


DEFAULT_INPUT = "translations.txt"
DEFAULT_CORRECTIONS = "corrections.json"
DEFAULT_GLOSSARY = "glossary.json"
DEFAULT_OUTPUT = "translations_fixed.txt"
DEFAULT_BACKUP = "translations_backup.txt"
DEFAULT_REPORT = "changes_report.txt"


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def split_entry(line: str):
    """
    Split only on the FIRST '='.
    This is important because translations can contain '=' later.
    """
    raw = line.rstrip("\n")
    if not raw or raw.startswith("#") or "=" not in raw:
        return None
    english, russian = raw.split("=", 1)
    return english, russian


def build_index(lines):
    """
    Map English keys to all line numbers where they occur.
    Duplicate keys are common in localization files, so we keep every occurrence.
    """
    index = {}
    for number, line in enumerate(lines, start=1):
        entry = split_entry(line)
        if entry is None:
            continue
        english, _ = entry
        index.setdefault(english, []).append(number)
    return index


def normalize_corrections(data):
    """
    Supports either:
      {"English key": "Russian translation"}

    or:
      {"entries": {"English key": "Russian translation"}}

    or a list:
      [{"english": "...", "russian": "...", "note": "..."}]
    """
    notes = {}

    if isinstance(data, dict) and "entries" in data:
        data = data["entries"]

    if isinstance(data, dict):
        return data, notes

    if isinstance(data, list):
        result = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            en = item.get("english")
            ru = item.get("russian")
            if en is not None and ru is not None:
                result[en] = ru
                if item.get("note"):
                    notes[en] = item["note"]
        return result, notes

    raise ValueError("corrections.json must contain an object or a list of correction entries")


def apply_corrections(lines, corrections, notes):
    index = build_index(lines)
    changed = []
    missing = []
    unchanged = []
    duplicates = []

    for english, new_russian in corrections.items():
        locations = index.get(english, [])

        if not locations:
            missing.append(english)
            continue

        if len(locations) > 1:
            duplicates.append((english, locations))

        for line_no in locations:
            old_line = lines[line_no - 1].rstrip("\n")
            old_entry = split_entry(old_line)

            if old_entry is None:
                continue

            _, old_russian = old_entry

            if old_russian == new_russian:
                unchanged.append((line_no, english, new_russian))
                continue

            lines[line_no - 1] = f"{english}={new_russian}\n"

            changed.append({
                "line": line_no,
                "english": english,
                "old": old_russian,
                "new": new_russian,
                "note": notes.get(english, "")
            })

    return changed, missing, unchanged, duplicates


def write_report(path, changed, missing, unchanged, duplicates):
    with path.open("w", encoding="utf-8") as f:
        f.write("TACTICAL BREACH WIZARDS — LOCALIZATION PATCH REPORT\n")
        f.write("=" * 58 + "\n\n")

        f.write(f"Changed:   {len(changed)}\n")
        f.write(f"Unchanged: {len(unchanged)}\n")
        f.write(f"Missing:   {len(missing)}\n")
        f.write(f"Duplicates:{len(duplicates)}\n\n")

        if changed:
            f.write("CHANGES\n")
            f.write("-" * 58 + "\n")
            for item in changed:
                f.write(f"\nLine {item['line']}\n")
                f.write(f"EN:  {item['english']}\n")
                f.write(f"OLD: {item['old']}\n")
                f.write(f"NEW: {item['new']}\n")
                if item["note"]:
                    f.write(f"NOTE: {item['note']}\n")

        if missing:
            f.write("\n\nMISSING KEYS\n")
            f.write("-" * 58 + "\n")
            for key in missing:
                f.write(key + "\n")

        if duplicates:
            f.write("\n\nDUPLICATE KEYS\n")
            f.write("-" * 58 + "\n")
            for key, lines in duplicates:
                f.write(f"{key}\n")
                f.write("  lines: " + ", ".join(map(str, lines)) + "\n")


def check_glossary(glossary):
    """
    The glossary is intentionally informational.
    It is NOT automatically applied to the translation file.
    This prevents accidental replacement of legitimate contextual variants.
    """
    if not isinstance(glossary, dict):
        return ["glossary.json should contain a JSON object"]

    warnings = []
    terms = glossary.get("terms", glossary)

    if not isinstance(terms, dict):
        warnings.append("glossary 'terms' must be an object")

    return warnings


def main():
    parser = argparse.ArgumentParser(description="Apply reviewed TBW localization corrections.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--corrections", default=DEFAULT_CORRECTIONS)
    parser.add_argument("--glossary", default=DEFAULT_GLOSSARY)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--backup", default=DEFAULT_BACKUP)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    corrections_path = Path(args.corrections)
    glossary_path = Path(args.glossary)
    output_path = Path(args.output)
    backup_path = Path(args.backup)
    report_path = Path(args.report)

    for path in (input_path, corrections_path):
        if not path.exists():
            raise SystemExit(f"ERROR: file not found: {path}")

    lines = input_path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    corrections_raw = load_json(corrections_path)
    corrections, notes = normalize_corrections(corrections_raw)

    glossary = {}
    if glossary_path.exists():
        glossary = load_json(glossary_path)
        warnings = check_glossary(glossary)
        for warning in warnings:
            print("WARNING:", warning)

    changed, missing, unchanged, duplicates = apply_corrections(
        lines, corrections, notes
    )

    if args.check_only:
        print(f"Keys in corrections: {len(corrections)}")
        print(f"Would change:        {len(changed)}")
        print(f"Already identical:   {len(unchanged)}")
        print(f"Missing in source:   {len(missing)}")
        print(f"Duplicate keys:      {len(duplicates)}")
        if missing:
            print("\nMissing keys:")
            for key in missing:
                print("  -", key)
        return

    shutil.copy2(input_path, backup_path)
    output_path.write_text("".join(lines), encoding="utf-8")

    write_report(report_path, changed, missing, unchanged, duplicates)

    print("DONE")
    print(f"Original:  {input_path}")
    print(f"Backup:    {backup_path}")
    print(f"Fixed:     {output_path}")
    print(f"Report:    {report_path}")
    print()
    print(f"Changed:   {len(changed)}")
    print(f"Unchanged: {len(unchanged)}")
    print(f"Missing:   {len(missing)}")
    print(f"Duplicates:{len(duplicates)}")


if __name__ == "__main__":
    main()
