"""New geometric artwork for the established HD UI icon system.

Coordinates are source sprite units. Shapes are drawn anew at 4x; the original
bitmap is used only as a design reference, never as a smoothing input.
"""
import math
from contextlib import contextmanager
from contextvars import ContextVar
import numpy as np
from PIL import Image, ImageDraw
import panel_redraw

GOLD = '#d98b12'
LIGHT = '#ffd779'
DARK = '#522100'
SILVER = '#c6c7ca'
DRAW_SCALE=ContextVar('ui_drawing_scale',default=1.0)
DRAW_OFFSET=ContextVar('ui_drawing_offset',default=(0,0))


@contextmanager
def drawing_scale(scale,offset=(0,0)):
    if not 0<scale<=1:raise ValueError('invalid UI drawing scale')
    if len(offset)!=2 or not all(math.isfinite(v) for v in offset):raise ValueError('invalid drawing offset')
    token=DRAW_SCALE.set(scale)
    position=DRAW_OFFSET.set(offset)
    try:yield
    finally:
        DRAW_SCALE.reset(token)
        DRAW_OFFSET.reset(position)


class Art:
    def __init__(self,w=16,h=16):
        self.w,self.h=w,h
        self.scale=DRAW_SCALE.get()
        self.offset=DRAW_OFFSET.get()
        self.factor=16
        self.image=Image.new('RGBA',(w*16,h*16))
        self.draw=ImageDraw.Draw(self.image)

    def point(self,x,y):
        return ((self.w/2+(x-self.w/2)*self.scale+self.offset[0])*16,
                (self.h/2+(y-self.h/2)*self.scale+self.offset[1])*16)

    def poly(self,points,color):
        self.draw.polygon([self.point(x,y) for x,y in points],fill=color)

    def rect(self,box,color):
        x,y,xx,yy=box
        x,y=self.point(x,y);xx,yy=self.point(xx,yy)
        self.draw.rectangle((round(x),round(y),round(xx)-1,round(yy)-1),fill=color)

    def line(self,points,color,width=1):
        self.draw.line([self.point(x,y) for x,y in points],fill=color,width=max(1,round(width*16*self.scale)),joint='curve')

    def ellipse(self,box,color):
        x,y,xx,yy=box
        self.draw.ellipse(tuple(round(v) for v in (*self.point(x,y),*self.point(xx,yy))),fill=color)

    def finish(self,metal=False):
        im=self.image.resize((self.w*4,self.h*4),Image.Resampling.BOX)
        if metal:
            # panel_redraw shades only warm metal, preserving transparency.
            im=panel_redraw.copper_finish(im,4)
        return im


def selector(height=16):
    if height not in (11,14,16):
        raise ValueError('unreviewed selector height')
    a=Art(96,16)
    a.rect((0,0,96,1), '#cfa12f')
    a.rect((0,height-1,96,height), '#cc8508')
    a.rect((0,0,1,height), '#b87908')
    a.rect((1,1,2,height-1), '#f3c052')
    a.rect((2,2,3,height-2), '#735000')
    a.rect((12,1,13,height-1), '#a86e08')
    a.rect((87,1,88,height-1), '#a86e08')
    a.rect((94,1,96,height-1), '#8f5d00')
    a.rect((90,2,92,height-2), '#d9a238')
    a.rect((90,2,92,3), '#f6ca67')
    a.rect((90,height-4,92,height-2), '#a16c15')
    a.poly([(3,3),(11,height/2),(3,height-3)], '#c18c0c')
    a.poly([(4,4),(4,height-4),(11,height/2)], '#e9b538')
    return a.finish()


def arrow(w,h,direction,color=GOLD):
    a=Art(w,h)
    p=[(.12,.25),(.58,.25),(.58,.05),(.96,.5),(.58,.95),(.58,.75),(.12,.75)]
    if direction=='left':p=[(1-x,y) for x,y in p]
    if direction=='up':p=[(y,1-x) for x,y in p]
    if direction=='down':p=[(y,x) for x,y in p]
    points=[(x*w,y*h) for x,y in p]
    a.poly(points,DARK)
    cx,cy=w/2,h/2
    a.poly([(cx+(x-cx)*.8,cy+(y-cy)*.8) for x,y in points],color)
    return a.finish(metal=True)


