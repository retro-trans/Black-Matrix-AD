"""Private VGA v10: apply the exact glyphs approved in the baseline preview.

No code/metric/layout changes. Preserve all other decoded VQ pixels, including
the star. Native fallback records and affected native captions stay consistent.
"""
import argparse
import json
import shutil
import numpy as np
from PIL import Image
import skies_vga_sharp_footer as previous
import mode1_sector

ROOT=previous.ROOT
prior=previous.prior
font=previous.previous
SOURCE=previous.OUT
SOURCE_SHA='a1069e012e40813ff7a21864bc16aaf95bdf4c8039cd3c19d7c9c2b8c17a16f4'
EXE_SHA='30ec99033a86074af1b0d6ee747be055477546dd433a7bf0ebc827dd561c03cc'
SYSTEM_SHA='09afbfdf3a98dc57aca152dec11507ab41f1311a03af983ee3d760def6de2fd8'
REVIEW=ROOT/'output/font-baseline-review-2026-10-31'
REVIEW_SHA='c7e913d58a3e96c87ea12734b498359eee2e4e1ff14b0325079c5634eb6aab9f'
PREVIEW_SHA='999f19d4ecabc96c4fb95fad8f15c05881e96c6a7f5c41f20d74c0bf3349414f'
OUT=ROOT/'build/skies-vga-compat-v10-approved-baseline'
STATUS='verified-skies-vga-approved-baseline'
CHANGED=set('JVWv013456789gjy.!?')


def approved_glyphs():
    raw=(REVIEW/'audit.json').read_bytes()
    if prior.sha(raw)!=REVIEW_SHA:raise ValueError('Approved preview data changed')
    report=json.loads(raw);old={};new={}
    for row in report['glyphs']:
        for key,destination in (('current',old),('proposed',new)):
            a=np.asarray(row[key],dtype='u1')
            if a.shape!=(24,12) or not set(a.flat)<={0,85,187,255}:raise ValueError('Unknown approved glyph shape')
            destination[row['char']]=Image.fromarray(a)
    if len(old)!=95 or {c for c in old if old[c].tobytes()!=new[c].tobytes()}!=CHANGED:
        raise ValueError('Approved character scope differs')
    return report,old,new


