"""Port shared localized data only through exact original-content matches."""
import hashlib
from pathlib import Path
import inject,pac,japanese_audit

def leaves(data):
    def descend(o,n,key):
        children=list(pac.members(data,o))
        if children:
            for i,start,size in children:yield from descend(start,size,key+(i,))
        else:yield key,o,n
    for i,o,n in pac.groups(data):
        if i:yield from descend(o,n,(i,))

def transfer_system(patched):
    one=japanese_audit.archive(1,'SYSTEM.DAT');two=japanese_audit.archive(2,'SYSTEM.DAT')
    target=bytearray(two);index={};used=[];unmatched=[];spans=[]
    for key,o,n in leaves(two):index.setdefault(hashlib.sha256(two[o:o+n]).digest(),[]).append((key,o,n))
    for key,o,n in leaves(one):
        if patched[o:o+n]==one[o:o+n]:continue
        matches=index.get(hashlib.sha256(one[o:o+n]).digest(),[])
        if not matches:unmatched.append(list(key));continue
        for tkey,to,tn in matches:
            if tn!=n:raise ValueError('shared member size mismatch')
            target[to:to+n]=patched[o:o+n];spans.append((to,to+n))
            used.append(dict(source=list(key),target=list(tkey),source_offset=o,target_offset=to,size=n))
    # Do not silently omit changed members outside decoded archive children.
    covered=bytearray(one)
    for key,o,n in leaves(one):covered[o:o+n]=patched[o:o+n]
    if covered!=patched:raise ValueError('SYSTEM changes outside member payloads')
    if unmatched:raise ValueError('changed SYSTEM members differ on Disc 2: '+str(unmatched))
    return target,used

def install(out,exe,parameters,scenario,system):
    out=Path(out);track=out/'disc2/Black-Matrix Advanced (Japan) (Disc 2) (Track 3).bin'
    # Prove the two original executables, parameter tables and scripts match.
    for name in ('1ST_READ.BIN','PARAMETA.DAT','SCENARIO.DAT'):
        if japanese_audit.archive(1,name)!=japanese_audit.archive(2,name):raise ValueError('disc-specific '+name)
    system2,members=transfer_system(system)
    targets={'1ST_READ.BIN':exe,'PARAMETA.DAT':parameters,'SCENARIO.DAT':scenario,'SYSTEM.DAT':system2}
    for name,data in targets.items():
        path=out/(name.replace('.DAT','.disc2.DAT').replace('.BIN','.disc2.BIN'));path.write_bytes(data)
        if name=='SCENARIO.DAT':inject.relocate(str(track),name,str(path))
        else:inject.put(str(track),name,str(path))
        with track.open('rb') as f:
            lba,size=inject.find(f,name)
            if inject._extent(f,lba,size)!=data:raise ValueError('shared Disc 2 readback failed')
    return dict(payloads={n:hashlib.sha256(d).hexdigest() for n,d in targets.items()},system_members=members,
                scope='shared script, executable and parameters; exact-match SYSTEM members only')