def triangle(w,h,direction):
    a=Art(w,h)
    pts=[(w*.12,h*.82),(w*.5,h*.14),(w*.88,h*.82)]
    if direction=='down':pts=[(x,h-y) for x,y in pts]
    a.poly(pts,'#623a00')
    cy=h*.51
    a.poly([(w/2+(x-w/2)*.82,cy+(y-cy)*.72) for x,y in pts],GOLD)
    a.line([(w*.24,h*(.68 if direction=='up' else .32)),(w*.76,h*(.68 if direction=='up' else .32))],LIGHT,.55)
    return a.finish(metal=True)


def star(w=24,h=16,occupancy=.65,vertical_offset=-2):
    # Keep the existing UV/advance, but fit the ink into the native 9px row
    # footprint. The old full-slot redraw extended below the selector rail.
    if not 0<occupancy<=1:raise ValueError('invalid star occupancy')
    a=Art(w,h)
    pts=[]
    for i in range(10):
        t=-math.pi/2+i*math.pi/5
        r=.46 if i%2==0 else .20
        pts.append((w/2+math.cos(t)*w*r*occupancy,h/2+vertical_offset+math.sin(t)*h*r*occupancy))
    cy=h/2+vertical_offset
    a.poly(pts,'#aaaaac'); a.poly([(w/2+(x-w/2)*.80,cy+(y-cy)*.80) for x,y in pts],'#f2f2f5')
    return a.finish()


def divider_frame():
    # Reuse approved corner geometry, with a dark copper field instead of grid.
    flat=panel_redraw.artwork(4,finish=False).crop((0,48*4,96*4,64*4))
    arr=np.array(flat)
    # The clean center must remain a material panel, not a texture stretch seam.
    arr[:,28*4:70*4,:3]=(32,12,0)
    return panel_redraw.copper_finish(Image.fromarray(arr),4)


def controller(letter):
    colors={'A':('#682020','#bb3534','#e77664'),'B':('#153168','#2c63bc','#6aa1ed'),
            'X':('#715600','#d6ae24','#ffe36e'),'Y':('#06542b','#0a9c4d','#65d584')}
    dark,base,light=colors[letter]
    a=Art();a.ellipse((1,1,15,15),'#151019');a.ellipse((2,1.5,14,14.5),dark)
    a.ellipse((2.5,2,13.5,13.5),base);a.ellipse((3.6,2.6,11.3,7.5),light)
    a.ellipse((4.1,3.2,12.4,12.7),base)
    ink=dark
    if letter=='A':
        a.line([(5,11),(8,4.5),(11,11)],ink,1.25);a.line([(6.1,8.8),(9.9,8.8)],ink,1)
    elif letter=='X':
        a.line([(5.5,4.8),(10.5,11)],ink,1.2);a.line([(10.5,4.8),(5.5,11)],ink,1.2)
    elif letter=='Y':
        a.line([(5.2,4.5),(8,8),(10.8,4.5)],ink,1.2);a.line([(8,8),(8,11.5)],ink,1.2)
    else:
        a.line([(5.6,11.3),(5.6,4.5),(9.3,4.5),(10.4,5.5),(10.4,6.5),(9.2,7.6),(5.6,7.6)],ink,1.05)
        a.line([(8.8,7.6),(10.6,8.6),(10.6,10.3),(9.5,11.3),(5.6,11.3)],ink,1.05)
    return a.finish()


def start_button():
    """Rounded triangular Start keycap, not a sharp faceted pyramid."""
    a=Art()
    def rounded(scale,dy=0):
        vertices=[(8+(x-8)*scale,8+(y-8)*scale+dy) for x,y in ((8,1.6),(15,13.6),(1,13.6))]
        result=[]
        for i,p in enumerate(vertices):
            prev,nxt=vertices[i-1],vertices[(i+1)%3]
            entry=(p[0]+(prev[0]-p[0])*.13,p[1]+(prev[1]-p[1])*.13)
            leave=(p[0]+(nxt[0]-p[0])*.13,p[1]+(nxt[1]-p[1])*.13)
            for j in range(9):
                t=j/8
                result.append(((1-t)**2*entry[0]+2*(1-t)*t*p[0]+t*t*leave[0],
                               (1-t)**2*entry[1]+2*(1-t)*t*p[1]+t*t*leave[1]))
        return result
    a.poly(rounded(1,.65),'#222222')
    a.poly(rounded(.94,.2),'#555555')
    a.poly(rounded(.85,-.25),'#c4c4c4')
    a.poly(rounded(.75,-.15),'#969696')
    a.line([(4,11.9),(12,11.9)],'#707070',.55)
    return a.finish()


