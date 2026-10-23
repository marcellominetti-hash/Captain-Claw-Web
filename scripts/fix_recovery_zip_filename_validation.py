#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
path = root / "Build_Release/asset-loader.js"
text = path.read_text(encoding="utf-8")

old = r"/^CLAW\.REZ$/i"
new = r"/^CLAW_ASSETS\.ZIP$/i"
count = text.count(old)
if count < 2:
    raise SystemExit(f"Expected at least 2 CLAW.REZ filename validators, found {count}")

text = text.replace(old, new)
path.write_text(text, encoding="utf-8", newline="\n")

if old in text:
    raise SystemExit("Legacy CLAW.REZ filename validator still present")
if text.count(new) < 2:
    raise SystemExit("CLAW_ASSETS.ZIP filename validator not installed correctly")

print(f"Fixed {count} ZIP filename validator(s).")
