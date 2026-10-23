#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
h_path = root / 'OpenClaw/Engine/Resource/ResourceCache.h'
cpp_path = root / 'OpenClaw/Engine/Resource/ResourceCache.cpp'

h = h_path.read_text(encoding='utf-8')
member_anchor = '    ResourceHandleList _lruList;\n'
member_repl = '    ResourceHandleList _lruList;\n    std::map<std::string, ResourceHandleList::iterator> _lruIterators;\n'
if member_anchor not in h:
    raise SystemExit('ResourceCache LRU member anchor not found')
h = h.replace(member_anchor, member_repl, 1)
h_path.write_text(h, encoding='utf-8', newline='\n')

cpp = cpp_path.read_text(encoding='utf-8')

load_old = '''    _lruList.push_front(handle);\n    _resourceMap[r->GetName()] = handle;\n\n    return handle;\n}\n'''
load_new = '''    _lruList.push_front(handle);\n    _lruIterators[handle->GetName()] = _lruList.begin();\n    _resourceMap[r->GetName()] = handle;\n\n    return handle;\n}\n'''
if load_old not in cpp:
    raise SystemExit('ResourceCache Load LRU anchor not found')
cpp = cpp.replace(load_old, load_new, 1)

update_old = '''void ResourceCache::Update(std::shared_ptr<ResourceHandle> handle)\n{\n    _lruList.remove(handle);\n    _lruList.push_front(handle);\n}\n'''
update_new = '''void ResourceCache::Update(std::shared_ptr<ResourceHandle> handle)\n{\n    // std::list::remove scans the whole cache on every hit. During WASM level\n    // construction the same images/animations are touched thousands of times,\n    // turning cache hits into an O(n) hot path. Keep the iterator for O(log n)\n    // lookup + O(1) erase/splice-equivalent movement instead.\n    auto pos = _lruIterators.find(handle->GetName());\n    if (pos != _lruIterators.end())\n    {\n        _lruList.erase(pos->second);\n    }\n    else\n    {\n        // Defensive fallback for any handle created before iterator tracking.\n        _lruList.remove(handle);\n    }\n    _lruList.push_front(handle);\n    _lruIterators[handle->GetName()] = _lruList.begin();\n}\n'''
if update_old not in cpp:
    raise SystemExit('ResourceCache Update anchor not found')
cpp = cpp.replace(update_old, update_new, 1)

free_one_old = '''    _lruList.pop_back();\n    _resourceMap.erase(handle->GetName());\n}\n'''
free_one_new = '''    std::string handleName = handle->GetName();\n    _lruList.pop_back();\n    _lruIterators.erase(handleName);\n    _resourceMap.erase(handleName);\n}\n'''
if free_one_old not in cpp:
    raise SystemExit('ResourceCache FreeOneResource anchor not found')
cpp = cpp.replace(free_one_old, free_one_new, 1)

free_old = '''void ResourceCache::Free(std::shared_ptr<ResourceHandle> gonner)\n{\n    _lruList.remove(gonner);\n    _resourceMap.erase(gonner->GetName());\n}\n'''
free_new = '''void ResourceCache::Free(std::shared_ptr<ResourceHandle> gonner)\n{\n    const std::string name = gonner->GetName();\n    auto pos = _lruIterators.find(name);\n    if (pos != _lruIterators.end())\n    {\n        _lruList.erase(pos->second);\n        _lruIterators.erase(pos);\n    }\n    else\n    {\n        _lruList.remove(gonner);\n    }\n    _resourceMap.erase(name);\n}\n'''
if free_old not in cpp:
    raise SystemExit('ResourceCache Free anchor not found')
cpp = cpp.replace(free_old, free_new, 1)

cpp_path.write_text(cpp, encoding='utf-8', newline='\n')

if '_lruIterators[handle->GetName()]' not in cpp or '_lruIterators' not in h:
    raise SystemExit('ResourceCache LRU iterator optimization was not injected')

print('ResourceCache LRU iterator optimization applied successfully.')
