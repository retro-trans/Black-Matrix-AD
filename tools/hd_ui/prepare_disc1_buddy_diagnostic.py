"""Prepare a separate offline Flycast profile; never start or alter user apps."""
import configparser
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/disc1-buddy-diagnostic-v1'
SOURCE = ROOT / 'build/skies-vga-compat-v2/play'
EXE_SHA = 'f41c1a4243274caf9a183114bd610407835521a011a48b18326e5e957e6f4e6b'


def settings():
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    cfg.read(SOURCE / 'emu.cfg', encoding='utf-8')
    frozen = json.loads((ROOT / 'build/skies-rayblade-font-v3/renderer-settings.json').read_text())
    cfg['config'].update(frozen['settings'])
    cfg['config'].update({
        'LuaFileName': 'buddy-diagnostic.lua',
        'Dreamcast.BiosPath': str(OUT / 'bios'),
        'Dreamcast.ContentPath': str(ROOT / 'output/patched-discs-2026-11-01/disc1'),
        'Dreamcast.SavePath': str(OUT / 'data'),
        'Dreamcast.SavestatePath': str(OUT / 'data'),
        'Dreamcast.VMUPath': str(OUT / 'data'),
        'Dreamcast.AutoLoadState': 'no', 'Dreamcast.AutoSaveState': 'no',
        'Dreamcast.Cable': '0', 'Dreamcast.Region': '0',
        'DiscordPresence': 'no', 'FetchBoxart': 'no', 'UploadCrashLogs': 'no',
        'Debug.GDBEnabled': 'no', 'UseReios': 'no',
        'rend.CustomTextures': 'no', 'rend.DumpTextures': 'no',
    })
    cfg['achievements']['Enabled'] = 'no'
    cfg['network'].update({'Enable': 'no', 'DCNet': 'no', 'EnableUPnP': 'no',
                           'NetworkOutput': 'no', 'GGPO': 'no', 'Stats': 'no'})
    cfg['window'].update({'fullscreen': 'no', 'maximized': 'no',
                          'width': '960', 'height': '720'})
    return cfg


def run():
    if OUT.exists():
        raise ValueError('Preserve previous diagnostic profile')
    emulator = SOURCE / 'flycast.exe'
    if hashlib.sha256(emulator.read_bytes()).hexdigest() != EXE_SHA:
        raise ValueError('Unexpected local emulator')
    payload = (ROOT / 'build/disc1-reconstructed-vga-v1/final-payloads/1ST_READ.BIN').read_bytes()
    if hashlib.sha256(payload).hexdigest() != '94606624f94c22b12b7bc5b48da513c222c19941722fbbae0511b2f1d7e20e8b':
        raise ValueError('Unexpected game executable')
    cfg = settings()
    lua = (ROOT / 'tools/hd_ui/disc1_buddy_diagnostic.lua').read_text(encoding='utf-8')
    words = ', '.join(hex(word) for word in struct.unpack('<16I', payload[:64]))
    lua = lua.replace('local expected = {0x00000000}', 'local expected = {' + words + '}')
    for name in ('bios/dc_boot.bin', 'bios/dc_flash.bin', 'data/dc_nvmem.bin'):
        if not (SOURCE / name).is_file():
            raise ValueError('Missing local BIOS initialization file: ' + name)
    OUT.mkdir()
    (OUT / 'bios').mkdir()
    (OUT / 'data').mkdir()
    copied = ['flycast.exe', 'bios/dc_boot.bin', 'bios/dc_flash.bin', 'data/dc_nvmem.bin']
    for name in copied:
        shutil.copy2(SOURCE / name, OUT / name)
        if (SOURCE / name).read_bytes() != (OUT / name).read_bytes():
            raise ValueError('Diagnostic copy differs: ' + name)
    with (OUT / 'emu.cfg').open('x', encoding='utf-8') as stream:
        cfg.write(stream)
    with (OUT / 'buddy-diagnostic.lua').open('x', encoding='utf-8') as stream:
        stream.write(lua)
    manifest = dict(status='prepared-not-runtime-tested', emulator_sha256=EXE_SHA,
                    guest_executable_sha256=hashlib.sha256(payload).hexdigest(),
                    guest_writes=False, automated_input=False, network_enabled=False,
                    user_saves_imported=False, original_disc_modified=False,
                    copied_local_files=copied, capture_trigger='pause callback before error teardown')
    with (OUT / 'profile.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    run()
