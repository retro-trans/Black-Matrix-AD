"""Lower the high lowercase a/p contours without moving their bottom anchors.

Private Disc 2 variant preserving the native objective-art build. Only two
Latin glyph records and their existing VQ page contents change in SYSTEM.
"""
import json
import shutil
import sys

import numpy as np
from PIL import Image,ImageDraw
import skies_rayblade_match as font

ROOT=font.ROOT
SOURCE=ROOT/'build/skies-rayblade-font-v3-native-art-v1'
SOURCE_SHA='bcfeb3c89b00227af16e95413d0275fdf0ef92e56e8f80b6b6bcbc5dc1fa83b5'
OUT=ROOT/'build/skies-rayblade-font-v4-baseline'
# Remove one redundant row inside a straight-sided counter. Everything above
# it moves down one original source pixel; everything below it remains exact.
# This is NOT a whole-glyph translation, rescale or bounding-box normalization.
DROP_ROWS={'a':15,'p':12}


def corrected(glyphs):
    result=dict(glyphs)
    for ch,row in DROP_ROWS.items():
        source=np.array(glyphs[ch])
        if source.shape!=(24,12) or glyphs[ch].getbbox()[1]!=6:
            raise ValueError('Unexpected lowercase source metrics')
        if not np.array_equal(source[row-1],source[row]) or not np.array_equal(source[row],source[row+1]):
            raise ValueError('Selected row is not a redundant straight section')
        out=np.zeros_like(source);out[1:row+1]=source[:row];out[row+1:]=source[row+1:]
        image=Image.fromarray(out)
        if image.getbbox()!=(glyphs[ch].getbbox()[0],7,glyphs[ch].getbbox()[2],glyphs[ch].getbbox()[3]):
            raise ValueError('Baseline, width or lowercase top changed unexpectedly')
        result[ch]=image
    return result


def native_record(source):
    # Same first-port fallback raster convention, with corrected source masks.
    small=source.resize((16,16),Image.Resampling.BOX);box=small.getbbox()
    image=Image.new('L',(32,16));image.paste(small,(1-box[0],0))
    coverage=np.array(image,dtype='i2')
    nearest=np.abs(coverage[:,:,None]-np.array(font.prior.LEVELS)).argmin(axis=2)
    return font.prior.encoded(Image.fromarray(np.array((0,3,2,1),dtype='u1')[nearest]))


def patch(system):
    _,original,_,_=font.prior.source_bitmap();fixed=corrected(original)
    old_pages,old_raw,_=font.pages(original);images,raw,counts=font.pages(fixed)
    result=bytearray(system);allowed=[]
    for bank,before,after in zip(font.full.BANKS,old_raw,raw):
        off=font.prior.FONT_OFFSET+16+bank*128
        if system[off:off+8192]!=before:raise ValueError('Unexpected existing VQ font page')
        result[off:off+8192]=after;allowed.append((off,off+8192))
    for ch in DROP_ROWS:
        index=font.prior.latin.charmap()[ch];off=font.prior.FONT_OFFSET+16+index*128
        if system[off:off+128]!=native_record(original[ch]):raise ValueError('Unexpected native fallback '+ch)
        result[off:off+128]=native_record(fixed[ch]);allowed.append((off,off+128))
    changed=np.flatnonzero(np.frombuffer(system,dtype='u1')!=np.frombuffer(result,dtype='u1'))
    if any(not any(lo<=i<hi for lo,hi in allowed) for i in changed):raise ValueError('Out-of-scope font edit')
    return bytes(result),images,raw,counts,changed.tolist(),fixed


def preview(exe,original,fixed):
    text=['a e n s u o    p g q y','This ship has now become a refuge',
          'for escaped slaves and the The','Weak,','a pan   paper   escape   apples']
    image=Image.new('RGB',(1088,790),'#181715');draw=ImageDraw.Draw(image)
    for section,(glyphs,label) in enumerate(((original,'Before: a/p top row 6'),(fixed,'After: top row 7, baseline and descenders unchanged'))):
        y=section*390;draw.text((8,y+8),label+' (offline preview)',fill='white')
        for row,line in enumerate(text):
            rendered=Image.new('RGBA',(536,36));pen=0
            for ch in line:
                tile=font.glyph(ch,glyphs).crop((0,0,*font.SAMPLE))
                tile=tile.resize((font.QUAD[0],font.QUAD[1]*2),Image.Resampling.BILINEAR)
                rendered.alpha_composite(tile,(pen,0))
                index=0 if ch==' ' else font.prior.latin.charmap()[ch]
                pen+=exe[font.prior.vwf.ADV_TAB-font.prior.atlas.BASE+index]+(4 if ch==' ' else 0)
            big=rendered.resize((1072,72),Image.Resampling.NEAREST)
            image.paste(big,(8,y+28+row*71),big)
    image.save(OUT/'comparison.png')


def build():
    if OUT.exists():raise ValueError('Preserve previous baseline test output')
    source=SOURCE/'disc2'/font.prior.TRACK
    if font.prior.digest(source)!=SOURCE_SHA:raise ValueError('Source track differs')
    system,lba=font.prior.read_file(source,'SYSTEM.DAT');exe,_=font.prior.read_file(source,'1ST_READ.BIN')
    after,images,raw,counts,offsets,fixed=patch(system)
    changes={(lba-font.prior.inject.HIGH_DENSITY_LBA+i//2048)*2352+16+i%2048:after[i] for i in offsets}
    OUT.mkdir();_,original,_,_=font.prior.source_bitmap();preview(exe,original,fixed)
    for i,(im,data) in enumerate(zip(images,raw)):
        im.resize((512,512),Image.Resampling.NEAREST).save(OUT/('font-page-%d.png'%i))
        (OUT/('font-page-%d.vq'%i)).write_bytes(data)
    folder=OUT/'disc2';folder.mkdir()
    sha=font.prior.copy_track(source,folder/source.name,SOURCE_SHA,changes)
    if font.prior.read_file(folder/source.name,'SYSTEM.DAT')[0]!=after:raise ValueError('SYSTEM readback differs')
    for name in ('1ST_READ.BIN','MAP.DAT','SCENARIO.DAT'):
        if font.prior.read_file(source,name)[0]!=font.prior.read_file(folder/source.name,name)[0]:
            raise ValueError('Non-font payload differs: '+name)
    companions=[]
    for p in source.parent.iterdir():
        if p.is_file() and p!=source:
            shutil.copy2(p,folder/p.name);digest=font.prior.digest(p)
            if font.prior.digest(folder/p.name)!=digest:raise ValueError('Companion differs')
            companions.append(dict(file=p.name,sha256=digest))
    if font.prior.digest(source)!=SOURCE_SHA:raise ValueError('Source changed')
    report=dict(status='verified-skies-lowercase-baseline',disc=2,
        source='build/skies-rayblade-font-v3-native-art-v1',source_sha256=SOURCE_SHA,track_sha256=sha,
        system_sha256=font.prior.sha(after),changed_system_bytes=len(offsets),characters=list(DROP_ROWS),
        source_top_before=6,source_top_after=7,drop_rows=DROP_ROWS,codebook_entries=counts,
        baseline_and_descenders_unchanged=True,metrics_geometry_and_executable_unchanged=True,
        native_fallback_also_updated=True,native_objective_cards_retained=24,companions=companions,
        hd_files_changed=0,saves_unchanged=True,in_game_verified=False)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['build']:build()
    else:
        _,glyphs,_,_=font.prior.source_bitmap();print('Codebooks:',font.pages(corrected(glyphs))[2])
