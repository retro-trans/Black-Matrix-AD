"""Reviewed translations for remaining parameter-table categories.

Names have independently checked slot padding. Descriptions keep 19-column
rows and counts. No stats, effects, prices or item IDs are modified.
"""
import hashlib,json,struct,textwrap
from pathlib import Path
import bmtext,patchline,uistr
ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA='eecb976aa94994b411e5345abbada7899988798bf5fa4007b2dc31d27171a3cf'
CATALOG=ROOT/'script/ui/remaining_parameters.json'

def original():
    data=(ROOT/'extracted/PARAMETA.DAT').read_bytes()
    if hashlib.sha256(data).hexdigest()!=SOURCE_SHA:raise ValueError('unknown parameters source')
    return data

def encode(row):
    text=row['english'];slots=row['slots']
    if row['category'].endswith('name'):
        if len(text)>slots:raise ValueError('name too long: '+text)
        count=len(text);text=text.ljust(slots)
    else:
        lines=text.split('\n') if '\n' in text else textwrap.wrap(text,19,break_long_words=False,break_on_hyphens=False)
        if len(lines)>slots//19 or any(len(s)>19 for s in lines):raise ValueError('description too long: '+text)
        text=''.join(s.ljust(19) for s in lines).ljust(slots);count=slots
    return struct.pack('<%dH'%(slots+1),count,*(patchline.to_sjis(c) for c in text))

def entries():
    rows=json.loads(CATALOG.read_text(encoding='utf-8'));source=original();seen=set()
    allocations={'unit_name':6,'item_name':8,'magic_name':8,'latent_name':7,
                 'item_description':38,'magic_description':38,'latent_description':38,
                 'latent_details':38,'help_description':57}
    spans=[]
    for row in rows:
        o=row['offset'];size=2+row['slots']*2
        if allocations.get(row['category'])!=row['slots']:raise ValueError('unknown parameter allocation')
        if not 0<=o<len(source)-size+1:raise ValueError('parameter outside archive')
        if o in seen:raise ValueError('duplicate parameter record')
        seen.add(o)
        if hashlib.sha256(source[o:o+size]).hexdigest()!=row['sha256']:raise ValueError('source record changed')
        _,count,japanese=next(uistr.walk(source,o,1))
        if japanese!=row['japanese'] or count>row['slots']:raise ValueError('source text/count mismatch')
        if row['category'].endswith('name'):
            if source[o+2+count*2:o+size]!=b'\x40\x81'*(row['slots']-count):raise ValueError('name padding not free')
        elif count!=row['slots']:raise ValueError('description count mismatch')
        spans.append((o,o+size))
        encode(row)
    spans.sort()
    if any(a[1]>b[0] for a,b in zip(spans,spans[1:])):raise ValueError('overlapping parameter fields')
    return rows

def patch(data):
    source=original();pending=[]
    if len(data)!=len(source):raise ValueError('parameter size mismatch')
    for row in entries():
        o=row['offset'];target=encode(row);old=source[o:o+len(target)]
        if data[o:o+len(target)] not in (old,target):raise ValueError('unknown parameter record at %X'%o)
        pending.append((o,target))
    for o,target in pending:data[o:o+len(target)]=target
    return {'records':len(pending),'scope':'reviewed name/description/help fields only'}

def records():
    result=set()
    for row in entries():
        payload=encode(row);count=struct.unpack_from('<H',payload)[0]
        reverse={patchline.to_sjis(ch):ch for ch in set(row['english']+' ') if ch!='\n'}
        text=''.join(reverse[w] for w in struct.unpack_from('<%dH'%row['slots'],payload,2))
        result.update((text,text[:count]))
    return sorted(result)
