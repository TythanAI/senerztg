#!/usr/bin/env python3
"""Package everything (bots + standalone products) into one .zip.

Includes every git-tracked and new (non-ignored) file under bots/ and products/,
with the current working-tree content — and therefore **excludes** secrets
(env/*.env), databases, caches and previous archives, since those are
git-ignored.

    python tools/make_archive.py
    -> bots/dist/senerztg-all-YYYYMMDD.zip
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess
import zipfile

BOTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../bots
REPO = os.path.dirname(BOTS)                                          # repo root
TOP = "senerztg"                                                      # top folder in the zip
INCLUDE_DIRS = ["bots", "products"]


def _git(*args: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def collect_files() -> list[str]:
    files: set[str] = set()
    for d in INCLUDE_DIRS:
        files |= set(_git("ls-files", d))
        files |= set(_git("ls-files", "--others", "--exclude-standard", d))
    # Never include previous archives.
    return sorted(f for f in files if not f.startswith("bots/dist/"))


def main() -> None:
    files = collect_files()
    dist = os.path.join(BOTS, "dist")
    os.makedirs(dist, exist_ok=True)
    stamp = dt.date.today().strftime("%Y%m%d")
    out_path = os.path.join(dist, f"{TOP}-all-{stamp}.zip")

    written = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            abs_path = os.path.join(REPO, rel)
            if not os.path.isfile(abs_path):
                continue
            # rel is repo-relative, e.g. "bots/core/app.py" -> "senerztg/bots/core/app.py"
            zf.write(abs_path, os.path.join(TOP, rel))
            written += 1

    size_kb = os.path.getsize(out_path) / 1024
    print(f"wrote {out_path}")
    print(f"  {written} files, {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