def icon_frame(a,variant=0):
    a.rect((.5,.5,15.5,15.5),'#311400')
    a.rect((1.2,1.2,14.8,14.8),'#080808')
    if variant:
        # Red/orange active versions preserve their original state distinction.
        for i in range(14):
            level=(13-i)/13
            r=round(55+level*(120 if variant==2 else 80))
            a.rect((1.2,1.2+i*.95,14.8,2.15+i*.95),(r,round(r*.31),2,255))
    a.rect((15,.5,16,15.5),'#91420d' if variant==0 else '#dd6b25')


def weapon(kind,variant=0):
    a=Art();icon_frame(a,variant)
    if kind in ('sword','dagger'):
        end=8.5 if kind=='dagger' else 10.5
        a.poly([(2,2),(5,2.8),(end+1,end-.5),(end-1,end+1),(2.8,5)],'#70747b')
        a.poly([(2,2),(end+.3,end),(end-1,end+.4),(2.8,5)],'#d7d9da')
        a.line([(end-2,end+2),(end+2,end-2)],'#e2a629',1.1)
        a.line([(end,end),(13.5,13.5)],'#a26308',1.3)
        a.line([(end+.4,end),(13.9,13.3)],'#f3c658',.5)
    elif kind=='spear':
        a.line([(5,5),(13.5,13.5)],'#b77e24',1.8)
        a.line([(5,5),(13.5,13.5)],'#f8c654',.6)
        a.poly([(2,1),(7,3),(6,6),(3,7)],'#bfc4cc');a.poly([(2,1),(6,6),(3,7)],'#eeeeef')
    elif kind=='axe':
        a.line([(4,3),(13.5,13.5)],'#ab7821',1.8)
        a.line([(4,3),(13.5,13.5)],'#f6cc63',.55)
        a.poly([(1.5,3),(5,5),(8,4),(9,7),(7.5,10),(3,9),(1,6)],'#92959a')
        a.poly([(1.5,3),(3,6),(6,8),(7.5,10),(3,9),(1,6)],'#e1e0de')
    elif kind=='bow':
        # Left-facing bow: curved limb, a separate taut string and a real
        # arrowhead. The old plain shaft below center read as a stray crossbar.
        a.line([(10.8,2),(8.4,3.5),(6.8,5.7),(6.3,8),(6.8,10.3),(8.4,12.5),(10.8,14)],'#8c570b',1.9)
        a.line([(10.6,2.2),(8.6,3.8),(7.2,5.8),(6.8,8),(7.2,10.2),(8.6,12.2),(10.6,13.8)],'#e7b94c',.95)
        a.line([(10.8,2.3),(10.8,13.7)],'#d3d0c5',.65)
        a.line([(2,8),(13.6,8)],'#c3c7cc',.85)
        a.poly([(1.5,8),(4.4,6.2),(3.8,8),(4.4,9.8)],'#edf0ec')
        a.line([(12,8),(13.7,6.8)],'#aeb5bb',.65)
        a.line([(12,8),(13.7,9.2)],'#aeb5bb',.65)
    elif kind=='staff':
        a.line([(4,3),(13,14)],'#adb0b5',1.55)
        a.line([(4,3),(13,14)],'#e6e1ce',.5)
        a.ellipse((2,1,6.7,6),'#bb8d18');a.ellipse((2.9,1.7,5.7,4.6),'#1955b4')
        a.ellipse((3.1,1.8,4.3,3),'#79b6f4')
    elif kind=='whip':
        a.line([(3,11),(5,6),(9,2),(13,3),(13,8),(9,11),(7,8),(10,6)],'#898b8e',1.1)
        a.line([(2.5,14),(4.5,10)],'#53545a',2)
    elif kind=='claw':
        for dx in (0,2,4):a.poly([(3+dx,6),(8+dx,3),(6+dx,7),(2+dx,11)],'#b89020')
        a.poly([(2,8),(6,9),(6,12),(3,13)],'#815009')
    elif kind=='fist':
        a.poly([(3,6),(4,3),(6,3),(7,2),(9,2),(10,3),(12,3),(13,7),(12,12),(5,13),(3,10)],'#64666a')
        a.line([(4,6),(4,4),(6,4),(6,7),(8,7),(8,3),(10,3),(10,7),(12,6)],'#b5b8bc',1)
        a.line([(4,8),(8,10),(11,9)],'#b5b8bc',1.2)
    elif kind=='stick':
        a.poly([(2,2),(4,2),(14,13),(12,14)],'#7e4b00')
        a.line([(3,2.5),(12.8,13)],'#b17e14',1.3)
    return a.finish()


