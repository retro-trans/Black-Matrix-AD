"""Complete activity item names and an ASCII-only, icon-safe pickup template."""
import struct
from pathlib import Path
import activity_localization as activity
import patchline
import vwf

ROOT=activity.ROOT
TABLE_START,TABLE_END,STRIDE=0xE3010,0xE3B50,32
TABLE_SHA='dd5a8c7dc4838a6d7bae51e75b31af1b0be4d1cd349abe3e2bb5cd076e4c3575'
POINTER=0x3E8C0
OLD_TEMPLATE=0x88C98
STORAGE=0x8C0F3000
STORAGE_END=STORAGE+0x100  # After native Units alias; before BEAR_TAB at F3464.
PREFIX='      Got '
SUFFIX='!'
ITEM_CONTROL=0xB005
WINDOW_COLUMNS_OFFSET=0x3E7D2
WINDOW_COLUMNS=20  # Six icon spaces + "Got " + nine name cells + "!".
TRANSLATIONS={
    'チョコレート':'Chocolate','スーパーＴシャツ':'Super Tee','スーパー長靴':'SuperBoot',
    '毛染め（金髪）':'Blond Dye','キャンディー':'Candy','ケーキ':'Cake','クッキー':'Cookie',
    'グミ':'Gummies','おせんべい':'Crackers','ガム':'Gum','リンゴ':'Apple',
    '謎の鉱石':'Odd Ore','ガーベラ':'Gerbera','ひまわり':'Sunflower','つばき':'Camellia',
    'すずらん':'Lily Bell','カブ':'Turnip','サツマイモ':'SweetPot.','白菜':'Napa',
    'ジャガイモ':'Potato','毛虫':'Caterplr','青リンゴ':'GreenApp.',
    'ご主人様の服':'MstrCloth','日記':'Diary','サラダ':'Salad','スープ':'Soup',
    'オムレツ':'Omelet','カレー':'Curry','春巻き':'SpringRl','漬け物':'Pickles',
    '特製ハンバーグ':'Sp.Hambg','くいしんぼステーキ':'Big Steak','キングパフェ':'KingPrft',
    '鉄人のやきいも':'Chef Yam','学生服（男）':'B Uniform','学生服（女）':'G Uniform','宝石':'Jewel','首輪':'Collar',
    '不思議な道具':'Odd Tool','不思議な粉':'OddPowder','不思議な巻物':'OddScroll',
    'スペシャルメニュー':'Spec.Menu','きぐるみ':'Costume','うさぎ':'Rabbit','キツネ':'Fox',
    'イノシシ':'Boar','まき':'Firewood','バナナ':'Banana','キャベツ':'Cabbage',
    'ピーマン':'Pepper','謎のお菓子':'Odd Snack','魚':'Fish','青虫':'Grub','さなぎ':'Pupa',
    'チョウチョ':'Butterfly','卵':'Egg','鳥':'Bird','カメ':'Turtle','やきとり':'Yakitori',
    '焼き肉':'BBQ Meat','焼き魚':'Grld Fish','やきいも':'Baked Yam','薬':'Medicine',
}


def entries():
    source=activity.original()
    if activity.digest(source[0xE3000:0xE4000])!=TABLE_SHA:
        raise ValueError('Unknown activity item table')
    result=[]
    for o in range(TABLE_START,TABLE_END,STRIDE):
        count=struct.unpack_from('<H',source,o)[0]
        if not 1<=count<=9:raise ValueError('Unexpected activity name count')
        words=struct.unpack_from('<9H',source,o+2)
        # Three originals retain a parenthesized qualifier after their display
        # count. Translate that stored text too; attributes begin at +20.
        japanese=b''.join(struct.pack('>H',w) for w in words).decode('cp932').rstrip('\u3000')
        english=TRANSLATIONS[japanese]
        if len(english)>9 or not english.isascii():raise ValueError('Activity label exceeds its nine-cell field')
        result.append(dict(offset=o,japanese=japanese,english=english))
    return result


def payload(name):
    return struct.pack('<10H',len(name),*(patchline.to_sjis(c) for c in name.ljust(9)))


