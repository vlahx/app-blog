#!/usr/bin/env python3
"""Generează arhive .zip pentru upload în Admin → Plugin-uri."""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packaging" / "plugins"
OUT = ROOT / "dist" / "plugins"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in sorted(p.name for p in PACK.iterdir() if p.is_dir() and not p.name.startswith("_")):
        src_dir = PACK / name
        zpath = OUT / f"{name}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(src_dir.rglob("*")):
                if f.is_file():
                    arc = f.relative_to(PACK)
                    zf.write(f, arcname=str(arc).replace("\\", "/"))
        print(f"Scris: {zpath}")


if __name__ == "__main__":
    main()