def shield():
    a=Art();a.poly([(1,2),(15,2),(15,9),(13,12),(8,15),(3,12),(1,9)],'#03465c')
    a.poly([(2,2.5),(14,2.5),(14,9),(12,11.5),(8,14),(4,11.5),(2,9)],'#1589ae')
    a.line([(2.5,8),(2.5,3),(13,3)],'#56c2d5',.8)
    a.rect((7,4,9,12),'#064e6b');a.rect((4,6,12,8),'#064e6b')
    return a.finish()


def crossed_swords():
    a=Art()
    for flip in (False,True):
        def pts(p):return [(16-x if flip else x,y) for x,y in p]
        a.poly(pts([(2,1),(5,3),(12,11),(10,13),(3,5)]),'#4d171a')
        a.poly(pts([(2.5,1.5),(4.5,3),(11.5,11),(10.5,11.8),(3.3,5)]),'#b84f43')
        a.line(pts([(8,13),(13,8)]),'#e17a58',1)
        a.line(pts([(11,11),(14.5,14.5)]),'#9b3226',1.7)
    return a.finish()


def bottle(color):
    a=Art();icon_frame(a)
    a.rect((6,2,10,3.5),'#9b9b92');a.rect((6.5,3.5,9.5,5),'#555b59')
    a.poly([(6.5,4.5),(9.5,4.5),(12.5,8),(12.5,14),(3.5,14),(3.5,8)],'#676b68')
    a.poly([(6.5,5),(9.5,5),(11.5,8),(11.5,13),(4.5,13),(4.5,8)],'#8c8d77')
    a.rect((5,8,11,12.5),color);a.rect((5,9,11,10),'#c2c1a5')
    a.line([(5,8),(5,12)],'#d9d9c4',.7)
    return a.finish()


def armor(metal=False):
    a=Art();icon_frame(a)
    a.poly([(4,3),(6,2),(7,4),(9,4),(10,2),(12,3),(15,6),(12,8),(11,7),(12,14),(4,14),(5,7),(4,8),(1,6)],'#54575b' if metal else '#684000')
    a.poly([(5,4),(6,4),(7,5),(9,5),(10,4),(11,4),(10.5,8),(11,12),(5,12),(5.5,8)],'#a5a6a5' if metal else '#a06b08')
    a.line([(5,9),(11,9)],'#d4d3cf' if metal else '#c38c19',.7)
    a.line([(7.8,5),(7.8,12)],'#44484c' if metal else '#764707',.6)
    return a.finish()


def coin():
    a=Art();icon_frame(a);a.ellipse((2,2,14,14),'#8e5700');a.ellipse((2.5,2.3,13,13),'#d49a10')
    a.ellipse((4,3.5,11.5,11.7),'#bb7e07')
    a.poly([(8,4.5),(10.3,7.5),(8,10.5),(5.7,7.5)],'#edbc31')
    return a.finish()


def tiny_marker(color):
    a=Art(8,8);a.rect((2,0,6,4),'#301300');a.rect((2.5,1,5.5,4),color)
    a.poly([(1,4),(7,4),(4,7.5)],color)
    return a.finish()


def config_cursor(frame):
    a=Art(32,16)
    levels=[1,.88,.62,.4,.1,0,.12,.4,.65,.9,.65,.4,.1,0,.3,.65]
    bright=levels[frame]
    a.line([(1,8),(31,8)],'#341600',2.5)
    a.line([(1,8),(31,8)],'#995300',.65)
    if bright:
        outer=1.4+bright*4.6
        a.poly([(19,8-outer),(19+outer,8),(19,8+outer),(19-outer,8)],'#643100')
        a.poly([(19,8-outer*.74),(19+outer*.74,8),(19,8+outer*.74),(19-outer*.74,8)],'#c37b0b')
        a.rect((18.6,8-outer,19.4,8+outer),'#e5a935')
        a.line([(19-outer,8),(19+outer,8)],'#e5a935',.6)
        if bright>.7:a.rect((17,6,21,10),'#562100')
    return a.finish(metal=True)


