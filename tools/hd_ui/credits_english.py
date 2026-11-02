"""Private cumulative English credits: audited ImageGen lettering/movie only."""
import argparse
from fractions import Fraction
import json
import re
import shutil
import subprocess

import numpy as np
from PIL import Image,ImageDraw

import story_cards_complete as prior
import movie_subtitle_safe_area as media

ROOT=prior.ROOT
b=prior.b
SOURCE=prior.OUT
AUDIT=ROOT/'build/credits-english-2026-11-02'
ORIGINAL=media.ORIGINALS/'STAFF.SFD'
ORIGINAL_SHA='a0e51148e5413d6598be88078be895e88dc7853f5a5c91805fe09a26865268f6'
ASSETS=ROOT/'assets/ui/credits'
TEXT=ASSETS/'credits-english-v1.en.json'
PROVENANCE=ASSETS/'credits-english-v1.provenance.json'
ENCODED=AUDIT/'encoded-v4'
QUALITY=3
OUT=ROOT/'output/patched-discs-english-credits-2026-11-02'
STATUS='private-english-credits-runtime-pending'
VERSION='0.1.8'
EXE_SHA=prior.EXE_SHA
TRACK_HASHES={1:'3783db572fb82610f0b81d9aad9d802cc529d99b62e9fffc560608e36d8de6b1',
              2:'0c327c0625380130b6ac26b202d38ae1add96264f821575fc885ef7b65c86cf6'}


def save(path,data):
    path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')


def run(args,**kw):
    p=subprocess.run([media.FFMPEG,'-hide_banner','-nostdin',*args],capture_output=True,**kw)
    if p.returncode:
        raise ValueError(p.stderr.decode(errors='replace')[-2500:])
    return p


