#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
path = root / 'OpenClaw/Engine/Actor/Components/RenderComponent.cpp'
text = path.read_text(encoding='utf-8')

old = '''        const char* imagesPath = pImagePathElem->GetText();\n        assert(imagesPath != NULL);\n\n        // Get all files residing in given directory\n        // !!! THIS ASSUMES THAT WE ONLY WANT IMAGES FROM THIS DIRECTORY. IT IGNORES ALL NESTED DIRECTORIES !!!\n        // Maybe add recursive algo to libwap\n        std::string imageDir = std::string(imagesPath);\n        //imageDir = imageDir.substr(0, imageDir.find("*")); // Get rid of everything after '*' including '*'\n        imageDir = imageDir.substr(0, imageDir.find_last_of("/")); // Get rid of filenames - get just path to the final directory\n'''
new = '''        const char* imagesPath = pImagePathElem->GetText();\n        assert(imagesPath != NULL);\n\n        // Original WAP data may contain Windows separators. Canonicalize the\n        // pattern before directory extraction and wildcard matching so the\n        // browser ZIP backend always sees the same POSIX-style path.\n        std::string normalizedImagePath(imagesPath);\n        std::replace(normalizedImagePath.begin(), normalizedImagePath.end(), '\\\\', '/');\n\n        // Get all files residing in given directory\n        // !!! THIS ASSUMES THAT WE ONLY WANT IMAGES FROM THIS DIRECTORY. IT IGNORES ALL NESTED DIRECTORIES !!!\n        // Maybe add recursive algo to libwap\n        std::string imageDir = normalizedImagePath;\n        //imageDir = imageDir.substr(0, imageDir.find("*")); // Get rid of everything after '*' including '*'\n        imageDir = imageDir.substr(0, imageDir.find_last_of("/")); // Get rid of filenames - get just path to the final directory\n'''
if old not in text:
    raise SystemExit('RenderComponent image-path directory block not found')
text = text.replace(old, new, 1)

old_pattern = '''        std::string imageDirLowercase(imagesPath);\n        std::transform(imageDirLowercase.begin(), imageDirLowercase.end(), imageDirLowercase.begin(), (int(*)(int)) std::tolower);\n'''
new_pattern = '''        std::string imageDirLowercase(normalizedImagePath);\n        std::transform(imageDirLowercase.begin(), imageDirLowercase.end(), imageDirLowercase.begin(), (int(*)(int)) std::tolower);\n'''
if old_pattern not in text:
    raise SystemExit('RenderComponent image wildcard block not found')
text = text.replace(old_pattern, new_pattern, 1)

path.write_text(text, encoding='utf-8', newline='\n')
print('Render image path normalization patch applied successfully.')