def map_marker(kind,color,w=16,h=16):
    if kind != 'tile':
        return map_selector(kind,color,w,h)
    a=Art(w,h)
    a.poly([(w/2,0),(w,h/2),(w/2,h),(0,h/2)],color)
    return a.finish()


def map_selector(kind,color,w=16,h=16):
    """Faceted map cursor and compact bevelled arrows, in native footprints.

    These are not the menu-row selector. Preserve the four rotation silhouettes
    and the source palette's substantial top/underside contrast.
    """
    palettes={
        '#bfc1be':('#080808','#d6d6d6','#b5b5b5','#949494','#7b7b7b','#393939'),
        '#ac3110':('#101010','#b53110','#942908','#7b2110','#631800','#310800'),
        '#0079cb':('#101010','#007bce','#0063b5','#00529c','#004284','#001852'),
        '#c6a327':('#101010','#efbd21','#ce9c18','#b58410','#946310','#522900'),
        '#292b2b':('#000000','#212121','#181818','#101010','#080808','#000000'),
    }
    edge,top,bevel,left,point,right=palettes[color]
    a=Art(w,h)
    if kind=='shield':
        a.poly([(2,2),(14,2),(14,9),(8,14),(2,9)],edge)
        a.poly([(3,3),(13,3),(13,8),(8,13),(3,8)],right)
        a.poly([(3,3),(13,3),(13,8),(3,8)],bevel)
        a.poly([(4,4),(12,4),(12,7),(4,7)],top)
        a.poly([(3,8),(8,8),(8,13)],left)
        a.poly([(8,8),(13,8),(8,13)],point)
    elif kind in ('diamond','lean-left','lean-right'):
        vertices={
            'diamond':((0,6),(8,1),(16,6),(8,9),(8,14)),
            'lean-left':((1,7),(6,1),(15,4),(9,9),(8,14)),
            'lean-right':((1,4),(10,1),(15,7),(7,9),(8,14)),
        }
        l,b,r,f,p=vertices[kind]
        a.poly([l,b,r,p],edge)
        # Keep a narrow dark rim; independently drawn planes give real depth.
        def inset(v):return (8+(v[0]-8)*.88,7+(v[1]-7)*.88)
        l,b,r,f,p=map(inset,(l,b,r,f,p))
        a.poly([l,f,p],left)
        a.poly([f,r,p],right)
        a.poly([l,b,r,f],top)
        a.line([l,f,r],bevel,.8)
        a.line([f,p],point,.65)
    elif kind in ('left','right'):
        # The source's vertical-arrow sprites occupy only rows 4..11.
        def pts(points):return [(8-x if kind=='right' else x,y) for x,y in points]
        a.poly(pts([(0,8),(8,4),(8,7),(5,8),(8,9),(8,12)]),edge)
        a.poly(pts([(1,8),(7,5),(7,6.5),(3.5,8),(7,9.5),(7,11)]),bevel)
        a.poly(pts([(1,8),(7,5),(7,6.5),(3.5,8)]),top)
        a.line(pts([(3.5,8),(7,9.5)]),point,.55)
    elif kind in ('up','down'):
        # Up uses y=0..5, down y=2..7, not nearly the full 16px tile height.
        def pts(points):return [(x,8-y if kind=='down' else y) for x,y in points]
        a.poly(pts([(2,6),(2,3),(8,0),(14,3),(14,6),(8,3)]),edge)
        a.poly(pts([(3,4.8),(3,3.5),(8,1),(13,3.5),(13,4.8),(8,2.6)]),bevel)
        a.poly(pts([(3,3.5),(8,1),(13,3.5),(12.5,4),(8,2.6),(3.5,4)]),top)
        a.line(pts([(3.2,4.6),(8,2.6),(12.8,4.6)]),point,.45)
    else:
        raise ValueError('unknown map selector')
    bounds={'shield':(2,2,14,14),'lean-left':(1,1,15,14),
            'diamond':(0,1,16,14),'lean-right':(1,1,15,14),
            'left':(0,4,8,12),'right':(0,4,8,12),
            'up':(2,0,14,6),'down':(2,2,14,8)}
    rect=tuple(v*4 for v in bounds[kind])
    art=a.finish();result=Image.new('RGBA',art.size)
    result.paste(art.crop(rect),rect[:2])
    return result


