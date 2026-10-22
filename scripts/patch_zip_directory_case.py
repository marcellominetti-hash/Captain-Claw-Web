#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
path = root / 'OpenClaw/Engine/Resource/ResourceCache.cpp'
text = path.read_text(encoding='utf-8')

needle = '''    std::string dirPath = directoryPath;\n    // Our directories beging and end with "/"\n'''
replacement = '''    std::string dirPath = directoryPath;\n    std::replace(dirPath.begin(), dirPath.end(), '\\\\', '/');\n    std::transform(dirPath.begin(), dirPath.end(), dirPath.begin(),\n                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });\n    // ZIP index keys are stored in lowercase and use forward slashes.\n    // Our directories begin and end with "/".\n'''
if needle not in text:
    raise SystemExit('ResourceZipArchive directory lookup anchor not found')
text = text.replace(needle, replacement, 1)
path.write_text(text, encoding='utf-8', newline='\n')

print('ZIP directory lookup normalization patch applied successfully.')
