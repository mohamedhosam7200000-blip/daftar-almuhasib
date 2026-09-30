"""Build the offline release zip: python offline/package.py

Produces offline/build/khabeer-offline.zip containing only what the
standalone app needs (no Anthropic code). Run `npm run build` in web/ first.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "offline" / "build" / "khabeer-offline.zip"
PREFIX = "khabeer-offline"

FILES = {
    "Khabeer.bat": ROOT / "offline" / "Khabeer.bat",
    "launch.ps1": ROOT / "offline" / "launch.ps1",
    "README-AR.txt": ROOT / "offline" / "README-AR.txt",
    "khabeer/__init__.py": ROOT / "khabeer" / "__init__.py",
    "khabeer/calc.py": ROOT / "khabeer" / "calc.py",
    "khabeer/prompts.py": ROOT / "khabeer" / "prompts.py",
}


def main() -> int:
    ui = ROOT / "web" / "dist-local"
    if not (ui / "index.html").exists():
        print("web/dist-local is missing: run `npm install && npm run build` in web/ first.")
        return 1
    files = dict(FILES)
    for p in sorted((ROOT / "khabeer" / "local").glob("*.py")):
        files[f"khabeer/local/{p.name}"] = p
    for p in sorted(ui.rglob("*")):
        if p.is_file():
            files[f"web/dist-local/{p.relative_to(ui).as_posix()}"] = p

    for arc, src in files.items():
        if src.suffix == ".py" and "anthropic" in src.read_text(encoding="utf-8").split('"""', 2)[-1]:
            print(f"refusing to package {arc}: it references anthropic")
            return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, src in files.items():
            z.write(src, f"{PREFIX}/{arc}")
    print(f"{OUT}  ({len(files)} files, {OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
