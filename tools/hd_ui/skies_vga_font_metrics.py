"""Private VGA v8: header-matched footer metrics and common p/q body baseline.

Keep native font cell/sample sizes, advances, allocations and all executable
code unchanged. Footer sprite X2 is compensated in artwork, not window layout.
"""
import argparse
import json
import shutil
import numpy as np
from PIL import Image,ImageDraw
import skies_vga_footer_labels as previous
import skies_baseline_fix as baseline
import skies_ritual_font as ritual
import skies_rayblade_match as header
import skies_attack_letters as sectors
import mode1_sector

ROOT=previous.ROOT
prior=previous.prior
SOURCE=previous.OUT
SOURCE_SHA='f17052ad98db46488b4c6f7ebd7e6a66b3b44eddd5c71aa8c3d44f6032c9a387'
SYSTEM_SHA='22e0cfc175d69276d51b4d9a7c318a2c9fb52bb074347a67ae074fb7719b4ba1'
OUT=ROOT/'build/skies-vga-compat-v8-font-metrics'
STATUS='verified-skies-vga-font-metrics'
LABELS=previous.LABELS|{63:'Back',64:'OK'}
RECTS=previous.RECTS|{63:(64,160,104,176),64:(0,208,32,224)}
TEXTURE=previous.TEXTURE
TOP=0.5


def source_glyphs():
    _,source,_,_=prior.source_bitmap()
    return baseline.corrected(source)


def corrected_glyphs(glyphs):
    result=dict(glyphs)
    for ch in ('p','q'):
        source=np.asarray(glyphs[ch]);expected=(2,7 if ch=='p' else 6,11,23)
        if glyphs[ch].getbbox()!=expected:raise ValueError('Unexpected p/q source outline')
        if ch=='q':
            # Same proven redundant-row technique as the earlier a/p fix:
            # lower the high q top without moving its lower bowl/stem yet.
            if not np.array_equal(source[11],source[12]) or not np.array_equal(source[12],source[13]):
                raise ValueError('q counter is not straight at row12')
            adjusted=np.zeros_like(source)
            adjusted[1:13]=source[:12];adjusted[13:]=source[13:]
            source=adjusted
        if not np.array_equal(source[12],source[13]):raise ValueError('p/q counter is not straight')
        # Add two identical straight counter rows. Bowl bottom19 ->21, same
        # as e/n/u. Keep a three-row stem below it inside the existing24sample.
        extended=np.concatenate((source[:14],np.repeat(source[13:14],2,axis=0),source[14:]),axis=0)[:24]
        result[ch]=Image.fromarray(extended)
        if result[ch].getbbox()!=(2,7,11,24):raise ValueError('Unexpected corrected p/q bounds')
    return result


def logical_line(text,glyphs,exe):
    """Exact header foreground bearings/advances; no per-letter bbox baseline."""
    line=Image.new('L',(192,24));pen=0
    for ch in text:
        glyph=glyphs[ch];box=glyph.getbbox()
        if ch==' ':
            pen+=exe[ritual.size.SMALL_ADV-prior.atlas.BASE]
            continue
        if box is None:raise ValueError('Unexpected blank caption glyph')
        left=box[0]
        for y in range(24):
            for x in range(12):
                a=glyph.getpixel((x,y));px=pen+2+x-left
                if a and not 0<=px<line.width:raise ValueError('Logical caption overflow')
                if a:line.putpixel((px,y),max(a,line.getpixel((px,y))))
        gid=prior.latin.charmap()[ch]
        pen+=exe[ritual.size.SMALL_ADV-prior.atlas.BASE+gid]
    return line,pen


def caption(text,width,glyphs,exe):
    line,advance=logical_line(text,glyphs,exe);box=line.getbbox()
    if box is None or box[2]/2>width-1:raise ValueError('Caption exceeds existing sprite')
    # Logical source1px -> native0.5px on BOTHaxes. Footer geometry X2 and
    # scanout Y2 restore1:1 header proportions. Work at4xnative for coverage.
    mask=Image.new('L',(width*4,64))
    mask.paste(line.resize((384,48),Image.Resampling.NEAREST),(0,round(TOP*4)))
    art=Image.new('RGBA',mask.size,(*previous.captions.GOLD,0));art.putalpha(mask)
    return art,dict(logical_advance=advance,logical_ink=box,
        native_x_scale=0.5,native_y_scale=0.5,display_x_scale=1,display_y_scale=1,top=TOP)


