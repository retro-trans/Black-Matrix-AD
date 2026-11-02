"""Fresh outline typography and copper frame geometry for the shared Status UI.

No original raster contours are interpolated: source ink bounds only anchor new
font outlines to existing sprite UVs. The original frame renderer is retained.
"""
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import panel_redraw
import interface_art

SERIF=Path('C:/Windows/Fonts/timesbd.ttf')
NUMBER=Path('C:/Windows/Fonts/times.ttf')
ITALIC=Path('C:/Windows/Fonts/timesi.ttf')
SANS=Path('C:/Windows/Fonts/arialbd.ttf')
BUTTON_EM=9.5
BUTTON_BASELINE=11.25
BUTTON_LEFT=2


def button_caption(text,width=32):
    """One font/em/baseline for all captions; never fit each word to a box."""
    face=ImageFont.truetype(str(SANS),round(BUTTON_EM*4))
    if width not in (32,40,56):raise ValueError('unexpected button sprite width')
    left,top,right,bottom=face.getbbox(text,anchor='ls')
    if (right+BUTTON_LEFT*4>width*4-4 or bottom+BUTTON_BASELINE*4>60
            or left+BUTTON_LEFT*4<0 or top+BUTTON_BASELINE*4<0):
        raise ValueError('button caption exceeds shared metrics')
    mask=Image.new('L',(width*4,64))
    ImageDraw.Draw(mask).text((BUTTON_LEFT*4,BUTTON_BASELINE*4),text,
                             font=face,fill=255,anchor='ls')
    box=mask.getbbox()
    if box is None or box[2]>width*4-4 or box[3]>60:
        raise ValueError('button caption exceeds shared metrics')
    a=np.zeros((64,width*4,4),dtype='uint8')
    # Same gradient coordinates as well: descenders do not change the color
    # or perceived size of the rest of a word.
    t=np.clip((np.arange(64)-18)/27,0,1)
    for c,(top,bottom) in enumerate(zip((255,201,78),(185,85,10))):
        a[:,:,c]=(top*(1-t)+bottom*t)[:,None]
    a[:,:,3]=np.array(mask)
    return Image.fromarray(a)


def ink_bounds(native):
    a=np.array(native.convert('RGBA'))
    mask=(a[:,:,:3].max(axis=2)>65)&(a[:,:,3]>0)
    box=Image.fromarray((mask*255).astype('uint8')).getbbox()
    if box is None:raise ValueError('empty glyph')
    return box


def lettering(text,size,box,font=SERIF,gold=True,occupancy=1.0):
    """Rasterize new vector outlines at 4x; exact target ink/UV footprint."""
    w,h=size;x,y,xx,yy=box
    if not (0<=x<xx<=w and 0<=y<yy<=h):raise ValueError('glyph outside slot')
    if not 0<occupancy<=1:raise ValueError('invalid glyph occupancy')
    # Keep the original visual center/advance, but leave air on all four sides.
    cx,cy=(x+xx)*2,(y+yy)*2
    gw,gh=max(1,round((xx-x)*4*occupancy)),max(1,round((yy-y)*4*occupancy))
    gx,gy=round(cx-gw/2),round(cy-gh/2)
    face=ImageFont.truetype(str(font),256)
    probe=Image.new('L',(max(512,len(text)*300),512))
    ImageDraw.Draw(probe).text((16,16),text,font=face,fill=255,stroke_width=0)
    crop=probe.getbbox()
    if crop is None:raise ValueError('empty lettering')
    mask=Image.new('L',(w*4,h*4))
    glyph=probe.crop(crop).resize((gw,gh),Image.Resampling.LANCZOS)
    mask.paste(glyph,(gx,gy))
    # Smooth copper/gold vertical material gradient, no pixel-art source data.
    a=np.zeros((h*4,w*4,4),dtype='uint8')
    top,bottom=((255,201,78),(185,85,10)) if gold else ((250,249,246),(190,190,202))
    t=np.clip((np.arange(h*4)-gy)/max(1,gh-1),0,1)
    for c in range(3):a[:,:,c]=(np.array(top)[c]*(1-t)+np.array(bottom)[c]*t)[:,None]
    a[:,:,3]=np.array(mask)
    return Image.fromarray(a)


