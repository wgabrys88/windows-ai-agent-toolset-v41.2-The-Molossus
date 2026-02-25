#!/usr/bin/env python3
"""
Convert all .html files in the current directory to Base64-encoded .txt files.

For each file like:
  example.html   → creates   example.txt   containing pure Base64 string
"""

import os
import base64
from pathlib import Path


def main():
    # Current working directory
    cwd = Path.cwd()
    print(f"Scanning directory: {cwd}\n")

    # Find all .html files (case insensitive)
    html_files = sorted(
        p for p in cwd.iterdir()
        if p.is_file() and p.suffix.lower() == '.html'
    )

    if not html_files:
        print("No .html files found in the current directory.")
        return

    processed = 0
    skipped = 0

    for html_path in html_files:
        txt_path = html_path.with_suffix('.txt')

        try:
            # Read binary content
            with html_path.open('rb') as f:
                content = f.read()

            # Encode to base64 (standard, no line breaks)
            b64 = base64.b64encode(content).decode('ascii')

            # Write pure base64 string to .txt
            with txt_path.open('w', encoding='ascii') as f:
                f.write(b64)

            size_kb = len(b64) // 1024
            print(f"✓ {html_path.name:24} → {txt_path.name} ({size_kb:,} KB base64)")
            processed += 1

        except PermissionError:
            print(f"✗ {html_path.name:24} → permission denied")
            skipped += 1
        except Exception as e:
            print(f"✗ {html_path.name:24} → {type(e).__name__}: {e}")
            skipped += 1

    print(f"\nDone. Processed: {processed}  |  Skipped/failed: {skipped}")


if __name__ == '__main__':
    main()