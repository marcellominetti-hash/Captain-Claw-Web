#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()


def read(rel):
    return (root / rel).read_text(encoding='utf-8')


def write(rel, text):
    (root / rel).write_text(text, encoding='utf-8', newline='\n')


# ZIP entries are indexed with POSIX separators, while original Captain Claw
# resource paths can contain Windows backslashes. Normalize both archive keys
# and lookups so the browser build behaves like the original resource backend.
zip_path = 'OpenClaw/Engine/Resource/ZipFile.cpp'
zip_cpp = read(zip_path)

helper_anchor = '''static char* string_to_lowercase(char* s)\n{\n    char* tmp = s;\n\n    for (; *tmp; ++tmp) {\n        *tmp = tolower((unsigned char)*tmp);\n    }\n\n    return s;\n}\n'''
helper_replacement = helper_anchor + r'''

static std::string NormalizeZipPath(const std::string& input)
{
    std::string normalized;
    normalized.reserve(input.size() + 1);

    for (unsigned char raw : input)
    {
        char c = static_cast<char>(std::tolower(raw));
        if (c == '\')
        {
            c = '/';
        }

        // Collapse duplicate separators. ZIP keys use one forward slash.
        if (c == '/' && !normalized.empty() && normalized.back() == '/')
        {
            continue;
        }
        normalized.push_back(c);
    }

    // Remove harmless leading ./ segments before adding the canonical root.
    while (normalized.size() >= 2 && normalized[0] == '.' && normalized[1] == '/')
    {
        normalized.erase(0, 2);
    }

    if (!normalized.empty() && normalized[0] != '/')
    {
        normalized.insert(normalized.begin(), '/');
    }

    return normalized;
}
'''
if helper_anchor not in zip_cpp:
    raise SystemExit('ZipFile.cpp lowercase helper anchor not found')
zip_cpp = zip_cpp.replace(helper_anchor, helper_replacement, 1)

init_old = '''            string_to_lowercase(fileName);\n            std::string spath = fileName;\n            spath.insert(0, "/");\n            m_ZipContentsMap[spath] = i;\n'''
init_new = '''            std::string spath = NormalizeZipPath(fileName);\n            m_ZipContentsMap[spath] = i;\n'''
if init_old not in zip_cpp:
    raise SystemExit('ZipFile.cpp archive-index path block not found')
zip_cpp = zip_cpp.replace(init_old, init_new, 1)

find_old = '''int ZipFile::Find(const std::string &path) const\n{\n    std::string lowerCase = path;\n    std::transform(lowerCase.begin(), lowerCase.end(), lowerCase.begin(), (int(*)(int)) std::tolower);\n    // In case the name doesnt start with forward flash, e.g. path == "folder1/folder2/file1", convert it\n    // to "/folder1/folder2/file1 format\n    if (lowerCase.size() > 0 && lowerCase[0] != '/')\n    {\n        lowerCase.insert(0, "/");\n    }\n    ZipContentsMap::const_iterator i = m_ZipContentsMap.find(lowerCase);\n    if (i == m_ZipContentsMap.end())\n        return -1;\n\n    return i->second;\n}\n'''
find_new = '''int ZipFile::Find(const std::string &path) const\n{\n    const std::string normalizedPath = NormalizeZipPath(path);\n    ZipContentsMap::const_iterator i = m_ZipContentsMap.find(normalizedPath);\n    if (i == m_ZipContentsMap.end())\n        return -1;\n\n    return i->second;\n}\n'''
if find_old not in zip_cpp:
    raise SystemExit('ZipFile.cpp Find block not found')
zip_cpp = zip_cpp.replace(find_old, find_new, 1)
write(zip_path, zip_cpp)

# Directory enumeration bypasses ZipFile::Find(), so normalize this path too.
cache_path = 'OpenClaw/Engine/Resource/ResourceCache.cpp'
cache_cpp = read(cache_path)
dir_old = '''    std::string dirPath = directoryPath;\n    // Our directories beging and end with "/"\n    if (dirPath.size() > 0 && dirPath[0] != '/')\n    {\n        dirPath.insert(0, "/");\n    }\n    if (dirPath.back() != '/')\n    {\n        dirPath += "/";\n    }\n'''
dir_new = '''    std::string dirPath = directoryPath ? directoryPath : "";\n    std::transform(dirPath.begin(), dirPath.end(), dirPath.begin(), [](unsigned char c) {\n        return static_cast<char>(std::tolower(c));\n    });\n    std::replace(dirPath.begin(), dirPath.end(), '\\\\', '/');\n\n    std::string normalizedDirPath;\n    normalizedDirPath.reserve(dirPath.size() + 2);\n    for (char c : dirPath)\n    {\n        if (c == '/' && !normalizedDirPath.empty() && normalizedDirPath.back() == '/')\n        {\n            continue;\n        }\n        normalizedDirPath.push_back(c);\n    }\n    dirPath.swap(normalizedDirPath);\n\n    while (dirPath.size() >= 2 && dirPath[0] == '.' && dirPath[1] == '/')\n    {\n        dirPath.erase(0, 2);\n    }\n\n    // Our directories begin and end with "/".\n    if (dirPath.empty() || dirPath[0] != '/')\n    {\n        dirPath.insert(0, "/");\n    }\n    if (dirPath.back() != '/')\n    {\n        dirPath += "/";\n    }\n'''
if dir_old not in cache_cpp:
    raise SystemExit('ResourceCache.cpp ZIP directory lookup block not found')
cache_cpp = cache_cpp.replace(dir_old, dir_new, 1)
write(cache_path, cache_cpp)

print('ZIP path normalization patch applied successfully.')
