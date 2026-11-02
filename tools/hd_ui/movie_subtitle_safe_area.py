"""Reburn existing Disc2 cues higher, preserving native audio and exact timing."""
import argparse
import concurrent.futures
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np
from PIL import Image
import results_party_native as prior
import prologue_timing_trial as timing

ROOT = prior.ROOT
OUT = ROOT/'build/movie-safe-area-2026-11-02'
MEDIA = OUT/'encoded'
ORIGINALS = ROOT/'extracted/disc2-movies-20260925'
TEXT = ROOT/'tools/disc2_subtitle_text.json'
TEXT_SHA = 'e544afcecaa0eef5f5efbe4ffe093faae0f46f061446f6a6c4dedf52738a5bb4'
MARGIN = 28  # Was10. All caption ink must end at/before source row214.
FPS = {1:Fraction(24000,1001),2:Fraction(24),3:Fraction(25),4:Fraction(30000,1001),
       5:Fraction(30),6:Fraction(50),7:Fraction(60000,1001),8:Fraction(60)}
FFMPEG = shutil.which('ffmpeg')


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,data):path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')


def subtitles():
    if sha(TEXT.read_bytes()) != TEXT_SHA:raise ValueError('Subtitle words/times changed')
    return read(TEXT)['clips']


def ts(seconds):
    whole,cs = divmod(round(seconds*100),100)
    minute,s = divmod(whole,60);h,m = divmod(minute,60)
    return f'{h}:{m:02}:{s:02}.{cs:02}'


def ass(cues):
    result = ('[Script Info]\nScriptType: v4.00+\nPlayResX: 320\nPlayResY: 240\n'
        'WrapStyle: 2\nScaledBorderAndShadow: yes\n[V4+ Styles]\n'
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, '
        'Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, '
        'Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
        f'Style: Default,Arial,14,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,1,0,2,12,12,{MARGIN},1\n'
        '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n')
    last = 0
    for start,end,text in cues:
        if not last<=start<end or len(text.splitlines())>2 or any(c in text for c in '{}'):
            raise ValueError('Unsafe subtitle cue')
        last=end
        result += f'Dialogue: 0,{ts(start)},{ts(end)},Default,,0,0,0,,{text.replace(chr(10),chr(92)+"N")}\n'
    return result


def run(args,*,cwd=OUT,log=None):
    if not FFMPEG:raise ValueError('Existing FFmpeg unavailable')
    p = subprocess.run([FFMPEG,'-hide_banner','-nostdin',*args],cwd=cwd,capture_output=True)
    if log is not None:log.write_bytes(p.stderr)
    if p.returncode:raise ValueError(p.stderr.decode(errors='replace')[-3000:])
    return p.stdout


def verify_layout():
    texts = list(dict.fromkeys(t for cues in subtitles().values() for _,_,t in cues))
    (OUT/'layout.ass').write_text(ass([(i,i+1,t) for i,t in enumerate(texts)]),encoding='utf-8')
    raw = run(['-v','error','-f','lavfi','-i',f'color=c=black:s=320x240:r=1:d={len(texts)}',
               '-vf','ass=layout.ass','-pix_fmt','gray','-f','rawvideo','pipe:1'])
    masks = np.frombuffer(raw,'u1').reshape(len(texts),240,320)
    rows = []
    for text,mask in zip(texts,masks):
        ys,xs=np.where(mask>100)
        if not len(xs):raise ValueError('Blank subtitle layout')
        box = [int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]
        if box[0]<10 or box[2]>310 or box[1]<160 or box[3]>214:
            raise ValueError('Subtitle outside safe area '+repr((text,box)))
        rows.append(dict(text=text,ink=box,bottom_clearance=240-box[3]))
    save(OUT/'layout-verification.json',dict(margin_v=MARGIN,unique_texts=len(rows),rows=rows,
          all_ink_above_row215=True,words_and_cue_times_unchanged=True))
    return rows


def elementary(data,kind):return b''.join(p['payload'] for p in timing.packets(data) if p['kind']==kind)


def units(video):
    starts = [m.start() for m in re.finditer(b'\0\0\1\0',video)]
    boundaries = [0]
    for a,b in zip(starts,starts[1:]):
        headers = [video.find(code,a+4,b) for code in (b'\0\0\1\xb3',b'\0\0\1\xb8')]
        boundaries.append(min([b]+[x for x in headers if x>=0]))
    boundaries.append(len(video))
    if not starts:raise ValueError('Missing pictures')
    return [video[a:b] for a,b in zip(boundaries,boundaries[1:])]


