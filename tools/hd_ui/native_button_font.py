"""Native-only Status/Equip footer typography; preserve HD and native icons."""
import json
import shutil
import struct
from PIL import Image, ImageDraw
import native_sword_fix as base
import vertical_attack_icon as icon
import status_art
import interface_redraw as pack
import pvr_atlas
import inject

ROOT=base.ROOT
SOURCE=base.OUT
OUT=ROOT/'build/reusable-atlas-noto-ui-r35-native-ui-v2'
HASHES={'SYSTEM.DAT':'1055352de26250de1f7dd37ec437986b5294e6c50eb1643069ec809701735e5e',
        'SYSTEM.disc2.DAT':'c743e41c9fc46af96b9159e1c5460706bc137d699a7b381b2911f25a6435a761'}
LABELS={51:'Status',57:'Magic',59:'Equip',61:'Unequip',62:'Discard',63:'Back'}


def caption(text,width):
    # Keep the HD font's em/baseline, but use a shared 1px left inset in native
    # slots so Unequip fits 40px without squeezing that word or shrinking it.
    art=status_art.button_caption(text,56)
    box=art.getchannel('A').getbbox()
    if box[0]<4 or box[2]-4>width*4-4:raise ValueError('native caption overflow')
    return art.crop((4,0,4+width*4,64)).resize((width,16),Image.Resampling.LANCZOS)


def updates(source):
    icon.validate_geometry(source)
    rows=pack.descriptors(source,icon.TEXTURE)
    original=pack.descriptors((base.SOURCE/'SYSTEM.DAT').read_bytes(),icon.TEXTURE)
    result=[]
    for index,text in LABELS.items():
        rect=rows[index]
        if rect!=original[index] or rect[3]-rect[1]!=16:
            raise ValueError('caption geometry changed')
        width=rect[2]-rect[0]
        image=caption(text,width)
        values=[]
        for r,g,b,a in image.getdata():
            r,g,b=(c*a//255 for c in (r,g,b))
            values.append(struct.pack('<H',0x8000|(r*31//255)<<10|(g*31//255)<<5|b*31//255 if a>=64 else 0))
        sites=[icon.TEXTURE+16+2*pvr_atlas.pixel_index(x,y)
               for y in range(rect[1],rect[3]) for x in range(rect[0],rect[2])]
        result.extend(zip(sites,values))
    return result


def patch_system(source):
    pending=updates(source)
    result=bytearray(source)
    for offset,word in pending:result[offset:offset+2]=word
    return bytes(result)


def preview(before,after):
    rows=pack.descriptors(before,icon.TEXTURE)
    sheet=Image.new('RGB',(1024,336),'#171717');draw=ImageDraw.Draw(sheet)
    for version,data in enumerate((before,after)):
        atlas=pvr_atlas.decode(data,icon.TEXTURE)
        draw.text((8,version*168+4),'Previous native (4x atlas samples)' if version==0 else 'New native: shared font/size/baseline (4x atlas samples)',fill='white')
        for row,labels in enumerate((((0,51),(2,59),(3,57),(1,63)),((0,59),(2,61),(3,62),(1,63)))):
            bar=Image.new('RGBA',(256,16),(0,0,0,255))
            for col,(button,label) in enumerate(labels):
                for index,x in ((button,col*64),(label,col*64+16)):
                    tile=atlas.crop(rows[index]);bar.paste(tile,(x,0),tile)
            sheet.paste(bar.resize((1024,64),Image.Resampling.NEAREST),(0,version*168+24+row*68))
    sheet.save(OUT/'comparison.png')


def build():
    if OUT.exists():raise ValueError('output exists; refusing overwrite')
    protected=base.snapshot()
    protected.update({str(p.relative_to(ROOT)):base.digest(p) for p in SOURCE.rglob('*') if p.is_file()})
    systems={}
    for name,sha in HASHES.items():
        if base.digest(SOURCE/name)!=sha:raise ValueError('unrecognized native source')
        systems[name]=patch_system((SOURCE/name).read_bytes())
    OUT.mkdir();discs=[]
    for number,dirname,name in ((1,'disc','SYSTEM.DAT'),(2,'disc2','SYSTEM.disc2.DAT')):
        shutil.copytree(SOURCE/dirname,OUT/dirname)
        filename=f'Black-Matrix Advanced (Japan) (Disc {number}) (Track 3).bin'
        old,new=SOURCE/dirname/filename,OUT/dirname/filename
        source=(SOURCE/name).read_bytes()
        with old.open('rb') as f:
            lba,size=inject.find(f,'SYSTEM.DAT')
            if inject._extent(f,lba,size)!=source:raise ValueError('disc/archive mismatch')
        pending=updates(source)
        raw=[(lba-inject.HIGH_DENSITY_LBA+o//2048)*2352+16+o%2048 for o,_ in pending]
        with new.open('r+b') as f:
            for offset,(_,value) in zip(raw,pending):f.seek(offset);f.write(value)
        with new.open('rb') as f:
            if inject._extent(f,lba,size)!=systems[name]:raise ValueError('disc readback failed')
        changed=base.verify_track(old,new,raw)
        (OUT/name).write_bytes(systems[name])
        discs.append(dict(disc=number,changed_raw_bytes=changed,only_caption_pixels_changed=True,
                          track_sha256=base.digest(new),system_sha256=base.digest(OUT/name)))
    if any(base.digest(ROOT/p)!=sha for p,sha in protected.items()):raise ValueError('protected inputs changed')
    preview((SOURCE/'SYSTEM.DAT').read_bytes(),systems['SYSTEM.DAT'])
    report=dict(status='verified-native-only',labels=LABELS,font=str(status_art.SANS),
                font_sha256=base.digest(status_art.SANS),em=status_art.BUTTON_EM,baseline=status_art.BUTTON_BASELINE,left_inset=1,
                hd_files_unchanged=True,native_sword_fix_preserved=True,discs=discs,protected_files=protected,
                live_game_tested=False)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='protected_files'},indent=2))


if __name__=='__main__':build()
