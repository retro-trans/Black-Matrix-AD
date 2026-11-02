"""Private VGA v12: align solid lower strokes, not merely faint AA bounds."""
import argparse
import json
import shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import skies_vga_item_alignment as previous
import skies_vga_approved_baseline as approved
import mode1_sector

ROOT=previous.ROOT
prior=previous.prior
font=approved.font
SOURCE=previous.OUT
SOURCE_SHA='fe9489454e8e90f62104dfe2efd2e32c22f0d3706cf5459b930c11f5bc93c863'
EXE_SHA='648edc63be2b9c8f7179226d298b4647c2efdb903f52813cc28fe9227305e7e8'
SYSTEM_SHA=previous.SYSTEM_SHA
OUT=ROOT/'build/skies-vga-compat-v12-optical-baseline'
STATUS='verified-skies-vga-optical-baseline'
CHANGED=set('013456789VWvw')


def corrected_glyphs():
    _,_,old=approved.approved_glyphs();new={c:g.copy() for c,g in old.items()}
    weak=set()
    for c,g in old.items():
        if c.isalnum() and np.max(np.asarray(g)[20])<255:weak.add(c)
    if weak!=CHANGED:raise ValueError('Unexpected solid baseline audit')
    for c in sorted(CHANGED):
        a=np.array(old[c]);row=a[20];peak=int(row.max())
        if peak not in (85,187) or np.any(a[21:]):raise ValueError('Unexpected lower stroke')
        # Keep existing silhouette, outer AA and upper contours. Make the
        # strongest bottom samples actual ink. W/v also have an entirely
        # translucent preceding row: join the solid stem through that row.
        row[row==peak]=255
        if not np.any(a[19]==255):a[19][a[19]==a[19].max()]=255
        new[c]=Image.fromarray(a)
    return old,new


def patch_system(system,exe):
    if prior.sha(system)!=SYSTEM_SHA or prior.sha(exe)!=EXE_SHA:raise ValueError('Unknown VGA v11 source')
    old,new=corrected_glyphs();result=bytearray(system);allowed=set();details=[]
    forward=exe[prior.atlas.FORWARD-prior.atlas.BASE:prior.atlas.FORWARD-prior.atlas.BASE+256]
    slots={c:forward[prior.latin.charmap()[c]] for c in CHANGED}
    if any(s>=128 for s in slots.values()):raise ValueError('Glyph not mapped')
    for bank in sorted({s//32 for s in slots.values()}):
        off=prior.FONT_OFFSET+16+font.ritual.full.BANKS[bank]*128
        page=font.ritual.full.decode_vq(system[off:off+8192])
        for ch,slot in slots.items():
            if slot//32!=bank:continue
            x=slot%8*16;y=slot%32//8*32
            if page.crop((x,y,x+16,y+32)).tobytes()!=font.header.glyph(ch,old).tobytes():
                raise ValueError('Source glyph differs: '+ch)
            page.paste(font.header.glyph(ch,new),(x,y))
        payload,count=font.ritual.full.encode_vq(page)
        result[off:off+8192]=payload;allowed.update(range(off,off+8192))
        details.append(dict(bank=bank,offset=off,codebook_entries=count))
    for ch in sorted(CHANGED):
        off=prior.FONT_OFFSET+16+prior.latin.charmap()[ch]*128
        if system[off:off+128]!=font.baseline.native_record(old[ch]):raise ValueError('Fallback differs: '+ch)
        result[off:off+128]=font.baseline.native_record(new[ch]);allowed.update(range(off,off+128))
    # None of the nine fallback footer captions contains these characters.
    if any(CHANGED.intersection(t) for t in font.LABELS.values()):raise ValueError('Caption update required')
    delta=np.flatnonzero(np.frombuffer(system,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if not delta or not set(delta)<=allowed:raise ValueError('Out-of-font edit')
    return bytes(result),delta,allowed,details


def preview(folder):
    old,new=corrected_glyphs();review,_,_=approved.approved_glyphs()
    advances={r['char']:r['advance'] for r in review['glyphs']}
    import preview_skies_baseline_audit as draw_font
    image=Image.new('RGB',(1440,870),'#11161b');d=ImageDraw.Draw(image)
    label=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
    d.text((20,10),'Optical baseline correction - offline font comparison, not a GPU screenshot',font=label,fill='white')
    texts=['why do you think He would grant','the wishes of people like us in','this world,',
           'VW vw 0123456789','abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ','g j p q y - natural tails retained']
    for col,(title,glyphs) in enumerate((('CURRENT',old),('CORRECTED',new))):
        x=20+col*710;d.text((x,48),title,font=label,fill='#d6dce3')
        for i,text in enumerate(texts):
            y=90+i*104;mask=draw_font.line(text,glyphs,advances)
            mask=mask.resize((mask.width*2,mask.height*2),Image.Resampling.NEAREST)
            d.line((x,y+42,x+660,y+42),fill='#3aba89')
            image.paste('#f3f5f7',(x,y),mask)
    image.save(folder/'optical-baseline-comparison.png')


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('VGA v11 source differs')
    print('Source track authenticated.',flush=True)
    exe,_=prior.read_file(source,'1ST_READ.BIN');system,lba=prior.read_file(source,'SYSTEM.DAT')
    after,delta,_,pages=patch_system(system,exe)
    report=dict(status=STATUS if build else 'planned-skies-vga-optical-baseline',disc=2,
        source_sha256=SOURCE_SHA,source=str(SOURCE.relative_to(ROOT)),executable_sha256=EXE_SHA,
        source_system_sha256=SYSTEM_SHA,system_sha256=prior.sha(after),changed_system_bytes=len(delta),
        characters=sorted(CHANGED),pages=pages,baseline=21,solid_stroke_row=20,
        source_cell=[12,24],glyph_quad=[16,12],same_silhouette_and_upper_contours=True,
        natural_descenders_unchanged=True,native_fallback_consistent=True,
        executable_size_spacing_and_allocations_unchanged=True,icons_art_and_footer_bitmaps_unchanged=True,
        item_alignment_and_vga_timing_retained=True,same_existing_save_folder=True,
        in_game_visual_verified=False,physical_hardware_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous optical-baseline build')
    changes,touched=previous.sectors.sector_changes(source,lba,after,delta)
    OUT.mkdir();preview(OUT);folder=OUT/'disc2';folder.mkdir();target=folder/source.name
    print('Writing private disc and verifying exact raw changes.',flush=True)
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
    print('Checking every game payload and companion.',flush=True)
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
