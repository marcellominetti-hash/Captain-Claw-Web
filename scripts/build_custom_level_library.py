#!/usr/bin/env python3
"""Build the private Android custom-level library from complete_level_pack.zip.

The input archive is never committed.  The output layout is designed to be
copied into android/app/src/main/assets/www/custom-levels/ before the private
APK is signed:

  custom-levels/manifest.json
  custom-levels/packs/<id>.zip

Each pack contains one WWD at the original LEVELn/WORLDS/WORLD.WWD path plus
only the private override directory belonging to that level, so different
custom levels cannot contaminate one another.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath


def usage() -> None:
    raise SystemExit("usage: build_custom_level_library.py <complete_level_pack.zip> <output-dir>")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return (slug[:56] or "level")


def level_id(title: str) -> str:
    digest = hashlib.sha1(title.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"{slugify(title)}-{digest}"


def detect_base_level(data: bytes, name: str) -> int:
    # WWD properties and resource references contain paths such as LEVEL3/TILES
    # and LEVEL3/IMAGES.  Counting those references is considerably safer than
    # guessing from the filename.  All files in the supplied pack were found to
    # expose a single dominant LEVEL1..14 family.
    upper = data.upper()
    matches = re.findall(rb"LEVEL\s*(1[0-4]|[1-9])(?=[\\/\x00])", upper)
    counts = Counter(int(m) for m in matches)

    # Some editors store strings as UTF-16LE.  Fold those into the same count.
    try:
        decoded16 = data.decode("utf-16le", errors="ignore").upper()
        for m in re.findall(r"LEVEL\s*(1[0-4]|[1-9])(?=[\\/\x00])", decoded16):
            counts[int(m)] += 1
    except Exception:
        pass

    if not counts:
        raise RuntimeError(f"cannot determine base LEVEL1..14 for {name!r}")

    ranked = counts.most_common()
    best_level, best_count = ranked[0]
    if len(ranked) > 1 and ranked[1][1] == best_count:
        raise RuntimeError(f"ambiguous base level for {name!r}: {dict(counts)}")
    return best_level


def safe_relative(path: str) -> str:
    parts = [p for p in PurePosixPath(path.replace("\\", "/")).parts if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise RuntimeError(f"unsafe archive path: {path!r}")
    return "/".join(parts)


def main() -> None:
    if len(sys.argv) != 3:
        usage()

    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    packs_dir = output / "packs"
    packs_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(source, "r") as src:
        names = src.namelist()
        root_wwds = [n for n in names if n.lower().endswith(".wwd") and "/" not in n.strip("/")]
        if not root_wwds:
            raise RuntimeError("no root .WWD files found")

        entries = []
        base_counts = Counter()
        special_count = 0

        for index, wwd_name in enumerate(sorted(root_wwds, key=str.casefold), start=1):
            title = Path(wwd_name).stem
            raw_wwd = src.read(wwd_name)
            base = detect_base_level(raw_wwd, wwd_name)
            base_counts[base] += 1

            ident = level_id(title)
            pack_name = ident + ".zip"
            pack_path = packs_dir / pack_name
            private_prefix = title.rstrip("/") + "/"
            private_files = [n for n in names if n.startswith(private_prefix) and not n.endswith("/")]
            has_assets = bool(private_files)
            if has_assets:
                special_count += 1

            world_path = f"LEVEL{base}/WORLDS/WORLD.WWD"
            written = {world_path.casefold()}

            with zipfile.ZipFile(pack_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as dst:
                # Put the selected level in the exact campaign slot expected by
                # the patched engine.  This entry always wins over an accidental
                # WORLD.WWD copy in the private override directory.
                dst.writestr(world_path, raw_wwd)

                for member in private_files:
                    rel = safe_relative(member[len(private_prefix):])
                    if rel.casefold() in written:
                        continue
                    written.add(rel.casefold())
                    dst.writestr(rel, src.read(member))

            entries.append({
                "id": ident,
                "title": title,
                "baseLevel": base,
                "archive": f"custom-levels/packs/{pack_name}",
                "hasAssets": has_assets,
                "packageBytes": pack_path.stat().st_size,
            })

            if index % 50 == 0 or index == len(root_wwds):
                print(f"packed {index}/{len(root_wwds)}")

    manifest = {
        "version": 1,
        "count": len(entries),
        "specialAssetLevels": special_count,
        "baseLevelDistribution": {str(k): base_counts[k] for k in sorted(base_counts)},
        "levels": entries,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    total_bytes = sum((packs_dir / (e["id"] + ".zip")).stat().st_size for e in entries)
    print(f"manifest: {output / 'manifest.json'}")
    print(f"levels: {len(entries)}")
    print(f"levels with private assets: {special_count}")
    print(f"pack bytes: {total_bytes}")
    print(f"base distribution: {dict(sorted(base_counts.items()))}")


if __name__ == "__main__":
    main()
