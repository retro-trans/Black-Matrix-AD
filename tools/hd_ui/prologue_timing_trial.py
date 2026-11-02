"""Private timing-only Sofdec trial. No transcoding or source-image writes.

Keep the supplied captioned MPEG elementary stream exactly; restore native ADX
PES packets, frequent picture timestamps and explicit audio/video interleaving.
This is an experiment, not a claimed playback fix.
"""
import argparse
import bisect
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path('M:/Black-Matrix-AD-private-tests/prologue-timing-v2')
ORIGINAL = Path('M:/Black-Matrix-AD-private-tests/opening-stop-20261102-18560/original-PROLOGUE.SFD')
SUPPLIED = ROOT / 'translated_clips/PROLOGUE.SFD'
ORIGINAL_SHA = '0be68894de4ecf64f59acc96fbc951f1956843b4e1cb6507747c4ada2456d923'
SUPPLIED_SHA = '84f0a94aad61027022856cca027f181abe923f53a2d11215339868a9e1e3abfa'


def sha(b): return hashlib.sha256(b).hexdigest()


def timestamp(b):
    return ((b[0] >> 1 & 7) << 30) | (b[1] << 22) | ((b[2] >> 1) << 15) | (b[3] << 7) | (b[4] >> 1)


def stamp(value, prefix):
    if not 0 <= value < 1 << 33: raise ValueError('Timestamp range')
    return bytes([(prefix << 4) | ((value >> 29) & 14) | 1,
                  (value >> 22) & 255, ((value >> 14) & 254) | 1,
                  (value >> 7) & 255, ((value << 1) & 254) | 1])


def packets(data):
    result = []
    for off in range(0, len(data), 2048):
        b = data[off:off + 2048]
        if b[:4] == b'\0\0\1\xb9': break
        if b[:4] != b'\0\0\1\xba': raise ValueError('Invalid pack')
        if b[15] not in (192, 224): continue
        pos = 18
        while b[pos] == 255: pos += 1
        if b[pos] & 192 == 64: pos += 2
        pts = dts = None
        if b[pos] & 240 in (32, 48):
            pts = timestamp(b[pos:pos + 5])
            if b[pos] & 240 == 48: dts = timestamp(b[pos + 5:pos + 10])
            pos += 10 if dts is not None else 5
        elif b[pos] == 15: pos += 1
        else: raise ValueError('Invalid MPEG1 PES')
        end = 18 + int.from_bytes(b[16:18], 'big')
        result.append(dict(kind=b[15], payload=b[pos:end], pts=pts, dts=dts, raw=b))
    return result


def pictures(video):
    """Use GOP timecode and temporal_reference, never byte offsets as time."""
    result = []; base = None
    for m in re.finditer(b'\0\0\1[\xb8\x00]', video):
        pos = m.start()
        if m[0][-1] == 184:
            word = int.from_bytes(video[pos + 4:pos + 8], 'big')
            if word >> 31: raise ValueError('Drop-frame stream not supported')
            base = (((word >> 26 & 31) * 60 + (word >> 20 & 63)) * 60 + (word >> 13 & 63)) * 30 + (word >> 7 & 63)
        else:
            if base is None: raise ValueError('Picture without GOP')
            temp = int.from_bytes(video[pos + 4:pos + 6], 'big') >> 6
            kind = video[pos + 5] >> 3 & 7
            if kind not in (1, 2, 3): raise ValueError('Unsupported picture type')
            result.append(dict(offset=pos, frame=base + temp, kind=kind, temporal_reference=temp))
    if sorted(r['frame'] for r in result) != list(range(len(result))):
        raise ValueError('Missing/duplicate display frames')
    return result


def video_pes(payload, pts=None, dts=None):
    # Match the native 46KiB video STD descriptor and fixed 12-byte PES header.
    header = b'\x60\x2e'
    header += stamp(pts, 3) + stamp(dts, 1) if dts is not None else stamp(pts, 2) if pts is not None else b'\x0f'
    header = b'\xff' * (12 - len(header)) + header
    body = header + payload
    pes = b'\0\0\1\xe0' + len(body).to_bytes(2, 'big') + body
    spare = 2036 - len(pes)
    if spare:
        if spare < 6: raise ValueError('Insufficient padding PES space')
        pes += b'\0\0\1\xbe' + (spare - 6).to_bytes(2, 'big') + b'\xff' * (spare - 6)
    if len(pes) != 2036: raise ValueError('PES size')
    return pes


