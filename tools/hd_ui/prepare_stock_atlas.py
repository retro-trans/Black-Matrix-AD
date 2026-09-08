"""Prepare an isolated game-patch experiment using the user's stock Flycast binary."""
import configparser
import argparse
import hashlib
import json
import shutil
import subprocess
import os
from pathlib import Path

import reusable_atlas as atlas
import stock_atlas_pack
import inject
import mainmenu
import battle_menu
import deployment_heading_pack
import font_style
import stance_menu
import field_battle_ui
import bizin_font
import seed_bizin_pack


def main():
    root=atlas.ROOT
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=root/'build/reusable-atlas-ui-r10')
    out=p.parse_args().output.resolve()
    # This generator is deliberately restricted to ignored test artifacts.
    if not out.is_relative_to((root/'build').resolve()) or out==(root/'build').resolve():
        raise ValueError('output must be a dedicated subdirectory of build/')
    if out in ((root/'build/disc').resolve(),(root/'build/stock-atlas-run').resolve()):
        raise ValueError('output cannot be the baseline disc or emulator profile')
    disc=out/'disc';run=root/'build/stock-atlas-run'
    cue=disc/'Black-Matrix Advanced (Japan) (Disc 1).cue'
    if os.name=='nt':
        # Read-only check before modifying ANY output. Do not patch a mounted
        # disc or close the emulator on the user's behalf.
        result=subprocess.run(['powershell.exe','-NoProfile','-Command',
            "@(Get-CimInstance Win32_Process -Filter \"Name = 'flycast.exe'\" | Select-Object -ExpandProperty CommandLine) | ConvertTo-Json -Compress"],
            check=True,capture_output=True,text=True)
        active=json.loads(result.stdout) if result.stdout.strip() else []
        if isinstance(active,str):active=[active]
        target=str(cue).replace('\\','/').casefold()
        for command in active:
            if command and target in command.replace('\\','/').casefold():
                raise RuntimeError('Close the emulator using this test disc before rebuilding it.')
    stock=Path('D:/Program/FlyCast')
    exe,manifest=atlas.patch((root/'build/1ST_READ.vwf.bin').read_bytes(),
                             (root/'extracted/1ST_READ.BIN').read_bytes())
    exe=mainmenu.patch(bytearray(exe))
    battle=battle_menu.patch(exe)
    stance=stance_menu.patch(exe,battle)
    native_font,font_meta=bizin_font.build()
    bizin_font.patch_metrics(exe)
    natural_code=atlas.vwf.build_code(manifest['code_labels']['slot_hook'],
                                    ui_fixes=True,natural_font=True).assemble()
    if atlas.vwf.CODE+len(natural_code)>atlas.vwf.FLOAT_TAB:
        raise ValueError('natural font renderer exceeds its arena')
    exe[atlas.vwf.CODE-atlas.BASE:atlas.vwf.CODE-atlas.BASE+len(natural_code)]=natural_code
    exe=bytes(exe)
    manifest.update(revision=10, font=font_meta, stance_menu=stance, cross_record_spacing=True,
                    yes_no_glyph_height=16, yes_no_top_inset=0, battle_menu_left_padding=10,
                    battle_menu=battle, main_menu_columns=mainmenu.COLS,
                    main_menu_labels=mainmenu.cooking.strings(mainmenu.UI),
                    patched_sha256=hashlib.sha256(exe).hexdigest())
    out.mkdir(parents=True,exist_ok=True)
    payload=out/'1ST_READ.BIN';payload.write_bytes(exe)
    # Copy only on initial setup. Never overwrite VMUs or existing test discs.
    # Subsequent patch updates modify the explicitly isolated Track 3 only.
    # Revision 1's known-good help disc is retained at build/reusable-atlas.
    if not disc.exists():shutil.copytree(root/'build/disc',disc)
    track=disc/'Black-Matrix Advanced (Japan) (Disc 1) (Track 3).bin'
    inject.put(str(track),'1ST_READ.BIN',str(payload))
    with track.open('rb') as f:
        lba,size=inject.find(f,'1ST_READ.BIN'); embedded=inject._extent(f,lba,size)
    if embedded!=exe:raise RuntimeError('disc executable readback failed')
    # Preserve all existing translations in the copied archive, changing only
    # the seven stance-help pages. Never rebuild the archive from vanilla here.
    with track.open('rb') as f:
        lba,size=inject.find(f,'PARAMETA.DAT'); parameters=bytearray(inject._extent(f,lba,size))
    # Permit regenerating our last verified archive when wording changes,
    # but do not accept unrelated user-modified records merely by size.
    previous_manifest=out/'manifest.json'
    previous_hash=(json.loads(previous_manifest.read_text(encoding='utf-8')).get('parameters_sha256')
                   if previous_manifest.exists() else None)
    known_previous=hashlib.sha256(parameters).hexdigest()==previous_hash
    original=(root/'extracted/PARAMETA.DAT').read_bytes()
    text=field_battle_ui.cooking.strings(field_battle_ui.BATTLE_HELP_UI)
    for offset,key in field_battle_ui.STANCE_HELP.items():
        expected=bytearray(original[offset-2:offset+114])
        field_battle_ui.record(expected,2,text[key].split('\\n'),19)
        current=parameters[offset-2:offset+114]
        if not known_previous and current not in (original[offset-2:offset+114],expected):
            raise ValueError('unknown stance help record at %X'%offset)
        parameters[offset-2:offset+114]=expected
    parameter_file=out/'PARAMETA.DAT';parameter_file.write_bytes(parameters)
    inject.put(str(track),'PARAMETA.DAT',str(parameter_file))
    with track.open('rb') as f:
        lba,size=inject.find(f,'PARAMETA.DAT'); embedded=inject._extent(f,lba,size)
    if embedded!=parameters:raise RuntimeError('disc parameter readback failed')
    manifest['stance_help_pages']=list(field_battle_ui.STANCE_HELP.values())
    manifest['parameters_sha256']=hashlib.sha256(parameters).hexdigest()
    with track.open('rb') as f:
        lba,size=inject.find(f,'SYSTEM.DAT'); system=bytearray(inject._extent(f,lba,size))
    font_offset=0x424E0
    current=system[font_offset:font_offset+len(native_font)]
    known_fonts=[native_font,(root/'build/FONT.vwf.bin').read_bytes(),
                 (root/'extracted/FONT.BIN').read_bytes()]
    if current not in known_fonts:raise ValueError('unknown embedded native font')
    system[font_offset:font_offset+len(native_font)]=native_font
    system_file=out/'SYSTEM.DAT';system_file.write_bytes(system)
    inject.put(str(track),'SYSTEM.DAT',str(system_file))
    with track.open('rb') as f:
        lba,size=inject.find(f,'SYSTEM.DAT'); embedded=inject._extent(f,lba,size)
    if embedded!=system:raise RuntimeError('disc system readback failed')
    manifest['system_sha256']=hashlib.sha256(system).hexdigest()
    run.mkdir(parents=True,exist_ok=True);(run/'data').mkdir(exist_ok=True)
    if not (run/'flycast.exe').exists():shutil.copy2(stock/'flycast.exe',run/'flycast.exe')
    stockhash=hashlib.sha256((stock/'flycast.exe').read_bytes()).hexdigest()
    if hashlib.sha256((run/'flycast.exe').read_bytes()).hexdigest()!=stockhash:
        raise RuntimeError('isolated emulator differs from stock; refusing to proceed')
    if not (run/'bios').exists():shutil.copytree(stock/'bios',run/'bios')
    for pattern in ('*vmu*.bin','dc_nvmem.bin'):
        for src in (stock/'data').glob(pattern):
            dst=run/'data'/src.name
            if not dst.exists():shutil.copy2(src,dst)
    cfg=run/'emu.cfg'
    if not cfg.exists():
        c=configparser.ConfigParser(interpolation=None);c.optionxform=str
        c.read(stock/'emu.cfg',encoding='utf-8')
        for key,value in {'Dreamcast.BiosPath':str(run/'bios'),
                          'Dreamcast.ContentPath':str(disc),
                          'Dreamcast.AutoLoadState':'no','Dreamcast.AutoSaveState':'no',
                          'rend.CustomTextures':'yes','rend.DumpTextures':'yes',
                          'rend.DumpUniqueTextures':'no'}.items():c['config'][key]=value
        # Default directories are relative to the isolated profile, not stock.
        for key in ('SavePath','SavestatePath','VMUPath','TexturePath','TextureDumpPath'):
            c['config']['Dreamcast.'+key]=''
        with cfg.open('w',encoding='utf-8') as f:c.write(f)
    low,high=stock_atlas_pack.sheets(bizin_font.NATIVE,font_style.default_font())
    bizin_font.preview()
    if all((run/'data/texdump/T20101M'/name).exists() for name in seed_bizin_pack.CAPTURES):
        manifest['font_pack']=seed_bizin_pack.install()
    low.save(out/'native-sheet-mask.png');high.save(out/'hd-sheet-mask.png')
    manifest['stock_emulator_sha256']=stockhash
    manifest['disc_readback_verified']=True
    manifest['disc_cue']=str(cue)
    if (run/'data/texdump/T20101M'/deployment_heading_pack.NAME).exists():
        manifest['deployment_heading']=deployment_heading_pack.install()
    else:
        manifest['deployment_heading']='pending: capture the deployment HUD, then run deployment_heading_pack.py'
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Ready: '+str(disc))
    print('Verified byte-identical stock Flycast: '+stockhash)
    print('No stock profile, original disc, or VMU files were modified.')


if __name__=='__main__':main()