def audit():
    if AUDIT.exists():raise ValueError('Preserve prior credits audit')
    original=ORIGINAL.read_bytes()
    current,lba=b.READER.read_file(b.track(SOURCE,2),'STAFF.SFD')
    if media.sha(original)!=ORIGINAL_SHA or current!=original:
        raise ValueError('Current/original credits identity differs')
    video=media.elementary(original,224)
    fps=media.FPS[video[7]&15]
    if str(fps)!='24':raise ValueError('Unknown credits frame rate')
    frames=len(media.units(video))
    AUDIT.mkdir();(AUDIT/'original.m1v').write_bytes(video)
    folder=AUDIT/'sampled';folder.mkdir()
    result=run(['-v','warning','-i',str(AUDIT/'original.m1v'),
        '-vf',r'select=not(mod(n\,24))','-fps_mode','passthrough',str(folder/'frame-%03d.png')])
    (AUDIT/'decode.log').write_bytes(result.stderr)
    paths=sorted(folder.glob('frame-*.png'))
    for start in range(0,len(paths),16):
        group=paths[start:start+16]
        sheet=Image.new('RGB',(1280,260*((len(group)+3)//4)),'#202020');draw=ImageDraw.Draw(sheet)
        for i,path in enumerate(group):
            x,y=i%4*320,i//4*260
            with Image.open(path) as im:sheet.paste(im.convert('RGB'),(x,y+20))
            draw.text((x+4,y+3),str(start+i)+'s / frame'+str((start+i)*24),fill='white')
        sheet.save(AUDIT/f'contact-{start//16:02}.png')
    shifts=[]
    for i in range(1,len(paths)):
        a=np.asarray(Image.open(paths[i-1]).convert('L'))>80
        c=np.asarray(Image.open(paths[i]).convert('L'))>80
        scores=[]
        for dy in range(0,100):
            aa,cc=a[dy:],c[:240-dy]
            denom=np.count_nonzero(aa)+np.count_nonzero(cc)
            scores.append(2*np.count_nonzero(aa&cc)/denom if denom>60 else 0)
        dy=int(np.argmax(scores))
        shifts.append(dict(second=i,shift=dy,score=round(scores[dy],4)))
    save(AUDIT/'inventory.json',dict(source=str(SOURCE),movie='STAFF.SFD',source_sha256=ORIGINAL_SHA,
        movie_bytes=len(original),lba=lba,fps=str(fps),frames=frames,sampled_every_frames=24,
        samples=len(paths),shifts=shifts,original_and_current_unchanged=True))
    print('Dry/read-only audit complete',frames,'frames',fps,'fps',len(paths),'samples',flush=True)
    print('First scroll shifts',shifts[:20],flush=True)


def stitch():
    target=AUDIT/'original-roll-v2.png'
    if target.exists():raise ValueError('Preserve prior roll review')
    canvas=np.zeros((4000,320,3),'u1');weights=np.full(4000,1000)
    for second in range(5,123):
        image=np.asarray(Image.open(AUDIT/f'sampled/frame-{second+1:03}.png').convert('RGB'))
        off=(second-5)*32
        for y in range(240):
            distance=abs(y-120)
            if distance<weights[off+y]:
                canvas[off+y]=image[y];weights[off+y]=distance
    Image.fromarray(canvas).save(target)
    ink=np.count_nonzero(canvas.max(axis=2)>80,axis=1)>2
    runs=[]
    for y in np.flatnonzero(ink):
        if runs and y-runs[-1][1]<=1:runs[-1][1]=int(y)+1
        else:runs.append([int(y),int(y)+1])
    for start in range(0,len(runs),36):
        group=runs[start:start+36]
        sheet=Image.new('RGB',(1280,48*((len(group)+2)//3)),'#202020');draw=ImageDraw.Draw(sheet)
        for i,(lo,hi) in enumerate(group):
            x,y=i%3*426,i//3*48
            draw.text((x+4,y+3),f'{start+i:03} y{lo}',fill='white')
            crop=Image.fromarray(canvas[lo:hi]).resize((384,(hi-lo)*384//320),Image.Resampling.NEAREST)
            sheet.paste(crop,(x+40,y+20))
        sheet.save(AUDIT/f'rows-v2-{start//36:02}.png')
    save(AUDIT/'roll-rows-v2.json',dict(origin_frame=120,pixels_per_three_frames=4,
        rows=[dict(index=i,y=lo,end=hi) for i,(lo,hi) in enumerate(runs)]))
    print(len(runs),'scroll rows',runs[:4],runs[-4:],flush=True)


def prepare():
    text=media.read(TEXT);rows=media.read(AUDIT/'roll-rows-v2.json')['rows']
    if len(text['rows'])!=133 or len(rows)!=133:raise ValueError('Credit row inventory changed')
    original=Image.open(AUDIT/'original-roll-v2.png').convert('RGB')
    jobs=[]
    for start in range(0,len(rows),16):
        group=rows[start:start+16];ident=f'rows-{start:03}-{start+len(group)-1:03}'
        source=AUDIT/(ident+'-source.png')
        sheet=Image.new('RGB',(640,len(group)*40+40),'black')
        for i,row in enumerate(group):
            crop=original.crop((0,row['y']-1,320,row['end']+1))
            sheet.paste(crop.resize((640,crop.height*2),Image.Resampling.NEAREST),(0,20+i*40))
        sheet.save(source)
        lines=['                    '.join(c for c in r['cells'] if c is not None) for r in text['rows'][start:start+len(group)]]
        prompt=('Use case: text-localization. Image1 is the EDIT TARGET, a compact inspection panel of original game-credit rows. '
            'Translate all its Japanese lettering into the EXACT English rows below. This is production lettering for a scrolling game movie. '
            'Output a square1024x1024 pure BLACK bitmap. White clean medium-weight sans-serif only, no decoration. '
            f'Exactly{len(group)} horizontal text rows, in the exact order below. '
            'Use one common font size (about32 pixels cap height at1024), single-line rows with generous even vertical gaps. '
            'LEFT ALIGN all rows at x60. Where a row has two names separated by a wide space, put the second name in a fixed RIGHT column starting x550. '
            'Single-name rows and role headings use the full width. Never wrap any row or merge rows. '
            'Every row has the SAME font size/weight, not larger headings. Keep about60px outer margins. '
            'Keep every spelling, punctuation and company affiliation exactly, including the unusual ESSENSE. '
            'No Japanese, numbers, row labels, bullets, rules, lines, border, watermark, boxes, extra words or duplicate names. '
            'Do NOT print any explanatory instructions. Do not alter or abbreviate the names. '
            'The text rows verbatim, each newline is one row:\n'+'\n'.join(lines))
        jobs.append(dict(id=ident,source=str(source),destination=str(ASSETS/'english-v1'/(ident+'.png')),
            first_row=start,count=len(group),lines=lines,prompt=prompt))
    for card,second in zip(text['static_cards'],(140,151)):
        source=AUDIT/f'sampled/frame-{second+1:03}.png'
        prompt=('Use case: text-localization. Image1 is the EDIT TARGET, original game ending company credit. '
            'Replace all Japanese with EXACT English below; preserve pure black background and centered restrained two-line composition. '
            'One complete landscape4:3 bitmap; clean medium-weight WHITE sans-serif. Same size for both lines, '
            'about18px cap height on640x480, with comfortable line spacing. No graphics, other words, borders or watermark. '
            'English verbatim:\n'+'\n'.join(card['lines']))
        jobs.append(dict(id=card['id'],source=str(source),destination=str(ASSETS/'english-v1'/(card['id']+'.png')),
            lines=card['lines'],prompt=prompt))
    save(ASSETS/'credits-english-v1.prompts.json',jobs)
    print('Prepared',len(jobs),'ImageGen jobs; first',jobs[0]['lines'][:4],flush=True)


def ink_runs(mask,gap=3):
    runs=[]
    for y in np.flatnonzero(np.count_nonzero(mask,axis=1)>2):
        if runs and y-runs[-1][1]<=gap:runs[-1][1]=int(y)+1
        else:runs.append([int(y),int(y)+1])
    return runs


def cell_crops(image,lo,hi,cells):
    tile=image.crop((0,lo,image.width,hi))
    mask=np.asarray(tile.convert('L'))>100
    yy,xx=np.nonzero(mask)
    if not len(xx):raise ValueError('Blank generated row')
    if len(cells)==1 or cells[1] is None:
        return [tile.crop((int(xx.min()),0,int(xx.max())+1,hi-lo))]
    active=np.count_nonzero(mask,axis=0)>0
    empty=[]
    for x in range(int(xx.min()),int(xx.max())+1):
        if not active[x]:
            if empty and empty[-1][1]==x:empty[-1][1]=x+1
            else:empty.append([x,x+1])
    gaps=[(a,c) for a,c in empty if .25*image.width<(a+c)/2<.75*image.width]
    if not gaps:raise ValueError('Generated paired names have no gutter')
    a,c=max(gaps,key=lambda r:r[1]-r[0]);split=(a+c)//2
    if c-a<20:raise ValueError('Generated columns touch')
    result=[]
    for start,end in ((0,split),(split,image.width)):
        part=tile.crop((start,0,end,hi-lo));box=part.convert('L').point(lambda v:255 if v>100 else 0).getbbox()
        if not box:raise ValueError('Missing generated name column')
        result.append(part.crop((box[0],0,box[2],hi-lo)))
    return result


def lettering():
    text=media.read(TEXT);source_rows=media.read(AUDIT/'roll-rows-v2.json')['rows']
    jobs=media.read(ASSETS/'credits-english-v1.prompts.json')
    provenance=media.read(PROVENANCE)
    if provenance['text_sha256']!=media.sha(TEXT.read_bytes()) or provenance['prompts_sha256']!=media.sha((ASSETS/'credits-english-v1.prompts.json').read_bytes()):
        raise ValueError('Reviewed credit text/prompts changed')
    guards={r['id']:r for r in provenance['assets']}
    roll=Image.new('RGB',(320,4000),'black');report=[];cards={}
    source=Image.open(AUDIT/'original-roll-v2.png').convert('RGB')
    for job in jobs:
        path=ASSETS/'english-v1'/(job['id']+'.png')
        if media.sha(path.read_bytes())!=guards[job['id']]['sha256']:
            raise ValueError('Reviewed ImageGen pixels changed')
        image=Image.open(path).convert('RGB')
        spans=ink_runs(np.asarray(image.convert('L'))>100)
        if 'first_row' not in job:
            if len(spans)!=2:raise ValueError('Company card must have two text lines')
            box=image.convert('L').point(lambda a:255 if a>100 else 0).getbbox()
            # Whole generated company card lettering, common9px cap at native size.
            cap=spans[0][1]-spans[0][0];scale=9/cap
            crop=image.crop((box[0]-1,box[1]-1,box[2]+1,box[3]+1))
            tile=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
            frame=Image.new('RGB',(320,240),'black')
            frame.paste(tile,((320-tile.width)//2,120-tile.height//2))
            cards[job['id']]=frame
            report.append(dict(id=job['id'],scale=scale,lines=2,box=box,cap_height=9))
            continue
        if len(spans)!=job['count']:raise ValueError('Missing/wrapped/duplicate generated credit row '+job['id']+' '+str(len(spans)))
        entries=text['rows'][job['first_row']:job['first_row']+job['count']]
        # Common per-panel cap-height conversion, never word-specific stretching.
        capitals=[hi-lo for (lo,hi),r in zip(spans,entries) if not re.search('[gjpqy]',' '.join(c or '' for c in r['cells']))]
        cap=float(np.median(capitals));scale=9/cap
        for (lo,hi),entry in zip(spans,entries):
            row=source_rows[entry['index']];top=row['y']
            cells=cell_crops(image,lo,hi,entry['cells'])
            bounds=[]
            for column,cell in enumerate(cells):
                converted=cell.resize((max(1,round(cell.width*scale)),max(1,round(cell.height*scale))),Image.Resampling.LANCZOS)
                x=18 if column==0 else 162
                if converted.height>14 or x+converted.width>306 or (len(cells)==2 and column==0 and x+converted.width>156):
                    raise ValueError('English credit line outside common font/grid '+str(entry['index']))
                roll.paste(converted,(x,top))
                bounds.append([x,top,x+converted.width,top+converted.height])
            if entry.get('preserve_original_right'):
                # Unverified staff reading: preserve original Japanese pixels,
                # not a guessed romanization or a generated approximation.
                original=source.crop((112,row['y'],200,row['end']))
                if original.width+162>306:raise ValueError('Original name overflow')
                roll.paste(original,(162,top))
                bounds.append([162,top,250,top+original.height])
            report.append(dict(index=entry['index'],id=job['id'],cells=entry['cells'],source_y=top,
                native_boxes=bounds,panel_cap_height=cap,scale=scale,target_cap_height=9,
                original_unverified_name_preserved=bool(entry.get('preserve_original_right'))))
    if len([r for r in report if 'index' in r])!=133:raise ValueError('Credit row omitted')
    return roll,cards,report


def preview():
    roll,cards,report=lettering()
    roll.save(AUDIT/'english-roll.png')
    for name,card in cards.items():card.resize((640,480),Image.Resampling.NEAREST).save(AUDIT/(name+'-native-preview.png'))
    for start in range(0,133,36):
        group=[r for r in report if 'index' in r][start:start+36]
        sheet=Image.new('RGB',(1280,48*((len(group)+2)//3)),'#202020');draw=ImageDraw.Draw(sheet)
        for i,row in enumerate(group):
            x,y=i%3*426,i//3*48
            draw.text((x+3,y+3),str(row['index']),fill='white')
            tile=roll.crop((0,row['source_y']-1,320,row['source_y']+15))
            sheet.paste(tile.resize((384,19),Image.Resampling.NEAREST),(x+40,y+20))
        sheet.save(AUDIT/f'english-rows-{start//36:02}.png')
    save(AUDIT/'lettering-layout.json',dict(rows=report,rows_checked=133,common_native_cap_height=9,
        unverified_name_row=109,all_original_vertical_row_positions_preserved=True,
        generated_pixels_used=True,lettering_redraw=False))
    print('Native lettering layout passed:133 rows,2 company cards,one original name preserved.',flush=True)


def viewport(roll,offset):
    return roll.transform((320,240),Image.Transform.AFFINE,(1,0,0,0,1,float(offset)),
        resample=Image.Resampling.BICUBIC,fillcolor='black')


def encode():
    folder=ENCODED
    if folder.exists():raise ValueError('Preserve previous credit encoding')
    original=ORIGINAL.read_bytes()
    if media.sha(original)!=ORIGINAL_SHA:raise ValueError('Original credits changed')
    roll,cards,layout=lettering()
    reference=Image.open(AUDIT/'original-roll-v2.png').convert('RGB')
    reference_mask=np.asarray(reference).max(axis=2)>80
    padded=np.pad(reference_mask,((240,240),(0,0)))
    folder.mkdir()
    source_video=AUDIT/'original.m1v'
    if media.elementary(original,224)!=source_video.read_bytes():raise ValueError('Audit movie changed')
    expected=len(media.units(source_video.read_bytes()))
    source_log=(folder/'source-decode.log').open('wb')
    target_log=(folder/'encode.log').open('wb')
    decoder=subprocess.Popen([media.FFMPEG,'-v','error','-nostdin','-i',str(source_video),
        '-f','rawvideo','-pix_fmt','rgb24','-fps_mode','passthrough','pipe:1'],stdout=subprocess.PIPE,stderr=source_log)
    encoder=subprocess.Popen([media.FFMPEG,'-v','warning','-nostdin','-n','-f','rawvideo','-s','320x240',
        '-pix_fmt','rgb24','-r','24','-i','pipe:0','-an','-c:v','mpeg1video','-threads','2',
        '-q:v',str(QUALITY),'-g','12','-bf','0','-r','24','-pix_fmt','yuv420p','-f','mpeg1video',str(folder/'english.m1v')],
        stdin=subprocess.PIPE,stderr=target_log)
    edits=[];scores=[];count=0;unchanged=[]
    import hashlib
    untouched_source=hashlib.sha256();untouched_prepared=hashlib.sha256()
    try:
        while raw:=decoder.stdout.read(320*240*3):
            if len(raw)!=320*240*3:raise ValueError('Truncated decoded frame')
            im=Image.frombytes('RGB',(320,240),raw);kind=None
            if 96<=count<2952:
                # Recover exact native integer scroll phase per frame, avoiding
                # subpixel rounding assumptions. Speed remains32px/s at24fps.
                predicted=round((count-120)*4/3)
                mask=np.asarray(im).max(axis=2)>80
                amount=np.count_nonzero(mask);choices=[]
                for off in range(predicted-1,predicted+2):
                    sample=padded[off+240:off+480]
                    denom=amount+np.count_nonzero(sample)
                    score=2*np.count_nonzero(mask&sample)/denom if denom>30 else 1
                    choices.append((score,-abs(off-predicted),off))
                score,_,offset=max(choices)
                # A few clipped glyph pixels entering/leaving the viewport are
                # not enough evidence for a Dice-score motion assertion.
                if amount>=300:
                    scores.append(float(score))
                    # Fractional phases have resampled original glyph edges;
                    # integer third-frame anchors must match much more tightly.
                    required=.94 if count%3==0 else .70
                    if score<required:raise ValueError('Unverified credit scroll phase '+str((count,score)))
                im=viewport(roll,Fraction((count-120)*4,3));kind='scroll'
                edits.append(dict(frame=count,kind=kind,offset=offset,match_score=float(score)))
            elif 3264<=count<3480 or 3528<=count<3768:
                ident='development' if count<3480 else 'production'
                # Both company cards use a white-on-black fade. Preserve its
                # per-frame brightness, measured from the original text region.
                level=int(np.asarray(im)[96:140,30:290].max())
                frame=np.asarray(cards[ident]).astype('u2')
                im=Image.fromarray(((frame*level+127)//255).astype('u1'))
                kind=ident;edits.append(dict(frame=count,kind=kind,source_peak=level))
            prepared=im.tobytes()
            if kind is None:
                untouched_source.update(raw);untouched_prepared.update(prepared);unchanged.append(count)
                if prepared!=raw:raise ValueError('Untranslated title/logo/END frame changed before encoding')
            encoder.stdin.write(prepared)
            if count in (240,960,1536,2112,2448,3360,3624):
                im.resize((640,480),Image.Resampling.NEAREST).save(folder/f'prepared-frame-{count:04}.png')
            count+=1
    finally:
        decoder.stdout.close();encoder.stdin.close()
        dc=decoder.wait();ec=encoder.wait();source_log.close();target_log.close()
    if dc or ec or count!=expected:raise ValueError('Credits encode/decode frame count failed')
    video=(folder/'english.m1v').read_bytes()
    if len(media.units(video))!=expected or video[4:8]!=source_video.read_bytes()[4:8]:
        raise ValueError('Movie geometry/rate/frame count changed')
    result=media.remux(original,video)
    if result is None:raise ValueError('Credits exceed original movie allocation')
    target=folder/'STAFF.SFD';target.write_bytes(result)
    decoded=run(['-v','error','-xerror','-i',str(target),'-map','0:v:0','-map','0:a:0','-progress','pipe:1','-f','null','-'])
    frames=int(re.findall(rb'frame=(\d+)',decoded.stdout)[-1])
    if frames!=expected:raise ValueError('Independent Sofdec decode frame count differs')
    audio=[run(['-v','error','-xerror','-i',str(path),'-map','0:a:0','-c:a','pcm_s16le','-f','hash','-hash','sha256','pipe:1']).stdout for path in (ORIGINAL,target)]
    if audio[0]!=audio[1]:raise ValueError('Decoded music changed')
    if media.elementary(original,192)!=media.elementary(result,192):raise ValueError('Native ADX changed')
    # Decoded production frames, not just the uncompressed preparation.
    run(['-v','error','-i',str(target),'-vf',r'select=not(mod(n\,144))','-fps_mode','passthrough',str(folder/'decoded-%03d.png')])
    row=dict(status='verified-english-credits-movie',name='STAFF.SFD',bytes=len(result),sha256=media.sha(result),
        original_sha256=ORIGINAL_SHA,frames=frames,fps='24',duration_seconds=frames/24,
        source_and_target_geometry='320x240',quality=QUALITY,original_audio_pes_and_adx_byte_exact=True,
        audio_pcm_hash=audio[0].decode().strip(),frame_pts_exact=True,monotonic_scr=True,decode_ok=True,
        scrolling_rows=133,static_company_cards=2,unverified_name_preserved_row=109,
        original_row_positions_order_scroll_phase_preserved=True,min_scroll_match=min(scores),
        nontranslated_frame_count=len(unchanged),nontranslated_preencode_source_sha256=untouched_source.hexdigest(),
        nontranslated_preencode_target_sha256=untouched_prepared.hexdigest(),
        imagegen_provenance_sha256=media.sha(PROVENANCE.read_bytes()),text_sha256=media.sha(TEXT.read_bytes()),
        path=str(target.relative_to(ROOT)),runtime_verified=False)
    save(folder/'verification.json',row)
    save(folder/'frame-edits.json',edits)
    print('English credits movie verified:',row,flush=True)


def build():
    if OUT.exists():raise ValueError('Preserve existing complete pair')
    if shutil.disk_usage(OUT.anchor).free<3*1024**3:raise ValueError('Insufficient E: space')
    previous=media.read(SOURCE/'manifest.json')
    if previous['status']!=prior.STATUS or previous['executable_sha256']!=EXE_SHA:
        raise ValueError('Wrong cumulative source')
    b.domina.zero.combined.verify_files(SOURCE,previous['files'])
    b.domina.zero.combined.cue_checks(SOURCE)
    for disc in (1,2):
        row=next(r for r in previous['files'] if r['path']==b.track(SOURCE,disc).relative_to(SOURCE).as_posix())
        if row['sha256']!=TRACK_HASHES[disc]:raise ValueError('Wrong per-disc identity')
    movie=media.read(ENCODED/'verification.json');replacement=(ENCODED/'STAFF.SFD').read_bytes()
    if (movie['status']!='verified-english-credits-movie' or movie['sha256']!=media.sha(replacement)
        or movie['text_sha256']!=media.sha(TEXT.read_bytes())
        or movie['imagegen_provenance_sha256']!=media.sha(PROVENANCE.read_bytes())):
        raise ValueError('Movie verification missing/stale')
    source=b.track(SOURCE,2);original,lba=b.READER.read_file(source,'STAFF.SFD')
    if media.sha(original)!=ORIGINAL_SHA or len(original)!=len(replacement):
        raise ValueError('Wrong original movie/allocation')
    if media.elementary(original,192)!=media.elementary(replacement,192):raise ValueError('Music changed')
    print('Dry plan verified: Disc1 exact copy; Disc2 only STAFF.SFD and parity.',flush=True)
    OUT.mkdir();files=[];touched=[]
    for row in previous['files']:
        src,dst=SOURCE/row['path'],OUT/row['path'];dst.parent.mkdir(exist_ok=True)
        if row['path']==source.relative_to(SOURCE).as_posix():
            digest,touched=prior.copy_track(src,dst,TRACK_HASHES[2],[(lba-45000,replacement)])
            files.append(dict(path=row['path'],bytes=dst.stat().st_size,sha256=digest))
        else:
            with src.open('rb') as a,dst.open('xb') as c:shutil.copyfileobj(a,c,4*1024*1024)
            files.append(dict(row))
    target=b.track(OUT,2)
    with source.open('rb') as a,target.open('rb') as c:
        directory=list(b.READER.inject.iso_files(a))
        if directory!=list(b.READER.inject.iso_files(c)) or b.READER.inject._extent(a,45000,32768)!=b.READER.inject._extent(c,45000,32768):
            raise ValueError('Boot/directory changed')
    for name,_,_ in directory:
        actual=b.READER.read_file(target,name)[0]
        expected=replacement if name=='STAFF.SFD' else b.READER.read_file(source,name)[0]
        if actual!=expected:raise ValueError('Unexpected ISO change '+name)
        print('Verified payload',name,flush=True)
    b.domina.zero.combined.verify_files(OUT,files);b.domina.zero.combined.cue_checks(OUT)
    b.domina.zero.combined.verify_files(SOURCE,previous['files'])
    exe=(SOURCE/'1ST_READ.BIN').read_bytes()
    if media.sha(exe)!=EXE_SHA:raise ValueError('Executable changed')
    (OUT/'1ST_READ.BIN').write_bytes(exe)
    for path in SOURCE.glob('*-preview.png'):shutil.copy2(path,OUT/path.name)
    shutil.copytree(SOURCE/'story-card-previews',OUT/'story-card-previews')
    shutil.copy2(SOURCE/'story-card-coverage.json',OUT/'story-card-coverage.json')
    previews=OUT/'credits-previews';previews.mkdir()
    for path in ENCODED.glob('decoded-*.png'):shutil.copy2(path,previews/path.name)
    for path in AUDIT.glob('*-native-preview.png'):shutil.copy2(path,previews/path.name)
    for path in AUDIT.glob('english-rows-*.png'):shutil.copy2(path,previews/path.name)
    shutil.copy2(TEXT,OUT/TEXT.name);shutil.copy2(PROVENANCE,OUT/PROVENANCE.name)
    shutil.copy2(ENCODED/'verification.json',OUT/'credits-movie-verification.json')
    (OUT/'Black Matrix AD.m3u').write_text(''.join(f'disc{d}/Black-Matrix Advanced (Japan) (Disc {d}).cue\n' for d in (1,2)))
    report=dict(status=STATUS,build_version=VERSION,files=files,source=str(SOURCE),source_files=previous['files'],
        executable_sha256=EXE_SHA,disc1_exact_source_copy=True,movie=movie,
        changed_raw_sectors=touched,only_disc2_staff_movie_and_sector_parity_changed=True,
        all_story_cards_code_fonts_ui_scripts_other_movies_preserved=True,
        original_audio_pes_adx_pcm_and_movie_duration_preserved=True,
        saves_and_profile_configuration_unchanged=True,renderer_launch_only_settings=b.renderer_settings(),
        private_local_only=True,gameplay_verified=False,physical_hardware_verified=False,
        unresolved=['One staff name at scrolling row109 right has unverified reading; original Japanese lettering retained.'])
    save(OUT/'manifest.json',report)
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'README.txt').write_text(
        'PRIVATE cumulative0.1.8: English ending credits in Disc2 STAFF.SFD.\n'
        'All133 scrolling rows and2 company cards checked;37 role headings covered.\n'
        'Staff/company spellings checked against original images and Dreamcast credit records.\n'
        'One staff name (row109 right) retained in Japanese because its reading is unverified.\n'
        'Actual ImageGen lettering, native9px cap-height/common column grid; original row positions/order.\n'
        'Original32px/second smooth scroll,24fps,4058 frames and169.083s video retained.\n'
        'Music ADX/PES and decoded PCM exact. Title/MPEG Sofdec/copyright/END retained.\n'
        'Disc1 exact0.1.7 copy. Disc2 ONLY STAFF movie/parity changes; all earlier fixes/story cards retained.\n'
        'Use project Play - Disc 2 - English Credits.cmd (or Disc1) after closing Flycast.\n'
        'SAME original E: VMUs, latest old saves PortA Slot2; no card/save/config writes.\n'
        'Movie full decode and disc readbacks verified. Fresh gameplay/hardware playback still pending.\n'
        'Separate Equip oversized font/topic alignment remains pending. No M: output.\n'
        'Originals/previous outputs untouched. Private local binaries only; no publication/upload/release.\n')
    print('New private complete English credits pair verified:',OUT,flush=True)


def launch(disc):
    b.domina.zero.launch(disc,build=OUT,status=STATUS,settings=b.renderer_settings())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--audit',action='store_true');p.add_argument('--stitch',action='store_true');p.add_argument('--prepare',action='store_true');p.add_argument('--preview',action='store_true');p.add_argument('--encode',action='store_true');p.add_argument('--build',action='store_true');p.add_argument('--launch',type=int,choices=(1,2));a=p.parse_args()
    if a.audit:audit()
    elif a.stitch:stitch()
    elif a.prepare:prepare()
    elif a.preview:preview()
    elif a.encode:encode()
    elif a.build:build()
    elif a.launch:launch(a.launch)