def patch_system(system,exe):
    if prior.sha(system)!=SYSTEM_SHA:raise ValueError('Unknown VGA v7 SYSTEM')
    if prior.sha(exe)!='577626debafc203b97d654467d34b6abd32f32781a7448a3f8bad0b72384bfea':
        raise ValueError('Unknown VGA v7 executable/metrics')
    old=source_glyphs();glyphs=corrected_glyphs(old)
    result=bytearray(system);allowed=set();page_info=[]
    forward=exe[prior.atlas.FORWARD-prior.atlas.BASE:prior.atlas.FORWARD-prior.atlas.BASE+256]
    slots={ch:forward[prior.latin.charmap()[ch]] for ch in ('p','q')}
    for bank in sorted({slot//32 for slot in slots.values()}):
        off=prior.FONT_OFFSET+16+ritual.full.BANKS[bank]*128
        page=ritual.full.decode_vq(system[off:off+8192])
        for ch,slot in slots.items():
            if slot//32!=bank:continue
            x=slot%8*16;y=slot%32//8*32
            if page.crop((x,y,x+16,y+32)).tobytes()!=header.glyph(ch,old).tobytes():
                raise ValueError('Unknown current p/q canonical tile')
            page.paste(header.glyph(ch,glyphs),(x,y))
        raw,count=ritual.full.encode_vq(page)
        result[off:off+8192]=raw;allowed.update(range(off,off+8192))
        page_info.append(dict(bank=bank,offset=off,codebook_entries=count))
    for ch in ('p','q'):
        off=prior.FONT_OFFSET+16+prior.latin.charmap()[ch]*128
        if system[off:off+128]!=baseline.native_record(old[ch]):raise ValueError('Unknown p/q fallback')
        result[off:off+128]=baseline.native_record(glyphs[ch]);allowed.update(range(off,off+128))
    rows=previous.captions.native.pack.descriptors(system,TEXTURE);metrics={}
    for index,text in LABELS.items():
        rect=RECTS[index]
        if rows[index]!=rect:raise ValueError('Footer sprite descriptor changed')
        art,metrics[text]=caption(text,rect[2]-rect[0],glyphs,exe)
        for off,value in previous.captions.native.encode(system,TEXTURE,rect,art):
            result[off:off+2]=value;allowed.update((off,off+1))
    delta=np.flatnonzero(np.frombuffer(system,dtype='u1')!=np.frombuffer(result,dtype='u1')).tolist()
    if not delta or not set(delta)<=allowed:raise ValueError('Out-of-font/label changes')
    return bytes(result),delta,allowed,dict(slots=slots,pages=page_info,footers=metrics),glyphs


def preview(before,after,exe,glyphs):
    out=Image.new('RGBA',(1190,665),'#100e0a');draw=ImageDraw.Draw(out)
    draw.text((10,5),'Offline actual-display proportions: header / corrected footer share exact foreground bearings and advances',fill='white')
    for col,(name,gs) in enumerate((('Old p/q source',source_glyphs()),('Corrected p/q body baseline',glyphs))):
        line,_=logical_line('Equip  p q e n u',gs,exe)
        art=Image.new('RGBA',line.size,(*previous.captions.GOLD,0));art.putalpha(line)
        draw.text((10+col*580,27),name,fill='white')
        out.alpha_composite(art.resize((576,72),Image.Resampling.NEAREST),(10+col*580,46))
    for version,system in enumerate((before,after)):
        y0=140+version*250
        draw.text((10,y0),'Before: footer spriteX2 not fully compensated' if version==0 else 'After: header-proportioned captions, consistent body baseline; same icons/origins',fill='white')
        atlas=previous.pvr_atlas.decode(system,TEXTURE);rows=previous.captions.native.pack.descriptors(system,TEXTURE)
        for row,items in enumerate((((0,51),(2,59),(3,57),(1,63)),((0,59),(2,61),(3,62),(1,63)),((0,97),(2,98),(1,64)))):
            for col,(icon,word) in enumerate(items):
                for index,dx in ((icon,0),(word,26)):
                    r=rows[index];tile=atlas.crop(r).resize(((r[2]-r[0])*4,64),Image.Resampling.NEAREST)
                    out.alpha_composite(tile,(10+col*280+dx*2,y0+20+row*74))
    out.save(OUT/'font-metrics-preview.png')


def run(build=False):
    source=SOURCE/'disc2'/prior.TRACK
    if prior.digest(source)!=SOURCE_SHA:raise ValueError('VGA v7 source differs')
    system,lba=prior.read_file(source,'SYSTEM.DAT');exe,_=prior.read_file(source,'1ST_READ.BIN')
    after,delta,_,details,glyphs=patch_system(system,exe)
    report=dict(status=STATUS if build else 'planned-skies-vga-font-metrics',disc=2,
        source_sha256=SOURCE_SHA,source=str(SOURCE.relative_to(ROOT)),system_sha256=prior.sha(after),
        changed_system_bytes=len(delta),details=details,pq_common_body_baseline=21,pq_descender_end=24,
        footer_display_proportions_match_header=True,all_nine_footers_corrected=True,
        descriptors_origins_icons_unchanged=True,executable_sha256=prior.sha(exe),
        executable_and_vga_boot_unchanged=True,font_sample_allocations_and_advances_unchanged=True,
        earlier_art_and_system_alignment_retained=True,same_existing_save_folder=True,
        in_game_visual_verified=False,physical_hardware_verified=False)
    if not build:print(json.dumps(report,indent=2));return
    if OUT.exists():raise ValueError('Preserve previous font-metrics build')
    changes,touched=sectors.sector_changes(source,lba,after,delta)
    OUT.mkdir();folder=OUT/'disc2';folder.mkdir();preview(system,after,exe,glyphs);target=folder/source.name
    report['track_sha256']=prior.copy_track(source,target,SOURCE_SHA,changes)
    report.update(changed_raw_bytes=len(changes),parity_repaired_sectors=touched)
    with source.open('rb') as stream:
        directory=list(prior.inject.iso_files(stream));boot=prior.inject._extent(stream,45000,32768)
    with target.open('rb') as stream:
        if list(prior.inject.iso_files(stream))!=directory or prior.inject._extent(stream,45000,32768)!=boot:
            raise ValueError('Boot or directory changed')
        for sector in touched:
            stream.seek(sector*2352);raw=stream.read(2352)
            if mode1_sector.regenerate(raw)!=raw:raise ValueError('Output parity invalid')
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
    print(json.dumps({k:v for k,v in report.items() if k not in ('files','details')},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true')
    run(parser.parse_args().build)
