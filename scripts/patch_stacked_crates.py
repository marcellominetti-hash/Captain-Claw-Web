#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
path = root / 'OpenClaw/Engine/Util/Converters.cpp'
text = path.read_text(encoding='utf-8')
old = 'assert(wwdObject->height > 0 && wwdObject->height <= 8 && "Invalid stacked crate height. Should be between 1 and 8");'
new = '''if (wwdObject->height < 1 || wwdObject->height > 256)\n            {\n                LOG_ERROR("Invalid stacked crate height: " + ToStr(wwdObject->height));\n                wwdObject->height = 1;\n            }'''
if old not in text:
    raise SystemExit('Stacked-crate assertion not found')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8', newline='\n')
print('Stacked-crate height compatibility patch applied (1..256).')
