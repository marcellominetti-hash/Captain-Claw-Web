#!/usr/bin/env python3
"""Apply deployment branding without modifying the upstream game engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path

site = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")

TEXT_REPLACEMENTS = (
    ("Claw Web", "Capitan Artiglio Web"),
    (
        "Captain Claw (1997) reimplemented for the browser - unofficial fan project",
        "Capitan Artiglio nel browser - deployment personale basato su OpenClaw",
    ),
)

for name in ("index.html", "claw-web.html"):
    path = site / name
    if not path.exists():
        raise SystemExit(f"Missing expected upstream file: {path}")
    text = path.read_text(encoding="utf-8")
    for old, new in TEXT_REPLACEMENTS:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")

manifest_path = site / "site.webmanifest"
if manifest_path.exists():
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["name"] = "Capitan Artiglio Web"
    data["short_name"] = "Artiglio Web"
    data["description"] = (
        "Capitan Artiglio nel browser, basato sul motore open-source OpenClaw. "
        "Gli asset originali non sono inclusi."
    )
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

# Small deployment marker, useful when debugging which build is actually open.
(site / "deployment.json").write_text(
    json.dumps(
        {
            "name": "Capitan Artiglio Web",
            "asset_policy": "CLAW.REZ is supplied locally by the player and is never deployed",
            "runtime": "arthurboss/claw-web (pinned by workflow)",
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)