def remux(original,video):
    frames = units(video);fps = FPS[video[7]&15]
    native = timing.packets(original)
    audio = [p for p in native if p['kind']==192]
    packets = [(p['pts'],0,i,p['raw'][12:]) for i,p in enumerate(audio)]
    for frame,unit in enumerate(frames):
        pic = unit.index(b'\0\0\1\0')
        if unit[pic+5]>>3&7 not in (1,2):raise ValueError('Unexpected B frame')
        pts = round(Fraction(frame*90000,1)/fps)
        for part,start in enumerate(range(0,len(unit),2012)):
            payload = timing.video_pes(unit[start:start+2012],pts if part==0 else None,
                                      pts if part==0 else None)
            packets.append((pts,1,frame*10000+part,payload))
    packets.sort(key=lambda x:x[:3])
    rate = ((original[9]&127)<<15)|(original[10]<<7)|(original[11]>>1)
    head = lambda clock:b'\0\0\1\xba'+timing.stamp(clock,2)+original[9:12]
    result = bytearray(b''.join(head(0)+original[i+12:i+2048] for i in range(0,6144,2048)))
    clock = 0
    for n,(pts,_,__,payload) in enumerate(packets,3):
        clock = max(clock,min(n*2048*90000//(rate*50),pts))
        result += head(clock)+payload
    result += b'\0\0\1\xb9'+b'\xff'*2044
    if len(result)>len(original):return None
    result += b'\xff'*(len(original)-len(result))
    after = timing.packets(result)
    if b''.join(p['payload'] for p in after if p['kind']==224)!=video:
        raise ValueError('Video mux round trip failed')
    if [p['raw'][12:] for p in after if p['kind']==192]!=[p['raw'][12:] for p in audio]:
        raise ValueError('Native audio PES changed')
    previous_clock = -1
    for i in range(0,len(result),2048):
        block = result[i:i+2048]
        if block[:4]==b'\0\0\1\xb9':break
        scr = timing.timestamp(block[4:9])
        if scr<previous_clock:raise ValueError('Backwards movie clock')
        previous_clock = scr
    points = [p['pts'] for p in after if p['kind']==224 and p['pts'] is not None]
    if points != [round(Fraction(i*90000,1)/fps) for i in range(len(frames))]:
        raise ValueError('Video frame timestamps differ')
    return bytes(result)


def encode_one(name):
    cues = subtitles()[name]
    folder = MEDIA/name;folder.mkdir(parents=True,exist_ok=True)
    source = ORIGINALS/(name+'.SFD');original = source.read_bytes()
    record = next(r for r in read(ORIGINALS/'manifest.json')['files'] if r['name']==source.name)
    if sha(original)!=record['sha256']:raise ValueError('Original movie changed')
    meta = folder/'verification.json'
    if meta.exists():
        row=read(meta)
        if row['text_sha256']!=TEXT_SHA or row['margin_v']!=MARGIN or sha((folder/source.name).read_bytes())!=row['sha256']:
            raise ValueError('Preserve different previous encoding')
        return row
    video = elementary(original,224);fps=FPS[video[7]&15];frames=len(units(video))
    (folder/'original.m1v').write_bytes(video)
    (folder/'raised.ass').write_text(ass(cues),encoding='utf-8')
    for quality in (2,3,4,5,6,8):
        run(['-v','warning','-y','-threads','2','-i','original.m1v','-vf','ass=raised.ass',
             '-an','-c:v','mpeg1video','-threads','2','-q:v',str(quality),'-g','12','-bf','0',
             '-r',str(fps),'-pix_fmt','yuv420p','-f','mpeg1video','raised.m1v'],
             cwd=folder,log=folder/f'encode-q{quality}.log')
        replacement = (folder/'raised.m1v').read_bytes()
        if len(units(replacement))!=frames or replacement[4:8]!=video[4:8]:
            raise ValueError('Frame count/rate/geometry changed')
        result = remux(original,replacement)
        if result is not None:break
    else:raise ValueError('Movie exceeds original allocation')
    target = folder/source.name;target.write_bytes(result)
    progress = run(['-v','error','-xerror','-threads','2','-i',str(target),'-map','0:v:0','-map','0:a:0',
                    '-progress','pipe:1','-f','null','-'],log=folder/'decode.log')
    decoded_frames = int(re.findall(rb'frame=(\d+)',progress)[-1])
    if decoded_frames!=frames:raise ValueError('Independent full decode frame count differs')
    pcm = [run(['-v','error','-xerror','-i',str(p),'-map','0:a:0','-c:a','pcm_s16le',
                '-f','hash','-hash','sha256','pipe:1']) for p in (source,target)]
    if pcm[0]!=pcm[1]:raise ValueError('Decoded audio PCM changed')
    sample = 5 if name=='MS1205' else sum(cues[0][:2])/2
    run(['-v','error','-y','-ss',str(sample),'-i',str(target),'-frames:v','1',str(folder/'preview.png')])
    current = prior.prior.builder.READER.read_file(prior.prior.builder.track(prior.OUT,2),source.name)[0]
    if elementary(current,192)!=elementary(original,192):raise ValueError('Current movie uses different audio')
    row = dict(name=source.name,bytes=len(result),sha256=sha(result),current_sha256=sha(current),
        original_sha256=sha(original),frames=frames,fps=str(fps),quality=quality,margin_v=MARGIN,
        text_sha256=TEXT_SHA,audio_pcm_hash=pcm[0].decode().strip(),audio_pes_byte_exact=True,
        original_geometry_and_duration=True,frame_pts_exact=True,monotonic_scr=True,decode_ok=True,
        subtitle_words_and_cue_times_unchanged=True,path=str(target.relative_to(ROOT)))
    save(meta,row);print(name,'raised subtitles; exact audio/frames/times verified',flush=True)
    return row


def encode(only=None):
    OUT.mkdir(exist_ok=True);MEDIA.mkdir(exist_ok=True)
    verify_layout()
    names = list(subtitles()) if only is None else only
    if any(n not in subtitles() for n in names):raise ValueError('Unknown captioned movie')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(encode_one,names))
    if only is None:
        save(MEDIA/'manifest.json',dict(status='verified-raised-disc2-subtitles',clips=rows,
            margin_v=MARGIN,text_sha256=TEXT_SHA,original_audio_preserved=True,
            prologue_and_other_uncaptioned_movies_unchanged=True,runtime_verified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--only',nargs='+');a=p.parse_args();encode(a.only)