def remux(original, supplied):
    native = packets(original); old = packets(supplied)
    video = b''.join(p['payload'] for p in old if p['kind'] == 224)
    native_video = b''.join(p['payload'] for p in native if p['kind'] == 224)
    frames = pictures(video); old_frames = pictures(native_video)
    if [(r['frame'], r['kind']) for r in frames] != [(r['frame'], r['kind']) for r in old_frames]:
        raise ValueError('Native/supplied frame ordering differs')
    seq = video.index(b'\0\0\1\xb3')
    if video[seq + 7] & 15 != 5: raise ValueError('Expected native 30fps')
    # Preserve every audio PES byte, including native timestamps and padding.
    audio = [p for p in native if p['kind'] == 192]
    if b''.join(p['payload'] for p in audio) != b''.join(p['payload'] for p in old if p['kind'] == 192):
        raise ValueError('Supplied audio is not the original ADX')
    events = [(max(0, p['pts'] - 270000), 0, i, p['raw'][12:]) for i, p in enumerate(audio)]
    offsets = [r['offset'] for r in frames]; start = 0; index = 0
    while start < len(video):
        count = min(2018, len(video) - start)
        if 0 < len(video) - start - count < 6: count -= 6
        first = bisect.bisect_left(offsets, start)
        last = bisect.bisect_left(offsets, start + count)
        pts = dts = None
        if first < last:
            row = frames[first]; pts = row['frame'] * 3000
            if row['kind'] != 3: dts = max(3000, pts - 3000)
        current = max(0, bisect.bisect_right(offsets, start) - 1)
        # Decode order stays intact even with B-frame presentation reordering.
        due = max(0, current * 3000 - 90000)
        events.append((due, 1, index, video_pes(video[start:start + count], pts, dts)))
        start += count; index += 1
    events.sort(key=lambda e:e[:3])
    rate = ((original[9] & 127) << 15) | (original[10] << 7) | (original[11] >> 1)
    result = bytearray()
    for offset in range(0,6144,2048):
        result += b'\0\0\1\xba' + stamp(0,2) + original[9:12] + original[offset+12:offset+2048]
    last_clock = 0
    for n, (_, _, _, pes) in enumerate(events, 3):
        clock = max(0, n * 2048 * 90000 // (rate * 50) - 90000)
        head = b'\0\0\1\xba' + stamp(clock, 2) + original[9:12]
        result += head + pes; last_clock = clock
    result += b'\0\0\1\xb9' + b'\xff' * 2044
    if len(result) > len(original): raise ValueError('Does not fit original movie extent')
    result += b'\xff' * (len(original) - len(result))
    check = packets(result)
    if b''.join(p['payload'] for p in check if p['kind'] == 224) != video: raise ValueError('Video changed')
    if [p['raw'][12:] for p in check if p['kind'] == 192] != [p['raw'][12:] for p in audio]: raise ValueError('Audio PES changed')
    return bytes(result), dict(frames=len(frames),video_sha256=sha(video),
        audio_sha256=sha(b''.join(p['payload'] for p in audio)),
        audio_pes_byte_exact=True,video_elementary_byte_exact=True,
        video_timestamp_packets=sum(p['kind']==224 and p['pts'] is not None for p in check),
        last_pack_clock_seconds=last_clock/90000,packet_count=len(events))


def encode():
    if OUT.exists(): raise ValueError('Preserve earlier trial')
    a=ORIGINAL.read_bytes();b=SUPPLIED.read_bytes()
    if sha(a)!=ORIGINAL_SHA or sha(b)!=SUPPLIED_SHA: raise ValueError('Movie identities changed')
    result, report = remux(a,b)
    OUT.mkdir(parents=True)
    (OUT/'PROLOGUE.SFD').write_bytes(result)
    report.update(status='timing-only-trial-runtime-unverified',sha256=sha(result),
                  bytes=len(result),original_sha256=sha(a),supplied_sha256=sha(b))
    (OUT/'timing.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


def verify_media():
    """Compare every decoded picture and PCM sample, independent of PTS."""
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg: raise ValueError('Local FFmpeg is required')
    report=dict(sha256=sha((OUT/'PROLOGUE.SFD').read_bytes()),comparisons=[])
    results=[]
    for path in (SUPPLIED,OUT/'PROLOGUE.SFD'):
        r=subprocess.run([ffmpeg,'-hide_banner','-nostdin','-v','error','-xerror',
            '-threads','1','-i',str(path),'-map','0:v:0','-vf','settb=1/30,setpts=N',
            '-fps_mode','passthrough','-f','framemd5','-'],capture_output=True,text=True,check=True)
        frames=[line.rsplit(',',1)[-1].strip() for line in r.stdout.splitlines() if line and not line.startswith('#')]
        audio=subprocess.run([ffmpeg,'-hide_banner','-nostdin','-v','error','-xerror',
            '-i',str(path),'-map','0:a:0','-c:a','pcm_s16le','-f','hash','-hash','sha256','-'],
            capture_output=True,text=True,check=True)
        results.append((frames,audio.stdout.strip()))
        report['comparisons'].append(dict(path=str(path),frames=len(frames),
            frame_hash_sequence_sha256=sha('\n'.join(frames).encode()),
            audio_pcm=audio.stdout.strip(),decoder_diagnostics=r.stderr))
    if results[0]!=results[1] or len(results[0][0])!=4295: raise ValueError('Decoded media differs')
    report.update(status='passed',same_decoded_frames_and_audio=True,
                  video_timestamp_reset_for_hash_comparison_only=True)
    (OUT/'media-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('All 4295 decoded English frames and complete PCM audio identical.',flush=True)


def build():
    import numpy as np
    import original_prologue_control as control
    import buddy_tv_control as tv
    import mode1_sector
    report=json.loads((OUT/'timing.json').read_text())
    movie=(OUT/'PROLOGUE.SFD').read_bytes()
    if sha(movie)!=report['sha256']: raise ValueError('Trial movie changed')
    if not (OUT/'media-verification.json').is_file(): raise ValueError('Verify decoded media first')
    media=json.loads((OUT/'media-verification.json').read_text())
    if media['sha256']!=sha(movie) or media['status']!='passed': raise ValueError('Media verification stale')
    folder=OUT/'disc1'
    if folder.exists(): raise ValueError('Preserve prior trial disc')
    if shutil.disk_usage(OUT.anchor).free<2*1024**3: raise ValueError('Insufficient trial space')
    source=control.SOURCE/control.TRACK
    if control.digest(source)!=control.SOURCE_SHA: raise ValueError('Unknown TV control source')
    plan=control.plan();first=plan['first_sector'];last=first+plan['sector_count']
    folder.mkdir();target=folder/control.TRACK
    h=hashlib.sha256();old_h=hashlib.sha256();sector=0
    with source.open('rb') as src,target.open('xb') as dst:
        while raw:=src.read(2352*4096):
            old_h.update(raw);count=len(raw)//2352;lo=max(first,sector);hi=min(last,sector+count)
            after=bytearray(raw)
            if lo<hi:
                selected=bytearray(raw[(lo-sector)*2352:(hi-sector)*2352])
                a=np.frombuffer(selected,'u1').reshape(-1,2352)
                a[:,16:2064]=np.frombuffer(movie[(lo-first)*2048:(hi-first)*2048],'u1').reshape(-1,2048)
                fixed=mode1_sector.regenerate(bytes(selected))
                after[(lo-sector)*2352:(hi-sector)*2352]=fixed
            dst.write(after);h.update(after);sector+=count
    if old_h.hexdigest()!=control.SOURCE_SHA: raise ValueError('Source changed during copy')
    # Full-track allowlist/readback. No raw bytes outside movie extent may differ.
    sector=0
    with source.open('rb') as src,target.open('rb') as dst:
        while a:=src.read(2352*4096):
            b=dst.read(len(a));count=len(a)//2352;lo=max(first,sector);hi=min(last,sector+count)
            if lo<hi:
                start=(lo-sector)*2352;end=(hi-sector)*2352
                if a[:start]!=b[:start] or a[end:]!=b[end:]: raise ValueError('Out-of-scope raw edits')
                rows=np.frombuffer(b[start:end],'u1').reshape(-1,2352)
                original_rows=np.frombuffer(a[start:end],'u1').reshape(-1,2352)
                if not np.array_equal(rows[:,:16],original_rows[:,:16]): raise ValueError('Sector headers changed')
                if rows[:,16:2064].tobytes()!=movie[(lo-first)*2048:(hi-first)*2048]: raise ValueError('Movie readback differs')
                if mode1_sector.regenerate(b[start:end])!=b[start:end]: raise ValueError('Invalid raw parity')
            elif a!=b: raise ValueError('Out-of-scope track change')
            sector+=count
    reader=control.READER
    with source.open('rb') as f:
        directory=list(reader.inject.iso_files(f));boot=reader.inject._extent(f,45000,32768)
    with target.open('rb') as f:
        if list(reader.inject.iso_files(f))!=directory or reader.inject._extent(f,45000,32768)!=boot: raise ValueError('Boot/directory changed')
    for name,_,_ in directory:
        a,_=reader.read_file(source,name);b,_=reader.read_file(target,name)
        if b!=(movie if name=='PROLOGUE.SFD' else a): raise ValueError('Unexpected ISO payload: '+name)
    files=[dict(path='disc1/'+target.name,sha256=h.hexdigest(),bytes=target.stat().st_size)]
    for src in control.SOURCE.iterdir():
        if src.is_file() and src!=source:
            dst=folder/src.name;shutil.copy2(src,dst)
            if control.digest(src)!=control.digest(dst): raise ValueError('Companion mismatch')
            files.append(dict(path='disc1/'+src.name,sha256=control.digest(dst),bytes=dst.stat().st_size))
    for row in files:
        if control.digest(OUT/row['path'])!=row['sha256']: raise ValueError('Final disc hash mismatch')
    if control.digest(source)!=control.SOURCE_SHA or sha(ORIGINAL.read_bytes())!=ORIGINAL_SHA or sha(SUPPLIED.read_bytes())!=SUPPLIED_SHA:
        raise ValueError('Inputs changed')
    exe,_=reader.read_file(source,'1ST_READ.BIN');(OUT/'1ST_READ.BIN').write_bytes(exe)
    cue=next(folder.glob('*.cue'))
    tv.prepare(OUT/'play',3,cue,OUT/'1ST_READ.BIN',tv.EXE_SHA)
    manifest=dict(status='timing-only-disc-prepared-runtime-pending',files=files,movie=report,
        source_track_sha256=control.SOURCE_SHA,only_movie_and_its_sector_parity_changed=True,
        same_executable_and_tv_settings_as_working_original_movie_control=True,
        private_local_only=True,originals_and_other_builds_unchanged=True,automated_input=False)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (OUT/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in files))
    (OUT/'README.txt').write_text('PRIVATE timing-only PROLOGUE test, not a verified fix.\n'
        'Same TV executable/settings as the original-movie comparison. Only PROLOGUE changes.\n'
        'English MPEG video and original ADX audio are byte-exact; packet timing/interleaving differ.\n'
        'Choose New Game and watch past the statue scene, then to the end. No saves imported.\n')
    print('Prepared private trial:',OUT,flush=True)


def launch():
    import buddy_tv_control as tv
    report=json.loads((OUT/'manifest.json').read_text())
    for row in report['files']:
        with (OUT/row['path']).open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=row['sha256']: raise ValueError('Trial disc changed')
    tv.launch(OUT/'play',next((OUT/'disc1').glob('*.cue')),OUT/'1ST_READ.BIN',
              instructions='Choose New Game and watch the prologue past the statue scene, then to the end.')


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--encode',action='store_true')
    p.add_argument('--verify-media',action='store_true')
    p.add_argument('--build',action='store_true');p.add_argument('--launch',action='store_true');args=p.parse_args()
    if args.encode: encode()
    if args.verify_media: verify_media()
    if args.build: build()
    if args.launch: launch()