def patch_system(system,exe):
    if prior.sha(system)!=SYSTEM_SHA or prior.sha(exe)!=EXE_SHA:raise ValueError('Unknown VGA v9 source')
    report,old,new=approved_glyphs();result=bytearray(system);allowed=set();details={}
    forward=exe[prior.atlas.FORWARD-prior.atlas.BASE:prior.atlas.FORWARD-prior.atlas.BASE+256]
    slots={c:forward[prior.latin.charmap()[c]] for c in sorted(CHANGED)}
    if any(s>=128 for s in slots.values()):raise ValueError('Approved glyph not mapped')
    for bank in sorted({slot//32 for slot in slots.values()}):
        off=prior.FONT_OFFSET+16+font.ritual.full.BANKS[bank]*128
        page=font.ritual.full.decode_vq(system[off:off+8192])
        for ch,slot in slots.items():
            if slot//32!=bank:continue
            x=slot%8*16;y=slot%32//8*32
            if page.crop((x,y,x+16,y+32)).tobytes()!=font.header.glyph(ch,old).tobytes():
                raise ValueError('Existing glyph does not match review: '+ch)
            page.paste(font.header.glyph(ch,new),(x,y))
        raw,count=font.ritual.full.encode_vq(page)
        result[off:off+8192]=raw;allowed.update(range(off,off+8192))
        details[bank]=dict(offset=off,codebook_entries=count)
    for ch in sorted(CHANGED):
        off=prior.FONT_OFFSET+16+prior.latin.charmap()[ch]*128
        if system[off:off+128]!=font.baseline.native_record(old[ch]):raise ValueError('Unknown fallback: '+ch)
        result[off:off+128]=font.baseline.native_record(new[ch]);allowed.update(range(off,off+128))
    # Only Magic/Buy contain changed letters. The sharp v9 draw path already
    # uses the canonical glyphs above; its native/tinted fallback must agree.
    native=font.previous.captions.native;captions=[]
    rows=native.pack.descriptors(system,font.TEXTURE)
    for index,text in font.LABELS.items():
        rect=font.RECTS[index]
        if rows[index]!=rect:raise ValueError('Footer descriptor changed')
        art,_=font.caption(text,rect[2]-rect[0],old,exe)
        encoded=native.encode(system,font.TEXTURE,rect,art)
        if any(system[off:off+2]!=value for off,value in encoded):raise ValueError('Unknown native footer art')
        if not CHANGED.intersection(text):continue
        art,_=font.caption(text,rect[2]-rect[0],new,exe)
        for off,value in native.encode(system,font.TEXTURE,rect,art):
            result[off:off+2]=value;allowed.update((off,off+1))
        captions.append(text)
    delta=np.flatnonzero(np.frombuffer(system,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if not delta or not set(delta)<=allowed:raise ValueError('Out-of-approved-font edits')
    return bytes(result),delta,allowed,dict(slots=slots,pages=details,native_captions=captions)


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('VGA v9 source track differs')
    exe,_=prior.read_file(source,'1ST_READ.BIN');system,lba=prior.read_file(source,'SYSTEM.DAT')
    after,delta,_,details=patch_system(system,exe)
    report=dict(status=STATUS if build else 'planned-skies-vga-approved-baseline',disc=2,
        source_sha256=SOURCE_SHA,source=str(SOURCE.relative_to(ROOT)),executable_sha256=prior.sha(exe),
        system_sha256=prior.sha(after),changed_system_bytes=len(delta),
        # Windows PowerShell5 JSON objects are case-insensitive: J/j and V/v
        # must be values in an array, never distinct keys in a manifest object.
        details=details|{'slots':[dict(character=c,slot=s) for c,s in details['slots'].items()]},
        approved_review_sha256=REVIEW_SHA,approved_preview_sha256=PREVIEW_SHA,
        characters=sorted(CHANGED),exact_approved_masks=True,baseline=21,descender_limit=24,
        native_fallback_consistent=True,sharp_footer_renderer_unchanged=True,
        executable_geometry_advances_allocations_unchanged=True,unrelated_art_and_star_unchanged=True,
        same_existing_save_folder=True,user_approved_preview=True,
        in_game_visual_verified=False,physical_hardware_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous approved-baseline build')
    if prior.digest(REVIEW/'baseline-preview.png')!=PREVIEW_SHA:raise ValueError('Approved preview image changed')
    changes,touched=font.sectors.sector_changes(source,lba,after,delta)
    OUT.mkdir();folder=OUT/'disc2';folder.mkdir();target=folder/source.name
    shutil.copy2(REVIEW/'audit.json',OUT/'approved-audit.json')
    shutil.copy2(REVIEW/'baseline-preview.png',OUT/'approved-preview.png')
    report['track_sha256']=prior.copy_track(source,target,SOURCE_SHA,changes)
    report.update(changed_raw_bytes=len(changes),parity_repaired_sectors=touched)
    with source.open('rb') as stream:
        directory=list(prior.inject.iso_files(stream));boot=prior.inject._extent(stream,45000,32768)
    with target.open('rb') as stream:
        if list(prior.inject.iso_files(stream))!=directory or prior.inject._extent(stream,45000,32768)!=boot:
            raise ValueError('Boot or directory changed')
        for sector in touched:
            stream.seek(sector*2352);raw=stream.read(2352)
            if mode1_sector.regenerate(raw)!=raw:raise ValueError('Output sector parity invalid')
    report['files']=[]
    for name,_,_ in directory:
        old,_=prior.read_file(source,name);new,_=prior.read_file(target,name)
        if new!=(after if name=='SYSTEM.DAT' else old):raise ValueError('Unrelated payload changed: '+name)
        report['files'].append(dict(name=name,sha256=prior.sha(new)))
    report['companions']=[]
    for path in source.parent.iterdir():
        if path.is_file() and path!=source:
            shutil.copy2(path,folder/path.name);digest=prior.digest(path)
            if prior.digest(folder/path.name)!=digest:raise ValueError('Companion changed')
            report['companions'].append(dict(file=path.name,sha256=digest))
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');run(p.parse_args().build)