def hud_parts():
    parts=[]
    for rect,label in (((34,173,88,176),'level underline'),((42,181,168,184),'HP underline'),((50,191,181,195),'BP underline')):
        x,y,xx,yy=rect;a=Art(xx-x,yy-y)
        a.rect((0,1,a.w,a.h),'#100c0b')
        for col in range(a.w*4):
            t=col/(a.w*4-1)
            c=tuple(round(v*(1-t)+z*t) for v,z in zip((225,161,48),(103,41,0)))+(255,)
            a.rect((col/4,0,(col+1)/4,a.h-1),c)
        parts.append((rect,a.finish(),label))
    return parts


def catalog():
    """Map source sprite IDs to independently redrawn art and a clear label."""
    stem=Art(8,8);stem.rect((0,0,1,8),'#c99920');stem.rect((1,0,2,8),'#9f7510')
    common={18:(arrow(16,8,'left'),'previous arrow'),19:(arrow(16,8,'right'),'next arrow'),
            77:(arrow(24,8,'right'),'horizontal pointer'),81:(stem.finish(),'scroll track'),
            82:(triangle(8,8,'up'),'small up'),83:(triangle(8,8,'down'),'small down'),
            84:(triangle(24,8,'down'),'continue'),
            89:(star(),'white star')}
    for start in (15,74):
        select=selector(14 if start==15 else 11)
        for i in range(3):common[start+i]=(select.crop((i*128,0,(i+1)*128,64)),'selection frame '+str(i))
    divider=divider_frame()
    for i in range(3):common[90+i]=(divider.crop((i*128,0,(i+1)*128,64)),'copper divider '+str(i))
    equipment={i:(controller(letter),'button '+letter) for i,letter in enumerate('ABXY')}
    equipment.update({12:(shield(),'guard shield'),13:(crossed_swords(),'counter swords'),
                      78:(armor(),'clothing'),79:(armor(True),'armor'),93:(coin(),'coin')})
    for variant,start in enumerate((18,26,34)):
        for j,key in enumerate(('sword','spear','axe','bow','whip','staff','claw','fist')):
            equipment[start+j]=(weapon(key,variant),key+' state '+str(variant))
    for i,c in enumerate(('#b58a19','#38a94b','#bba01f','#2066b6','#af3920','#9c3a19')):
        equipment[43+i]=(bottle(c),'bottle '+str(i))
    for i in range(3):equipment[81+i]=(weapon('stick',i),'stick state '+str(i))
    for i in range(3):equipment[85+i]=(weapon('dagger',i),'dagger state '+str(i))
    # These late sword variants have different source slots but the same visual type.
    equipment[88]=(weapon('sword',1),'sword active');equipment[89]=(weapon('sword',2),'sword bright')
    for i in range(8):
        equipment[110+i]=(tiny_marker((int(245-i*13),int(170-i*11),12,255)),'gold marker '+str(i))
        equipment[118+i]=(tiny_marker((10,int(110-i*8),int(245-i*15),255)),'blue marker '+str(i))
    config={21+i:(config_cursor(i),'configuration cursor '+str(i)) for i in range(16)}
    config.update({37:(arrow(16,8,'right'),'configuration pointer'),
                   38:(triangle(32,16,'up'),'configuration up'),39:(triangle(32,16,'down'),'configuration down')})
    battle={}
    for row,c in enumerate(('#bfc1be','#ac3110','#0079cb','#c6a327','#292b2b')):
        for j,key in enumerate(('shield','lean-left','diamond','lean-right','left','up','down','right')):
            w,h=(8,16) if j in (4,7) else (16,8) if j in (5,6) else (16,16)
            battle[30+row*8+j]=(map_marker(key,c,w,h),'battle '+key+' color '+str(row))
    for i,c in enumerate(('#006ef7','#0f42b1','#0a2073','#070843','#dc0000','#a20000','#610000','#320000',
                           '#00ce00','#009200','#005700','#003500','#e4a011','#af6e09','#764702','#482900')):
        battle[117+i]=(map_marker('tile',c,32,16),'floor tile '+str(i))
    return {'common':common,'equipment':equipment,'config':config,'battle':battle}
