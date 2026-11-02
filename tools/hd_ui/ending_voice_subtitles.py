"""Identify voice-only ending artwork and recover original audio read-only."""
import argparse
import json
import re
import struct
import subprocess
import shutil
import hashlib
import os
import sys
import wave

import numpy as np
from PIL import Image,ImageDraw

import credits_english as prior
import pvr_atlas
import psi2
import scriptpack

ROOT=prior.ROOT
b=prior.b
SOURCE=prior.OUT
OUT=ROOT/'build/ending-voice-subtitles-2026-11-02'
SCREENSHOT='C:/Users/Binh/AppData/Local/Temp/codex-clipboard-5272d626-2dd6-48b4-869d-f476c47009bf.png'


def save(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')


def fingerprint(image):
    a=np.asarray(image.convert('RGB').resize((40,30),Image.Resampling.BILINEAR)).astype('f4')
    # Global lighting/fade-in invariant comparison, not a screenshot edit.
    a=a.reshape(-1);return a/max(float(np.linalg.norm(a)),1)


def identify():
    if OUT.exists():raise ValueError('Preserve existing ending audit')
    OUT.mkdir()
    with Image.open(SCREENSHOT) as im:
        width=round(im.height*4/3);left=(im.width-width)//2
        target=fingerprint(im.crop((left,0,left+width,im.height)))
    ranked=[];errors=[]
    for name in ('EVENT.DAT','SYSTEM.DAT','OASOBI.DAT','GRAPHIC.DAT'):
        data=b.READER.read_file(b.track(SOURCE,2),name)[0]
        count=0
        for match in re.finditer(b'SCL ',data):
            off=match.start()
            try:
                cols,rows,_,pages=pvr_atlas.scl_layout(data,off)
                if cols<20 or rows<8:continue
                im=pvr_atlas.decode_scl(data,off);count+=1
                score=float(np.dot(target,fingerprint(im)))
                if score>.85:
                    ranked.append((score,name,off,im.copy()))
            except (ValueError,IndexError,OverflowError) as e:
                errors.append(dict(archive=name,offset=off,error=str(e)))
        print('Compared',name,count,'large pictures',flush=True)
    ranked.sort(key=lambda r:r[0],reverse=True);rows=[]
    for i,(score,name,off,im) in enumerate(ranked[:16]):
        filename=f'match-{i:02}-{name.lower()}-{off:08x}.png'
        im.resize((640,480),Image.Resampling.NEAREST).save(OUT/filename)
        rows.append(dict(rank=i,score=score,archive=name,offset=off,image=filename))
    sheet=Image.new('RGB',(1280,260*((len(rows)+3)//4)),'#202020');draw=ImageDraw.Draw(sheet)
    for i,row in enumerate(rows):
        x,y=i%4*320,i//4*260
        with Image.open(OUT/row['image']) as im:sheet.paste(im.resize((320,240)),(x,y+20))
        draw.text((x+3,y+3),f"{row['rank']} {row['archive']} {row['offset']:x} {row['score']:.4f}",fill='white')
    sheet.save(OUT/'matches.png')
    save(OUT/'artwork-matches.json',dict(source=str(SOURCE),matches=rows,decode_errors=errors,
        source_unchanged=True,no_emulator_or_save_writes=True))
    print('Best',rows[:3],flush=True)


def recover():
    """Decode candidates without changing any game data; exact mapping audited below."""
    dest=OUT/'audio';dest.mkdir(exist_ok=False)
    scenario=b.READER.read_file(b.track(SOURCE,2),'SCENARIO.DAT')[0]
    program=next(p for i,s,p in psi2.groups(scenario) if i==558)
    walk=psi2.walk(program);bounds=sorted(walk.boundaries)+[walk.end]
    cues=[]
    for pos,end in zip(bounds,bounds[1:]):
        if struct.unpack_from('<H',program,pos)[0]!=0x1a:continue
        assert struct.unpack_from('<H',program,pos+2)[0]==1
        field=(pos+4+3)&~3
        voice=struct.unpack_from('<I',program,field)[0]
        cues.append(dict(offset=pos,voice=voice))
    pcm=b.READER.read_file(b.track(SOURCE,2),'PCM.DAT')[0]
    groups=scriptpack.split_groups(pcm)
    # The filesystem's in-memory table starts after CMP2's first pair (header
    # entry). Runtime resource N is therefore on-disk container entry N+1.
    rows=[]
    for voice in sorted({c['voice'] for c in cues}):
        raw=groups[voice+1];path=dest/f'{voice:04x}.aica';path.write_bytes(raw)
        # Native voice stream setup 8C06B49A: Yamaha ADPCM, mono, 0x7800 Hz.
        # WAV wrapper allows FFmpeg's native AICA decoder to inspect the data.
        fmt=struct.pack('<HHIIHHH',0x20,1,30720,15360,1,4,0)
        wav=b'RIFF'+struct.pack('<I',4+8+len(fmt)+8+len(raw))+b'WAVEfmt '+struct.pack('<I',len(fmt))+fmt+b'data'+struct.pack('<I',len(raw))+raw
        wrapped=dest/f'{voice:04x}.aica.wav';wrapped.write_bytes(wav)
        out=dest/f'{voice:04x}.wav'
        subprocess.run([shutil.which('ffmpeg'),'-v','error','-i',str(wrapped),'-ar','16000','-ac','1','-c:a','pcm_s16le',str(out)],check=True)
        rows.append(dict(voice=voice,container_group=voice+1,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),wav=str(out)))
    save(OUT/'voice-inventory.json',dict(group=558,cues=cues,audio=rows,
         codec='Yamaha ADPCM',native_rate=30720,mapping_status='native filesystem header skip; needs ASR/context corroboration'))
    print('Recovered',len(rows),'clips',flush=True)


def transcribe(model_name,joined=False,no_vad=False,minimum=0,slow=False,translate=False,context=False):
    os.environ['HF_HUB_OFFLINE']='1';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    sys.path.insert(0,str(ROOT/'build/retranslation-review-runtime'))
    from faster_whisper import WhisperModel
    cache=__import__('pathlib').Path('C:/Users/Binh/.cache/huggingface/hub')
    snapshot=next((cache/f'models--Systran--faster-whisper-{model_name}'/'snapshots').iterdir())
    model=WhisperModel(str(snapshot),device='cpu',compute_type='int8',cpu_threads=2,num_workers=1,local_files_only=True)
    inv=json.loads((OUT/'voice-inventory.json').read_text());dest=OUT/(f'asr-{model_name}'+('-no-vad' if no_vad else '')+('-slow' if slow else '')+('-translate' if translate else '')+('-context' if context else ''));dest.mkdir(exist_ok=True)
    if joined:
        rows=[];audio=[];position=0
        for row in inv['audio']:
            with wave.open(row['wav'],'rb') as wav:part=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype('f4')/32768
            rows.append(dict(voice=row['voice'],start=position,end=position+len(part)/16000))
            audio.extend((part,np.zeros(16000,dtype='f4')));position+=len(part)/16000+1
        samples=np.concatenate(audio)
        segs,info=model.transcribe(samples,language='ja',task='transcribe',beam_size=5,temperature=0,
            condition_on_previous_text=False,vad_filter=False,word_timestamps=True)
        segs=[dict(start=s.start,end=s.end,text=s.text,avg_logprob=s.avg_logprob,
             no_speech_prob=s.no_speech_prob,words=[dict(start=w.start,end=w.end,word=w.word,probability=w.probability) for w in (s.words or [])]) for s in segs]
        save(dest/'joined-no-vad.json',dict(rows=rows,segments=segs,status='unreviewed ASR candidate; concatenated with one-second gaps'))
        print('Joined transcription complete',flush=True);return
    for row in inv['audio']:
        if row['voice']<minimum:continue
        path=dest/f"{row['voice']:04x}.json"
        if path.exists():continue
        with wave.open(row['wav'],'rb') as wav:
            assert wav.getframerate()==16000 and wav.getsampwidth()==2 and wav.getnchannels()==1
            samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype('f4')/32768
        if slow:
            proc=subprocess.run([shutil.which('ffmpeg'),'-v','error','-i',row['wav'],'-af','atempo=0.8','-f','f32le','pipe:1'],capture_output=True,check=True)
            samples=np.frombuffer(proc.stdout,dtype='<f4')
        options={}
        if context:
            # Proper-name vocabulary only, not a suggested transcript.
            options=dict(initial_prompt='登場人物：アベル、ドミナ、プリカ、クレージュ、ミシェット、プラハ、ゼロ、ヨハネ、ルピルピ、ルカ。',
                repetition_penalty=1.15,no_repeat_ngram_size=3)
            samples=np.concatenate((np.zeros(16000,dtype='f4'),samples,np.zeros(16000,dtype='f4')))
        segs,info=model.transcribe(samples,language='ja',task='translate' if translate else 'transcribe',beam_size=5,temperature=0,
            condition_on_previous_text=False,vad_filter=not no_vad,
            vad_parameters=dict(min_silence_duration_ms=500,speech_pad_ms=200),word_timestamps=True,**options)
        segs=[dict(start=s.start,end=s.end,text=s.text,avg_logprob=s.avg_logprob,
             no_speech_prob=s.no_speech_prob,words=[dict(start=w.start,end=w.end,word=w.word,probability=w.probability) for w in (s.words or [])]) for s in segs]
        result=dict(voice=row['voice'],model=model_name,duration=len(samples)/16000,
             duration_after_vad=info.duration_after_vad,segments=segs,status='unreviewed ASR candidate')
        save(path,result);print(hex(row['voice']),''.join(s['text'] for s in segs),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--identify',action='store_true');p.add_argument('--recover',action='store_true');p.add_argument('--transcribe',choices=['small','large-v2','large-v3']);p.add_argument('--joined',action='store_true');p.add_argument('--no-vad',action='store_true');p.add_argument('--minimum',type=lambda x:int(x,0),default=0);p.add_argument('--slow',action='store_true');p.add_argument('--translate',action='store_true');p.add_argument('--context',action='store_true');a=p.parse_args()
    if a.identify:identify()
    if a.recover:recover()
    if a.transcribe:transcribe(a.transcribe,a.joined,a.no_vad,a.minimum,a.slow,a.translate,a.context)
