#!/usr/bin/env python3
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path('.')
MANIFEST_PATH = ROOT / 'data' / 'custom-levels-menu.json'
UI_H = ROOT / 'OpenClaw/Engine/UserInterface/UserInterface.h'
UI_CPP = ROOT / 'OpenClaw/Engine/UserInterface/UserInterface.cpp'
HUMAN_CPP = ROOT / 'OpenClaw/Engine/UserInterface/HumanView.cpp'
MENU_XML = ROOT / 'Build_Release/ASSETS/MENU.xml'
LABEL_DIR = ROOT / 'Build_Release/ASSETS/CUSTOM_LEVELS/LABELS'
ASSET_DIR = ROOT / 'Build_Release/ASSETS/CUSTOM_LEVELS'

PER_PAGE = 6
CUSTOM_LEVEL_BASE = 1000

manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
titles = manifest['titles']
if len(titles) != 623:
    raise SystemExit(f'Expected 623 custom levels, got {len(titles)}')

pages = math.ceil(len(titles) / PER_PAGE)
extra_page_names = [f'MenuPage_CustomLevels_{i:03d}' for i in range(2, pages + 1)]

h = UI_H.read_text(encoding='utf-8')
marker_unused = '    MenuPage_SinglePlayer_LoadCustomLevel, // Unused\n'
marker_plain = '    MenuPage_SinglePlayer_LoadCustomLevel,\n'
marker = marker_unused if marker_unused in h else marker_plain
if marker not in h:
    raise SystemExit('Custom level enum marker not found in UserInterface.h')
block = '    MenuPage_SinglePlayer_LoadCustomLevel,\n' + ''.join(f'    {name},\n' for name in extra_page_names)
h = h.replace(marker, block, 1)
UI_H.write_text(h, encoding='utf-8')

cpp = UI_CPP.read_text(encoding='utf-8')
map_marker = '    { "MenuPage_SinglePlayer_LoadCustomLevel",  MenuPage_SinglePlayer_LoadCustomLevel },\n'
if map_marker not in cpp:
    raise SystemExit('Custom level page map marker not found in UserInterface.cpp')
map_block = map_marker + ''.join(f'    {{ "{name}", {name} }},\n' for name in extra_page_names)
cpp = cpp.replace(map_marker, map_block, 1)
UI_CPP.write_text(cpp, encoding='utf-8')

human = HUMAN_CPP.read_text(encoding='utf-8')
human_marker = ('        bool isNewGame = pCastEventData->GetIsNewGame();\n'
                '        int levelNumber = pCastEventData->GetLevelNumber();\n'
                '        int checkpointNumber = pCastEventData->GetCheckpointNumber();\n')
if human_marker not in human:
    raise SystemExit('LoadGameDelegate marker not found in HumanView.cpp')
human_extra = human_marker + r'''
#ifdef __EMSCRIPTEN__
        // Capitan Artiglio native custom-level menu. MENU.xml uses normal
        // LoadGame events with reserved level numbers 1000..1622. Intercept
        // before the campaign loader and let JS restart OpenClaw with the
        // selected CUSTOM_LEVEL.ZIP mounted before main().
        if (levelNumber >= 1000 && levelNumber < 2000)
        {
            const int customIndex = levelNumber - 1000;
            EM_ASM({
                const idx = $0;
                try {
                    if (window.CapitanCustomMenu && typeof window.CapitanCustomMenu.launch === 'function') {
                        window.CapitanCustomMenu.launch(idx);
                    } else {
                        console.error('[CapitanCustomMenu] launch bridge missing', idx);
                    }
                } catch (e) {
                    console.error('[CapitanCustomMenu] launch failed', e);
                }
            }, customIndex);
            return;
        }
#endif
'''
human = human.replace(human_marker, human_extra, 1)
HUMAN_CPP.write_text(human, encoding='utf-8')

menu = MENU_XML.read_text(encoding='utf-8')
if '<!-- CAPITAN_ARTIGLIO_CUSTOM_LEVEL_PAGES -->' in menu:
    raise SystemExit('Custom menu pages already generated')

def esc_block():
    return '''        <KeyboardEvent>\n            <KeyType>Escape</KeyType>\n            <GeneratedEvent>\n                <Type>SwitchPage</Type>\n                <PageName>MenuPage_SinglePlayer</PageName>\n            </GeneratedEvent>\n        </KeyboardEvent>\n'''

def image_item(name, inactive, active, x, y, state, event_xml):
    return f'''        <MenuItem>\n            <Name>{name}</Name>\n            <Type>Button</Type>\n            <State>{state}</State>\n            <InactiveImage>{inactive}</InactiveImage>\n            <ActiveImage>{active}</ActiveImage>\n            <Position x="{x}" y="{y}" />\n            <GeneratedEvent>\n{event_xml}\n            </GeneratedEvent>\n        </MenuItem>\n'''

