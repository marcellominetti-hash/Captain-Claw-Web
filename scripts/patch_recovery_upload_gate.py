#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
loader_path = root / "Build_Release/asset-loader.js"
sw_path = root / "Build_Release/sw.js"

loader = loader_path.read_text(encoding="utf-8")

# Remove filename-based rejection from both selection validation and upload.
# The archive is validated by size and ZIP magic bytes instead.
loader, n1 = re.subn(
    r"\n\s*if \(!file\.name\.match\(/\^CLAW(?:_ASSETS)?(?:\\)?\.ZIP\$/i\)\) \{.*?\n\s*\}\n",
    "\n",
    loader,
    count=2,
    flags=re.S,
)

# Be robust to the original CLAW.REZ gate if the earlier patch changes.
loader, n2 = re.subn(
    r"\n\s*if \(!file\.name\.match\(/\^CLAW(?:\\)?\.REZ\$/i\)\) \{.*?\n\s*\}\n",
    "\n",
    loader,
    count=2,
    flags=re.S,
)

if n1 + n2 < 2:
    raise SystemExit(f"Expected to remove two filename gates, removed {n1+n2}")

# Keep user-facing copy accurate: name is irrelevant; ZIP content is what matters.
loader = loader.replace(
    "wrong name, empty, wildly wrong size, or missing the RezMgr",
    "empty, wildly wrong size, or missing the ZIP",
)
loader = loader.replace(
    "The file must be named CLAW_ASSETS.ZIP (from the original Captain Claw game).",
    "Select the ZIP archive containing the extracted Captain Claw game assets.",
)
loader = loader.replace(
    "Error: File must be named CLAW_ASSETS.ZIP",
    "Error: Invalid game-data ZIP",
)

loader_path.write_text(loader, encoding="utf-8", newline="\n")

# Force a fresh shell cache for this recovery build. recovery-v2 also uses a new
# SW scope, so old /recovery/ clients cannot control it.
if sw_path.exists():
    sw = sw_path.read_text(encoding="utf-8")
    sw, count = re.subn(
        r'const CACHE_VERSION = "v[0-9]+";',
        'const CACHE_VERSION = "recovery-v2-1";',
        sw,
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not bump recovery service-worker cache version")
    sw_path.write_text(sw, encoding="utf-8", newline="\n")

# Assertions: there must be no filename gate left.
final = loader_path.read_text(encoding="utf-8")
if re.search(r"file\.name\.match", final):
    raise SystemExit("A filename-based upload gate is still present")
if "hasZipSignature(file)" not in final:
    raise SystemExit("ZIP signature validation is missing")

print("Recovery upload gate removed; ZIP content validation retained.")
