"""Pack the user-selected ImageGen artwork into a NEW private native disc pair.

Format conversion only: no image regeneration, retouching, cropping, panels or
new lettering. Preserve full 4:3 composition, converting to the existing640x240
RGB565 tiled background (displayed at640x480). No runtime allocations change.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
import master_selection_prompt as master

ROOT=master.ROOT
ASSET=ROOT/'assets/ui/master-selection/choose-your-master-imagegen-v1.png'
ASSET_SHA='c88b94788d975731215cd6d28e9d864cf895607f3aa708ab470abcd463a78db1'
OUT=Path('M:/Black Matrix AD - Patched Discs - ImageGen - 2026-11-02')
STATUS='private-imagegen-selection-runtime-pending'
REVIEW=master.REVIEW/'imagegen-packed-native-preview.png'


def native_image():
    if master.names.sha(ASSET.read_bytes())!=ASSET_SHA:raise ValueError('Reviewed ImageGen asset changed')
    with Image.open(ASSET) as original:
        if original.width*3!=original.height*4:raise ValueError('Expected full4:3 ImageGen composition')
        if original.mode=='RGBA' and original.getchannel('A').getextrema()!=(255,255):
            raise ValueError('Unexpected transparent game background')
        size=original.size
        image=original.convert('RGB').resize((640,240),Image.Resampling.LANCZOS)
    return image,size


def quantized(image):
    a=np.array(image,dtype=np.uint32)
    words=((a[:,:,0]*31+127)//255)<<11|((a[:,:,1]*63+127)//255)<<5|((a[:,:,2]*31+127)//255)
    return Image.fromarray(np.stack(((words>>11&31)*255//31,(words>>5&63)*255//63,
                                    (words&31)*255//31),axis=-1).astype('u1'))


def patch(source):
    if master.names.sha(source[master.OFFSET:master.OFFSET+master.LENGTH])!=master.LEAF_SHA:
        raise ValueError('Unknown original master-selection member')
    cols,rows,descriptors,pages=master.pvr_atlas.scl_layout(source,master.OFFSET)
    if (cols,rows,len(pages))!=(40,15,3):raise ValueError('Native background allocation changed')
    native,size=native_image();result=bytearray(source)
    tiles=master.pvr_atlas.encode_scl(result,master.OFFSET,native)
    decoded=master.pvr_atlas.decode_scl(result,master.OFFSET)
    if decoded.tobytes()!=quantized(native).tobytes():raise ValueError('RGB565 native readback mismatch')
    nc,nr,nd,newpages=master.pvr_atlas.scl_layout(result,master.OFFSET)
    if (nc,nr,newpages)!=(cols,rows,pages):raise ValueError('Atlas allocation changed')
    allowed=np.zeros(len(source),dtype=bool)
    allowed[master.OFFSET+32:master.OFFSET+32+600*4]=True
    for offset in pages:allowed[offset+16:offset+16+131072]=True
    changes=np.flatnonzero(np.frombuffer(source,'u1')!=np.frombuffer(result,'u1'))
    if not len(changes) or np.any(~allowed[changes]):raise ValueError('Unrelated archive bytes changed')
    return bytes(result),decoded,dict(text=master.text(),method='existing ImageGen asset converted to nativeRGB565',
        imagegen_asset=str(ASSET),imagegen_asset_sha256=ASSET_SHA,source_image_size=size,
        native_size=[640,240],display_size=[640,480],member=[4],
        source_member_sha256=master.LEAF_SHA,native_rgb_sha256=master.names.sha(decoded.tobytes()),
        native_system_sha256=master.names.sha(result),native_tiles=tiles,tile_capacity=len(pages)*256,
        changed_system_bytes=len(changes),no_added_banner=True,no_runtime_or_allocation_changes=True,
        entire_selected_background_replaced=True,original_background_pixel_exact=False,
        all_other_members_headers_code_fonts_and_names_preserved=True)


def preview():
    source,_=master.source_payload(1,'SYSTEM.DAT');_,image,report=patch(source)
    REVIEW.parent.mkdir(exist_ok=True)
    image.resize((640,480),Image.Resampling.NEAREST).save(REVIEW)
    print(json.dumps(report,indent=2))
    print('Dry run only. Disc files and game processes unchanged. Native preview:',REVIEW,flush=True)


def build():
    master.build(out=OUT,patcher=patch,status=STATUS)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');a=p.parse_args()
    if a.build:build()
    else:preview()
