#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
path = root / 'OpenClaw/Engine/Util/Converters.cpp'
text = path.read_text(encoding='utf-8')
old = '''            if (wwdObject->height == 0)\n            {\n                wwdObject->height = 1;\n            }\n            assert(wwdObject->height > 0 && wwdObject->height <= 8 && "Invalid stacked crate height. Should be between 1 and 8");\n'''
new = '''            // Fan-made WWDs can intentionally contain taller StackedCrates than\n            // the original campaign's 1..8 assumption. Keep the authored height\n            // while guarding against invalid/corrupt values.\n            if (wwdObject->height <= 0)\n            {\n                wwdObject->height = 1;\n            }\n            if (wwdObject->height > 256)\n            {\n                LOG_WARNING("StackedCrates height above safety limit; clamping to 256");\n                wwdObject->height = 256;\n            }\n'''
if old not in text:
    raise SystemExit('StackedCrates assertion block not found')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8', newline='\n')
print('STACKFIX source patch applied.')
