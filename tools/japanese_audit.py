"""Conservative Japanese record inventory; candidates are not patch authority."""
import argparse,json,re,struct,sys
from pathlib import Path
from collections import Counter
import bmtext,inject,scriptpack
ROOT=Path(__file__).resolve().parents[1]
JP=re.compile(r'[\u3041-\u3096\u30a1-\u30fa\u3400-\u9fff]')

def candidates(data):
    valid={}
    def char(w):
        if w not in valid:
            t=bmtext.decode_char(w)
            valid[w]=t if (w==0xA0FF or w in bmtext.GAIJI or 0x8140<=w<=0x9872) and '{' not in t else None
        return valid[w]
    occupied=0
    for off in range(0,len(data)-4,2):
        if off<occupied:continue
        count=struct.unpack_from('<H',data,off)[0]
        if not 2<=count<=192 or off+2+count*2>len(data):continue
        words=struct.unpack_from('<%dH'%count,data,off+2)
        letters=[char(w) for w in words]
        if any(t is None for t in letters):continue
        text=''.join(letters)
        if JP.search(text):
            occupied=off+2+count*2
            yield dict(offset=off,count=count,text=text)

def archive(disc,name):
    with (ROOT/('Black-Matrix Advanced (Japan) (Disc %d) (Track 3).bin'%disc)).open('rb') as f:
        lba,size=inject.find(f,name);return inject._extent(f,lba,size)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,default=ROOT/'build/reusable-atlas-noto-ui-r34')
    args=parser.parse_args()
    out=ROOT/'build/japanese-audit';out.mkdir(exist_ok=True)
    translations=scriptpack.load_translations(sorted((ROOT/'script/en').glob('*.en.tsv')))
    original=archive(1,'SCENARIO.DAT')
    pending=[dict(offset=o,kind=k,text=t) for o,k,v,t in bmtext.strings(original) if o not in translations]
    (out/'scenario-pending.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2),encoding='utf-8')
    for name in ('1ST_READ.BIN','PARAMETA.DAT','SYSTEM.DAT'):
        source=archive(1,name);current=(args.build/name).read_bytes()
        rows=[]
        for r in candidates(source):
            o=r['offset'];size=2+2*r['count']
            r['unchanged']=source[o:o+size]==current[o:o+size]
            if r['unchanged']:rows.append(r)
        (out/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,len(rows),'candidates;',len({r['text'].strip() for r in rows}),'unique',flush=True)
    print('Unmapped scenario records',len(pending))
    print('Scope: length-prefixed text candidates, not bitmap/movie OCR or proof that all screens are English.')

if __name__=='__main__':main()
