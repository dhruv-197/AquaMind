#!/usr/bin/env python3
"""Fail if user-facing sources contain classic mojibake markers.

Scans checked-in UI, API, and documentation text for the Latin-1 misreads of
UTF-8 punctuation (â, Ã, Â, and the Unicode replacement character). Legitimate
Unicode such as degree symbols (deg C / °C) is allowed; only the broken
sequences that mean "this file was saved with the wrong encoding" fail the check.

Run:
  py scripts/check_encoding.py
  npm run check:encoding
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Directories / files that judges or operators actually read.
SCAN_ROOTS = (
    ROOT / "src",
    ROOT / "fastapi_app",
    ROOT / "ai",
    ROOT / "climate",
    ROOT / "server.ts",
    ROOT / "vite.config.ts",
    ROOT / "README.md",
    ROOT / "TECHNICAL_ROUND_PREP.md",
    ROOT / "PROTOTYPE_IMPROVEMENT_PLAN.md",
    ROOT / ".env.example",
)

EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".py", ".md", ".html", ".css", ".example"}

SKIP_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    ".rec_cache",
    ".om_cache",
    "demo_fixtures",  # captured payloads; not edited as product copy
}

# Characters that almost always mean UTF-8 was decoded as Latin-1 / cp1252.
MOJIBAKE_MARKERS = ("â", "Ã", "Â", "\ufffd")


def iter_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() not in EXTENSIONS and path.name not in {".env.example"}:
                continue
            files.append(path)
    return sorted(files)


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return (line_no, marker, snippet) for each offending line."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [(0, "encoding", "file is not valid UTF-8")]

    hits: list[tuple[int, str, str]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for marker in MOJIBAKE_MARKERS:
            if marker in line:
                hits.append((line_no, marker, line.strip()[:140]))
                break
    return hits


def main() -> int:
    failures: list[str] = []
    scanned = 0
    for path in iter_files():
        scanned += 1
        for line_no, marker, snippet in scan_file(path):
            rel = path.relative_to(ROOT).as_posix()
            failures.append(f"{rel}:{line_no}: found {marker!r} in {snippet!r}")

    if failures:
        print(f"Encoding check failed ({len(failures)} hit(s) across {scanned} files):")
        for item in failures:
            print(f"  {item}")
        print(
            "\nReplace broken punctuation with ASCII (' - ... *) or a correct UTF-8 "
            "character, then re-run: py scripts/check_encoding.py"
        )
        return 1

    print(f"Encoding check passed ({scanned} files, no mojibake markers).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