blocks = ['\n    <!-- CAPITAN_ARTIGLIO_CUSTOM_LEVEL_PAGES -->\n']
for page_idx in range(pages):
    page_name = 'MenuPage_SinglePlayer_LoadCustomLevel' if page_idx == 0 else f'MenuPage_CustomLevels_{page_idx+1:03d}'
    start = page_idx * PER_PAGE
    end = min(start + PER_PAGE, len(titles))
    blocks.append('    <MenuPage>\n')
    blocks.append(f'        <PageName>{page_name}</PageName>\n')
    blocks.append(esc_block())
    blocks.append('''        <MenuItem>\n            <Name>CUSTOM_LEVELS_TITLE</Name>\n            <Type>Text</Type>\n            <State>Inactive</State>\n            <InactiveImage>/CUSTOM_LEVELS/title.png</InactiveImage>\n            <Position x="160" y="145" />\n        </MenuItem>\n''')
    for row, level_idx in enumerate(range(start, end)):
        y = 188 + row * 31
        label_num = level_idx + 1
        event = ('                <Type>LoadGame</Type>\n'
                 '                <IsNewGame>true</IsNewGame>\n'
                 f'                <LevelNumber>{CUSTOM_LEVEL_BASE + level_idx}</LevelNumber>\n'
                 '                <CheckpointNumber>0</CheckpointNumber>')
        blocks.append(image_item(f'CUSTOM_LEVEL_{label_num:03d}',
            f'/CUSTOM_LEVELS/LABELS/{label_num:03d}_inactive.png',
            f'/CUSTOM_LEVELS/LABELS/{label_num:03d}_active.png',
            110, y, 'Active' if row == 0 else 'Inactive', event))
    nav_y = 388
    if page_idx > 0:
        prev_name = 'MenuPage_SinglePlayer_LoadCustomLevel' if page_idx == 1 else f'MenuPage_CustomLevels_{page_idx:03d}'
        event = '                <Type>SwitchPage</Type>\n' + f'                <PageName>{prev_name}</PageName>'
        blocks.append(image_item('CUSTOM_PREV', '/CUSTOM_LEVELS/prev_inactive.png', '/CUSTOM_LEVELS/prev_active.png', 92, nav_y, 'Inactive', event))
    if page_idx < pages - 1:
        next_name = f'MenuPage_CustomLevels_{page_idx+2:03d}'
        event = '                <Type>SwitchPage</Type>\n' + f'                <PageName>{next_name}</PageName>'
        blocks.append(image_item('CUSTOM_NEXT', '/CUSTOM_LEVELS/next_inactive.png', '/CUSTOM_LEVELS/next_active.png', 260, nav_y, 'Inactive', event))
    event = '                <Type>SwitchPage</Type>\n                <PageName>MenuPage_SinglePlayer</PageName>'
    blocks.append(image_item('CUSTOM_BACK', '/CUSTOM_LEVELS/back_inactive.png', '/CUSTOM_LEVELS/back_active.png', 428, nav_y, 'Inactive', event))
    blocks.append('    </MenuPage>\n')

if '</GameMenu>' not in menu:
    raise SystemExit('MENU.xml closing marker not found')
menu = menu.replace('</GameMenu>', ''.join(blocks) + '\n</GameMenu>', 1)
MENU_XML.write_text(menu, encoding='utf-8')

LABEL_DIR.mkdir(parents=True, exist_ok=True)
ASSET_DIR.mkdir(parents=True, exist_ok=True)
font_candidates = ['/usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf']
font_path = next((p for p in font_candidates if Path(p).exists()), None)
if font_path:
    font = ImageFont.truetype(font_path, 18)
    title_font = ImageFont.truetype(font_path, 27)
    nav_font = ImageFont.truetype(font_path, 18)
else:
    font = title_font = nav_font = ImageFont.load_default()

def fit_text(draw, text, font_obj, max_width):
    text = str(text).strip()
    if draw.textbbox((0, 0), text, font=font_obj)[2] <= max_width:
        return text
    suffix = '...'
    while text and draw.textbbox((0, 0), text + suffix, font=font_obj)[2] > max_width:
        text = text[:-1]
    return (text + suffix) if text else suffix

def make_label(path, text, active=False, width=420, height=27, font_obj=None):
    font_obj = font_obj or font
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    text = fit_text(d, text, font_obj, width - 16)
    bbox = d.textbbox((0, 0), text, font=font_obj, stroke_width=1)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (width - tw) // 2
    y = (height - th) // 2 - 2
    fill = (255, 236, 126, 255) if active else (222, 188, 82, 255)
    stroke = (63, 35, 10, 255)
    d.text((x + 1, y + 2), text, font=font_obj, fill=(40, 20, 4, 190), stroke_width=1, stroke_fill=(40, 20, 4, 190))
    d.text((x, y), text, font=font_obj, fill=fill, stroke_width=1, stroke_fill=stroke)
    img.save(path)

for idx, title in enumerate(titles, start=1):
    make_label(LABEL_DIR / f'{idx:03d}_inactive.png', title, False)
    make_label(LABEL_DIR / f'{idx:03d}_active.png', title, True)
make_label(ASSET_DIR / 'title.png', 'CUSTOM LEVELS', True, width=320, height=36, font_obj=title_font)
for name, text in [('prev', 'PREV'), ('next', 'NEXT'), ('back', 'BACK')]:
    make_label(ASSET_DIR / f'{name}_inactive.png', text, False, width=120, height=28, font_obj=nav_font)
    make_label(ASSET_DIR / f'{name}_active.png', text, True, width=120, height=28, font_obj=nav_font)

print(f'Generated native custom-level menu: {len(titles)} levels, {pages} pages')
