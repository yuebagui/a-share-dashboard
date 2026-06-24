#!/usr/bin/env python3
"""
Copy the dashboard app to the repository root for GitHub Pages branch publishing.

GitHub Pages is currently configured to serve `/` from `main`, so the live
workflow writes the public site files there while keeping source files under
`dashboard/`.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_ROOT = REPO_ROOT / "dashboard"
DEFAULT_OUTPUT = REPO_ROOT

FILES = [
    ("index.html", "index.html"),
    ("app.js", "app.js"),
    ("public-calculator.js", "public-calculator.js"),
    ("styles.css", "styles.css"),
    ("data/daily.json", "data/daily.json"),
    ("data/refresh-status.json", "data/refresh-status.json"),
    ("data/sample.json", "data/sample.json"),
]


def build_static_site(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for source_rel, target_rel in FILES:
        source = DASHBOARD_ROOT / source_rel
        target = output_dir / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Output directory for public site files")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    build_static_site(out)
    print(f"Wrote GitHub Pages static site to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
