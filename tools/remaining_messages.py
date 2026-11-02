"""Source-bound fixed executable messages; no pointers or controls changed."""
import hashlib,json,struct
from pathlib import Path
import patchline
ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'script/ui/remaining_messages.json'
STAT_MESSAGE_OFFSETS=frozenset((0x88B80,0x88B96,0x88BAC,0x88BC2,0x88BD8,0x88BEE,
                               0x88C04,0x88C1A,0x88C30,0x88C44,0x88C58,0x88C6C))

def entries():
    source=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    rows=json.loads(CATALOG.read_text(encoding='utf-8'));seen=set()
    for r in rows:
        o=r['offset'];size=2+2*r['count']
        if o in seen or hashlib.sha256(source[o:o+size]).hexdigest()!=r['sha256']:raise ValueError('message source mismatch')
        seen.add(o)
        if len(r['english'])>r['count']:raise ValueError('message exceeds allocation: '+r['english'])
        lines=r['english'].splitlines()
        if len(lines)>2 or any(len(s)>19 for s in lines):raise ValueError('message exceeds two 19-column rows')
    return rows

def display_count(r):
    if r['offset'] in STAT_MESSAGE_OFFSETS:
        if not r['english'].endswith('\n') or r['english'].count('\n')!=1:
            raise ValueError('Stat message must end at its single line break')
        return len(r['english'])
    return r['count']

def payload(r,legacy=False):
    count=r['count'] if legacy else display_count(r)
    # Retain fixed storage and all pointer targets. Only the displayed count
    # excludes the unused spaces AFTER stat messages' final line break.
    return struct.pack('<%dH'%(r['count']+1),count,*(patchline.to_sjis(ch) for ch in r['english'].ljust(r['count'])))

def patch(data):
    source=(ROOT/'extracted/1ST_READ.BIN').read_bytes();pending=[]
    for r in entries():
        o=r['offset'];target=payload(r)
        if data[o:o+len(target)] not in (source[o:o+len(target)],payload(r,legacy=True),target):raise ValueError('unknown existing message at %X'%o)
        pending.append((o,target))
    for o,target in pending:data[o:o+len(target)]=target
    return {'records':len(pending),'scope':'fixed executable text only; no pointers, controls or save data'}

def records():
    return sorted({s for r in entries() if '\n' not in r['english'] for s in (r['english'],r['english'].ljust(r['count']))})