def frame_tree():
    root=ET.fromstring(panel_redraw.ART.read_text())
    for element in root.iter():
        if 'stroke-width' in element.attrib:
            element.set('stroke-width','0.6')
            element.set('stroke','#381b07')
        if element.get('fill')=='#843900':element.set('fill','#a35212')
        if element.get('fill')=='#a54a08':element.set('fill','#b15b13')
    # Replace the filled C-like silhouettes with thin interlocking key outlines.
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag.rsplit('}',1)[-1]=='polygon':parent.remove(child)
    ns='{http://www.w3.org/2000/svg}'
    traces=[[(2,49),(18,49),(18,53),(10,53),(10,55),(5,55),(5,59),(10,59),(10,63),(2,63)],
            [(9,49),(9,53)],[(14,49),(14,53)],
            [(18,49),(24,49),(24,51),(20,51)],
            [(10,59),(18,59),(18,63),(25,63)],[(14,59),(14,63)],
            [(8,57),(11,55)],[(8,57),(11,57)]]
    for mirrored in (False,True):
        for points in traces:
            for (x,y),(xx,yy) in zip(points,points[1:]):
                if mirrored:x,xx=96-x,96-xx
                ET.SubElement(root,ns+'line',dict(x1=str(x),y1=str(y),x2=str(xx),y2=str(yy),
                    stroke='#a65312',**{'stroke-width':'0.85'}))
    return root


def frame(scale=4):return panel_redraw.artwork(scale,frame_tree())


def divider():
    # Dedicated dark bars use the simpler keys in the user's reference.
    flat=panel_redraw.artwork(4,finish=False).crop((0,192,384,256))
    a=np.array(flat)
    # Paint only the INTERIOR. Painting every row erased the horizontal rails
    # from the middle sprite, turning two bars into one unbordered dark block.
    a[4:60,112:280,:3]=(32,12,0)
    return panel_redraw.copper_finish(Image.fromarray(a),4)


def common(native,rows):
    updates=[((0,0,96,80),frame(),'copper panels with key corners')]
    labels={20:'/',**{21+i:str(i) for i in range(10)},
            **{31+i:str(i) for i in range(10)},41:'×',42:'+',43:'−',44:'/',45:':',
            **{46+i:chr(65+i) for i in range(26)},72:'up',73:'down',78:'(',79:')',
            85:'Next',86:'Level',87:'Total',88:'Time',**{93+i:str(i) for i in range(10)}}
    for index,text in labels.items():
        rect=rows[index];low=native.crop(rect)
        white=31<=index<=40 or index in (42,43) or 93<=index<=102
        font=ITALIC if 93<=index<=102 else NUMBER if white else SERIF
        art=lettering(text,low.size,ink_bounds(low),font,not white,occupancy=.86)
        updates.append((rect,art,'glyph '+text))
    # All three pieces must carry continuous rails, including the tiled middle.
    for index,source in ((90,(0,0,32,16)),(91,(32,0,64,16)),(92,(64,0,96,16))):
        key=divider().crop(tuple(v*4 for v in source))
        updates.append((rows[index],key,'divider bar '+str(index)))
    return updates


def equipment(native,rows):
    result=[]
    for index,text in ((51,'Status'),(57,'Magic'),(59,'Equip'),(63,'Back'),(65,'Exit'),
                       (54,'Manual'),(55,'Adjust'),(56,'Max'),(64,'OK'),(69,'Reset')):
        rect=rows[index]
        result.append((rect,button_caption(text,rect[2]-rect[0]),'button '+text))
    # Regenerate vector shapes at a smaller drawing scale, not a resized PNG.
    with interface_art.drawing_scale(.86):
        icons=interface_art.catalog()['equipment']
    # These 16px UV slots also appear on the shorter Lv/HP rows. Keep the ink
    # in their top 11px, matching the existing small upright attack-type badge.
    with interface_art.drawing_scale(.60,offset=(0,-2)):
        row_icons=interface_art.catalog()['equipment']
    for index,(art,label) in icons.items():
        if index>=110:continue # Tiny 8x8 status markers need their native legibility.
        if index>=4:art=row_icons[index][0]
        result.append((rows[index],art,'compact '+label))
    with interface_art.drawing_scale(.86):start=interface_art.start_button()
    result.append((rows[5],start,'Start button'))
    return result