def patch_event(data):
    source=activity.original();pending=[]
    for row in entries():
        o=row['offset'];target=payload(row['english'])
        accepted=[source[o:o+20],target]
        if o in activity.NAMES:
            accepted.append(activity.name_payload(activity.NAMES[o][1])+source[o+18:o+20])
        if data[o:o+20] not in accepted:raise ValueError('Unknown activity item edit at %X'%o)
        pending.append((o,target))
    for o,target in pending:data[o:o+20]=target
    return dict(records=len(pending),unique_names=len({r['english'] for r in entries()}),field_cells=9)


def template():
    words=[patchline.to_sjis(c) for c in PREFIX]+[ITEM_CONTROL]+[patchline.to_sjis(c) for c in SUFFIX]
    return struct.pack('<%dH'%(len(words)+1),len(words),*words)


def patch_executable(data):
    source=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
    # The caller reads this same record's count for window measurement and
    # its pointer for expansion. One data-pointer relocation updates both.
    old=struct.pack('<6H',5,0x8140,ITEM_CONTROL,0x83B1,0x83B2,0x83B3)
    if source[OLD_TEMPLATE:OLD_TEMPLATE+len(old)]!=old or data[OLD_TEMPLATE:OLD_TEMPLATE+len(old)]!=old:
        raise ValueError('Unknown original pickup template')
    old_pointer=struct.pack('<I',vwf.LOAD_BASE+OLD_TEMPLATE)
    new_pointer=struct.pack('<I',STORAGE)
    lo,hi=STORAGE-vwf.LOAD_BASE,STORAGE_END-vwf.LOAD_BASE
    if not (0x8C0F3000<=STORAGE<STORAGE_END<=vwf.BEAR_TAB):raise ValueError('Pickup record reservation overlaps metrics')
    target=template().ljust(hi-lo,b'\0')
    # Physical window width and character-node capacity are separate. The
    # stock pickup descriptor allocates only 15 columns and one row, which
    # splits the 17-cell Rabbit message after "      Got Rabbi".
    old_columns=struct.pack('<H',0xE00F)
    new_columns=struct.pack('<H',0xE000|WINDOW_COLUMNS)
    if source[WINDOW_COLUMNS_OFFSET:WINDOW_COLUMNS_OFFSET+8]!=bytes.fromhex('0fe0e28101e0e381'):
        raise ValueError('Unknown pickup window descriptor instructions')
    if data[WINDOW_COLUMNS_OFFSET:WINDOW_COLUMNS_OFFSET+2] not in (old_columns,new_columns):
        raise ValueError('Unknown pickup window column edit')
    if data[WINDOW_COLUMNS_OFFSET+2:WINDOW_COLUMNS_OFFSET+8]!=source[WINDOW_COLUMNS_OFFSET+2:WINDOW_COLUMNS_OFFSET+8]:
        raise ValueError('Unknown pickup window row/descriptor edit')
    if max(map(len,records()))>WINDOW_COLUMNS or WINDOW_COLUMNS>100:
        raise ValueError('Pickup message exceeds its one-row node capacity')
    if any(source[lo:hi]) or data[lo:hi] not in (bytes(hi-lo),target):
        raise ValueError('Pickup record reservation is occupied')
    if data[POINTER:POINTER+4] not in (old_pointer,new_pointer):raise ValueError('Unknown pickup record pointer')
    space=data[vwf.ADV_TAB-vwf.LOAD_BASE]
    if space*6<32:raise ValueError('Pickup icon spacer is narrower than its sprite')
    # Largest source count is 9. Stock width routine adds name count (including
    # one conservative control cell) and rounds 28px cells to 32px panels.
    width=(struct.unpack_from('<H',target)[0]+9)*28
    panels=width//32+1
    if panels*32>640:raise ValueError('Pickup window would exceed screen')
    data[lo:hi]=target
    data[POINTER:POINTER+4]=new_pointer
    data[WINDOW_COLUMNS_OFFSET:WINDOW_COLUMNS_OFFSET+2]=new_columns
    return dict(template=PREFIX+'{item}'+SUFFIX,icon_spacer=space*6,max_panel_width=panels*32,
                pointer_offset=POINTER,storage=STORAGE,columns=WINDOW_COLUMNS,rows=1,
                scope='template relocation and pickup-only column immediate; no global layout changes')


def records():
    return sorted({PREFIX+r['english']+SUFFIX for r in entries()})


if __name__=='__main__':
    import json
    path=ROOT/'build/1ST_READ.vwf.bin'
    data=bytearray(path.read_bytes())
    report=patch_executable(data)
    path.write_bytes(data)
    print(json.dumps(report,indent=2))
