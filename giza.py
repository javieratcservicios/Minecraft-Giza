#!/usr/bin/env python3
"""Giza Creativo nativo: pygame + OpenGL. Sin navegador ni JavaScript.
Edición HD. Ejecutar con .venv/bin/python giza.py. Datos: giza_mapa.bin.
"""
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import argparse, json, math, time, zlib, threading, ctypes, textwrap
from pathlib import Path
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from mapa_datos import MapReader
import numpy as np
ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT/'giza_catalogo.json').read_text())
BLOCKS = DATA['bloques']; PLACES = DATA['lugares']; MAT = DATA['materiales']
IDS = {b['id']: b['num'] for b in BLOCKS}
SAVE = ROOT/'giza_partida.json'
DIRECTIONS = [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]
VERTS = np.array([[(1,0,0),(1,1,0),(1,1,1),(1,0,1)],[(0,0,1),(0,1,1),(0,1,0),(0,0,0)],[(0,1,1),(1,1,1),(1,1,0),(0,1,0)],[(0,0,0),(1,0,0),(1,0,1),(0,0,1)],[(1,0,1),(1,1,1),(0,1,1),(0,0,1)],[(0,0,0),(0,1,0),(1,1,0),(1,0,0)]],dtype=np.float32)
SHADES = [.80,.70,1,.52,.9,.62]
FACE_TEX = np.asarray(DATA['caras']).reshape(-1,3)
TRANSPARENT = np.array([b.get('transparente',False) or b['forma'] in ('cruz','hojas','liquido','cristal','panel') for b in BLOCKS])
TRANSPARENT[0] = True
CROSS = np.array([b["forma"]=="cruz" for b in BLOCKS])
VISIBLE = np.array([b["forma"]!="nada" for b in BLOCKS]); VISIBLE[0]=False
LIQUID = np.array([b['forma']=='liquido' for b in BLOCKS])
BLENDED = np.array([b['forma']=='liquido' or (b['forma'] in ('cristal','panel') and ('glass' in b['id'] or 'ice' in b['id'])) or b['id'] in ('slime_block','honey_block') for b in BLOCKS])
SOLID = np.array([b['forma'] not in ('nada','cruz','liquido','alfombra') for b in BLOCKS]); SOLID[0]=False
BOXES = {'losa':(0,0,0,16,8,16),'capa':(0,0,0,16,2,16),'alfombra':(0,0,0,16,1,16),'placa':(1,0,1,15,1,15),'boton':(5,0,6,11,2,10),'camino':(0,0,0,16,15,16),'valla':(6,0,6,10,16,10),'muro':(4,0,4,12,14,12),'panel':(7,0,0,9,16,16),'puerta':(0,0,13,16,16,16),'trampilla':(0,0,0,16,3,16),'cama':(0,0,0,16,9,16),'cofre':(1,0,1,15,14,15),'farol':(5,0,5,11,9,11),'huevo':(2,0,2,14,15,14),'cartel':(0,6,7,16,14,9),'yunque':(1,0,3,15,16,13),'cactus':(1,0,1,15,16,15),'liquido':(0,0,0,16,14,16)}
BOUNDS = np.array([BOXES.get(b['forma'],(0,0,0,16,16,16)) for b in BLOCKS],dtype=np.float32)/16
PARTIAL = np.array([b['forma'] not in ('cubo','cristal','hojas','liquido','nada') for b in BLOCKS])
class World:
    def __init__(self):
        self.index=json.loads((ROOT/'giza_indice.json').read_text()); self.file=MapReader(ROOT); self.lock=threading.Lock();self.changes={};self.revision=0
    @lru_cache(maxsize=512)
    def tile(self,cx,cz):
        entry=self.index.get(f'{cx},{cz}')
        if not entry:return np.zeros((16,256,16),dtype=np.uint16)
        with self.lock:
            self.file.seek(entry[0]); raw=self.file.read(entry[1])
        return np.frombuffer(zlib.decompress(raw),dtype='<u2').reshape(16,16,256).transpose(0,2,1)
    def block(self,x,y,z):
        if not 0<=y<256:return 0
        return self.changes.get((x,y,z),int(self.tile(x//16,z//16)[x%16,y,z%16]))
    def set(self,p,n):
        if 0<p[1]<256 and f'{p[0]//16},{p[2]//16}' in self.index:
            self.changes[p]=int(n);self.revision+=1;return True
        return False
    def mesh(self,cx,cz):
        a=np.zeros((18,258,18),dtype=np.uint16)
        a[1:17,1:257,1:17]=self.tile(cx,cz)
        a[0,1:257,1:17]=self.tile(cx-1,cz)[15,:,:]
        a[17,1:257,1:17]=self.tile(cx+1,cz)[0,:,:]
        a[1:17,1:257,0]=self.tile(cx,cz-1)[:,:,15]
        a[1:17,1:257,17]=self.tile(cx,cz+1)[:,:,0]
        for dx in (-1,1):
            for dz in (-1,1):a[0 if dx<0 else 17,1:257,0 if dz<0 else 17]=self.tile(cx+dx,cz+dz)[15 if dx<0 else 0,:,15 if dz<0 else 0]
        for (x,y,z),n in list(self.changes.items()):
            lx,lz=x-cx*16+1,z-cz*16+1
            if 0<=lx<18 and 0<=lz<18:a[lx,y+1,lz]=n
        core=a[1:17,1:257,1:17]; arrays=[[],[]]
        top=np.max(np.where((a!=0)&~TRANSPARENT[a],np.arange(258)[None,:,None],0),axis=1)
        opaque=(a!=0)&~TRANSPARENT[a]&~PARTIAL[a]
        for face,(dx,dy,dz) in enumerate(DIRECTIONS):
            nb=a[1+dx:17+dx,1+dy:257+dy,1+dz:17+dz]
            mask=VISIBLE[core]&~CROSS[core]&((nb==0)|TRANSPARENT[nb]|PARTIAL[nb]|PARTIAL[core])&~((core==nb)&TRANSPARENT[core])
            for transparent in (0,1):
                coords=np.argwhere(mask & (BLENDED[core] if transparent else ~BLENDED[core]))
                if not len(coords):continue
                kinds=core[tuple(coords.T)]; verts=coords[:,None,:].astype(np.float32)+VERTS[face][None,:,:]
                bounds=BOUNDS[kinds].copy()
                # Los fluidos apilados llenan la celda para no dejar huecos.
                water=LIQUID[kinds] & (a[coords[:,0]+1,coords[:,1]+2,coords[:,2]+1]==kinds)
                bounds[water,4]=1
                verts=coords[:,None,:]+bounds[:,None,:3]+VERTS[face][None,:,:]*(bounds[:,None,3:]-bounds[:,None,:3])
                verts[:,:,0]+=cx*16;verts[:,:,2]+=cz*16
                layer=FACE_TEX[kinds,0 if face==2 else 2 if face==3 else 1]
                uv=np.tile(np.array([[0,1],[0,0],[1,0],[1,1]],dtype=np.float32),(len(coords),1,1))
                uv[:,:,0]=(layer[:,None]%32+uv[:,:,0]*.98+.01)/32
                uv[:,:,1]=(layer[:,None]//32+uv[:,:,1]*.98+.01)/19
                exposed=coords[:,1]+dy+1>=top[coords[:,0]+1+dx,coords[:,2]+1+dz]
                colors=np.zeros((len(coords),4,3),dtype=np.float32)
                colors[:,:,0]=np.where(exposed,1.,.12)[:,None]
                colors[:,:,2]=np.array([BLOCKS[int(k)].get('luz',0)/15 for k in kinds])[:,None]
                base=coords+np.array([1+dx,1+dy,1+dz]);tangents=[axis for axis,d in enumerate((dx,dy,dz)) if not d]
                for v,corner in enumerate(VERTS[face]):
                    side1=np.zeros(3,dtype=int);side2=side1.copy()
                    side1[tangents[0]]=1 if corner[tangents[0]] else -1
                    side2[tangents[1]]=1 if corner[tangents[1]] else -1
                    n1=opaque[tuple((base+side1).T)].astype(float);n2=opaque[tuple((base+side2).T)].astype(float);nc=opaque[tuple((base+side1+side2).T)].astype(float)
                    occlusion=np.where((n1+n2)==2,3,n1+n2+nc)
                    colors[:,v,1]=1-occlusion*.16
                alpha=np.full((len(coords),4,1),.68 if transparent else 1,dtype=np.float32)
                arrays[transparent].append(np.concatenate([verts,uv,colors,alpha],axis=2).reshape(-1,9))
        coords=np.argwhere(CROSS[core])
        if len(coords):
            kinds=core[tuple(coords.T)];layer=FACE_TEX[kinds,1]
            cross=np.array([[(0,0,0),(0,1,0),(1,1,1),(1,0,1)],[(1,0,0),(1,1,0),(0,1,1),(0,0,1)]],dtype=np.float32).reshape(8,3)
            verts=coords[:,None,:]+cross[None,:,:];verts[:,:,0]+=cx*16;verts[:,:,2]+=cz*16
            uv=np.tile(np.array([[0,1],[0,0],[1,0],[1,1]]*2,dtype=np.float32),(len(coords),1,1));uv[:,:,0]=(layer[:,None]%32+uv[:,:,0]*.98+.01)/32;uv[:,:,1]=(layer[:,None]//32+uv[:,:,1]*.98+.01)/19
            arrays[0].append(np.concatenate([verts,uv,np.tile(np.array([1.,1.,0.,1.]),(len(coords),8,1))],axis=2).reshape(-1,9))
        return tuple(np.ascontiguousarray(np.concatenate(v),dtype=np.float32) if v else np.empty((0,9),dtype=np.float32) for v in arrays)

def mining_time(b,tier):
    hardness=b['dureza']
    if hardness<0:return 'Indestructible'
    if hardness==0:return 'Instantáneo'
    correct=tier!='mano' and b['herramienta'] not in ('ninguna',None)
    speed={'mano':1,'madera':2,'piedra':4,'hierro':6,'diamante':8,'netherita':9,'oro':12}[tier] if correct else 1
    level={'mano':-1,'madera':0,'oro':0,'piedra':1,'hierro':2,'diamante':3,'netherita':4}[tier]
    needed={'madera':0,'piedra':1,'hierro':2,'diamante':3}.get(b.get('nivel'),0)
    drops=not b.get('nivel') or (correct and level>=needed)
    return f'{math.ceil(hardness*(30 if drops else 100)/speed)/20:.2f} s'+('' if drops else ' (sin drop)')

def save_atomic(data):
    temp=SAVE.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False));temp.replace(SAVE)

def run(args):
    import pygame
    from OpenGL import GL as gl
    from OpenGL.GLU import gluPerspective
    pygame.init();pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE,24)
    pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS,1);pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES,4)
    flags=pygame.OPENGL|pygame.DOUBLEBUF|(0 if args.ventana else pygame.FULLSCREEN)
    resolution=tuple(map(int,args.resolucion.lower().split('x'))) if getattr(args,'resolucion',None) else (1280,720)
    try:pygame.display.set_mode(resolution if args.ventana else (0,0),flags,vsync=1)
    except pygame.error:
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS,0);pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES,0);pygame.display.set_mode(resolution if args.ventana else (0,0),flags)
    pygame.display.set_caption('Giza Creativo — Python nativo')
    screen=pygame.display.get_surface();width,height=screen.get_size()
    world=World();pos=[640.,151.62,760.];yaw=-62.;pitch=-4.;bar=[MAT[k] for k in ('caliza','calizaGastada','tura','granito','arenisca','vidrio' if 'vidrio' in MAT else 'agua','hierba','tronco','antorcha')]
    settings={'radio':9,'fov':72,'sens':.12,'dia':1.0};flying=True;noclip=False;slot=0;data={}
    if SAVE.exists():
        try:
            data=json.loads(SAVE.read_text());pos=list(map(float,data['pos']));yaw=float(data['yaw']);pitch=float(data['pitch']);bar=data['barra'];settings.update(data.get('ajustes',{}));flying=data.get('volar',True);noclip=data.get('atravesar',False)
            world.changes={tuple(p):n for p,n in data.get('cambios',[]) if 0<=n<len(BLOCKS)}
        except (ValueError,KeyError,TypeError) as e:print('No se pudo leer la partida:',e)
    if not data.get('calidad_hd',False):settings['radio']=9
    mesh_lists={};pending={};pool=ThreadPoolExecutor(max_workers=3);running=True;panel='inicio';query='';category='Todas';filter_name='';page=0;selected=bar[0];vy=0.;grounded=False;clock=pygame.time.Clock();lastsave=time.monotonic();notice='';notice_until=0;buttons=[];last_center=None
    overlay=pygame.Surface((1280,720),pygame.SRCALPHA);ui_texture=gl.glGenTextures(1);ui_last=0
    raw=np.frombuffer((ROOT/'giza_texturas.bin').read_bytes(),dtype=np.uint8).reshape(-1,16,16,4)
    from giza_hd import HDRenderer
    renderer=HDRenderer(world,DATA,raw)
    from giza_ui import Interface
    interface=Interface(DATA,renderer.atlas_pixels,width,height)
    debug=False
    def say(text):
        nonlocal notice,notice_until
        notice=text;notice_until=time.monotonic()+5
    def capture():
        active=panel is None;pygame.event.set_grab(active);pygame.mouse.set_visible(not active);pygame.mouse.get_rel()
        if panel=='catalogo':pygame.key.start_text_input()
        else:pygame.key.stop_text_input()
    def persist():
        nonlocal lastsave
        if args.sin_guardar:return
        save_atomic({'schema':1,'calidad_hd':True,'pos':pos,'yaw':yaw,'pitch':pitch,'barra':bar,'ajustes':settings,'volar':flying,'atravesar':noclip,'cambios':[[list(p),n] for p,n in world.changes.items()]});lastsave=time.monotonic()
    def teleport(place):
        nonlocal pos,yaw,pitch,flying,noclip,panel,vy
        pos=[place['x'],place['y']+1.62,place['z']];dx,dy,dz=[place['mira'][i]-pos[i] for i in range(3)];yaw=math.degrees(math.atan2(dx,-dz));pitch=math.degrees(math.atan2(dy,math.hypot(dx,dz)));flying=True;noclip=place['id']=='descarga';vy=0;panel=None;say(place['nota']);capture()
    def collision(p):
        for x in range(math.floor(p[0]-.28),math.floor(p[0]+.28)+1):
            for y in range(math.floor(p[1]-1.62),math.floor(p[1]+.16)+1):
                for z in range(math.floor(p[2]-.28),math.floor(p[2]+.28)+1):
                    k=world.block(x,y,z)
                    if SOLID[k]:
                        box=BOUNDS[k]
                        if (p[0]-.28<x+box[3] and p[0]+.28>x+box[0] and p[1]-1.62<y+box[4] and p[1]+.16>y+box[1] and p[2]-.28<z+box[5] and p[2]+.28>z+box[2]):return True
        return False
    def ray():
        ya,pi=map(math.radians,(yaw,pitch));d=(math.sin(ya)*math.cos(pi),math.sin(pi),-math.cos(ya)*math.cos(pi));prev=tuple(map(math.floor,pos))
        for n in range(1,281):
            p=tuple(math.floor(pos[i]+d[i]*n*.05) for i in range(3));k=world.block(*p)
            if k and not LIQUID[k]:return p,prev
            prev=p
        return None,None
    def invalidate(p):
        for dx,dz in ((0,0),(1,0),(-1,0),(0,1),(0,-1)):
            key=((p[0]+dx)//16,(p[2]+dz)//16)
            if key in mesh_lists:
                for lid in mesh_lists.pop(key):gl.glDeleteLists(lid,1)
            if key in pending:pending.pop(key).cancel()
    def edit(button):
        nonlocal selected
        hit,before=ray()
        if hit is None:return
        if button==2:bar[slot]=world.block(*hit);say(BLOCKS[bar[slot]]['nombre']);return
        p=hit if button==1 else before
        if button==1 and p[1]==0:return
        if button==3 and not noclip and abs(p[0]+.5-pos[0])<.78 and abs(p[2]+.5-pos[2])<.78 and p[1]<pos[1]+.16 and p[1]+1>pos[1]-1.62:return
        if world.set(p,0 if button==1 else bar[slot]):invalidate(p)
    def draw_array(arr):
        if not len(arr):return
        gl.glEnableClientState(gl.GL_VERTEX_ARRAY);gl.glEnableClientState(gl.GL_TEXTURE_COORD_ARRAY);gl.glEnableClientState(gl.GL_COLOR_ARRAY)
        gl.glVertexPointer(3,gl.GL_FLOAT,36,ctypes.c_void_p(arr.ctypes.data));gl.glTexCoordPointer(2,gl.GL_FLOAT,36,ctypes.c_void_p(arr.ctypes.data+12));gl.glColorPointer(4,gl.GL_FLOAT,36,ctypes.c_void_p(arr.ctypes.data+20));gl.glDrawArrays(gl.GL_QUADS,0,len(arr))
        gl.glDisableClientState(gl.GL_VERTEX_ARRAY);gl.glDisableClientState(gl.GL_TEXTURE_COORD_ARRAY);gl.glDisableClientState(gl.GL_COLOR_ARRAY)
    def compile_mesh(arr):
        lid=gl.glGenLists(1);gl.glNewList(lid,gl.GL_COMPILE);draw_array(arr);gl.glEndList();return lid
    def ui():
        nonlocal buttons,overlay
        mx,my=pygame.mouse.get_pos()
        overlay,buttons=interface.draw({'panel':panel,'mouse':(mx*1280/width,my*720/height),'settings':settings,'selected':selected,'bar':bar,'slot':slot,'flying':flying,'noclip':noclip,'query':query,'category':category,'filter_name':filter_name,'page':page,'pos':pos,'fps':clock.get_fps(),'pending':len(pending),'notice':notice,'notice_until':notice_until,'fingers':fingers,'debug':debug,'mining_time':mining_time})
    def action(a):
        nonlocal panel,page,category,filter_name,selected,flying,noclip,last_center
        if isinstance(a,tuple):
            kind,value=a
            if kind=='lugar':teleport(PLACES[value])
            elif kind=='categoria':category=value;page=0
            elif kind=='filtro':filter_name=value;page=0
            elif kind=='bloque':selected=value
            elif kind=='usar':
                if not BLOCKS[value].get('colocable',True):say('Este bloque es invisible y no se puede colocar');return
                bar[slot]=value;panel=None;capture()
            elif kind=='siguiente' and (page+1)*24<value:page+=1
            return
        if a=='jugar':panel=None;capture()
        elif a in ('catalogo','lugares','ajustes','ficha'):panel=a;capture()
        elif a=='guardar':persist();say('Partida guardada')
        elif a=='salir':return 'salir'
        elif a=='anterior':page=max(0,page-1)
        elif a=='radio':settings['radio']={5:9,9:13,13:17,17:5}.get(settings['radio'],9);last_center=None
        elif a=='fov':settings['fov']=60 if settings['fov']>=100 else settings['fov']+10
        elif a=='sens':settings['sens']=.06 if settings['sens']>=.24 else round(settings['sens']+.03,2)
        elif a=='dia':settings['dia']=.27 if settings['dia']>.5 else 1;last_center=None
        elif a=='sombras':settings['sombras']=not settings.get('sombras',True)
        elif a=='volar':flying=not flying
        elif a=='atravesar':noclip=not noclip
        elif a=='borrar':panel='confirmar'
        elif a=='confirmar_borrar':
            world.changes.clear();world.revision+=1
            for lists in mesh_lists.values():
                for lid in lists:gl.glDeleteLists(lid,1)
            mesh_lists.clear()
            for future in pending.values():future.cancel()
            pending.clear();persist();panel='ajustes';say('Mapa restaurado')
    if args.lugar:
        teleport(next(p for p in PLACES if p['id']==args.lugar))
    if args.panel:panel=args.panel
    capture();frame=0;edit_time=0;fingers={};touch_move=[0.,0.];touch_up=0
    try:
        while running:
            dt=min(clock.tick(60)/1000,.05);frame+=1
            for event in pygame.event.get():
                if event.type==pygame.QUIT:running=False
                elif event.type==pygame.WINDOWFOCUSLOST:
                    panel='pausa';capture();persist()
                elif event.type==pygame.TEXTINPUT and panel=='catalogo':query+=event.text;page=0
                elif event.type in (pygame.FINGERDOWN,pygame.FINGERMOTION,pygame.FINGERUP):
                    fx,fy=event.x*1280,event.y*720
                    if event.type==pygame.FINGERDOWN:
                        if panel:
                            for rect,a in buttons:
                                if rect.collidepoint(fx,fy):
                                    if action(a)=='salir':running=False
                                    break
                        else:
                            used=False
                            for rect,a in buttons:
                                if a is not None and rect.collidepoint(fx,fy):action(a);used=True;break
                            if not used:
                                kind='barra' if fy>628 and 348<=fx<933 else 'arriba' if fx>1180 and 470<fy<540 else 'abajo' if fx>1180 and 550<fy<620 else 'mover' if fx<640 else 'mirar'
                                fingers[event.finger_id]={'kind':kind,'x':event.x,'y':event.y,'time':time.monotonic(),'moved':False,'last':0}
                                if kind=='barra':slot=min(8,int((fx-348)//65))
                    elif event.finger_id in fingers:
                        finger=fingers[event.finger_id];kind=finger['kind']
                        if event.type==pygame.FINGERMOTION:
                            if abs(event.x-finger['x'])+abs(event.y-finger['y'])>.015:finger['moved']=True
                            if kind=='mover':touch_move=[max(-1,min(1,(event.x-finger['x'])*12)),max(-1,min(1,-(event.y-finger['y'])*12))]
                            elif kind=='mirar':yaw+=event.dx*width*settings['sens'];pitch=max(-89,min(89,pitch-event.dy*height*settings['sens']))
                        else:
                            if kind=='mirar' and not finger['moved'] and time.monotonic()-finger['time']<.38:edit(3)
                            if kind=='mover':touch_move=[0.,0.]
                            del fingers[event.finger_id]
                elif event.type==pygame.KEYDOWN:
                    k=event.key
                    if k==pygame.K_ESCAPE:
                        panel=None if panel=='pausa' else 'pausa' if panel is None else 'inicio';capture()
                    elif k==pygame.K_F5:persist();say('Partida guardada')
                    elif k==pygame.K_F3:debug=not debug
                    elif panel=='catalogo' and k==pygame.K_BACKSPACE:query=query[:-1];page=0
                    elif panel=='catalogo' and k==pygame.K_LEFT:page=max(0,page-1)
                    elif panel=='catalogo' and k==pygame.K_RIGHT:page+=1
                    elif panel is None:
                        if k==pygame.K_f:flying=not flying;vy=0
                        elif k==pygame.K_n:noclip=not noclip
                        elif k in (pygame.K_e,pygame.K_m):panel='catalogo' if k==pygame.K_e else 'lugares';capture()
                        elif pygame.K_1<=k<=pygame.K_9:slot=k-pygame.K_1
                elif event.type==pygame.MOUSEMOTION and panel is None and not getattr(event,'touch',False):yaw+=event.rel[0]*settings['sens'];pitch=max(-89,min(89,pitch-event.rel[1]*settings['sens']))
                elif event.type==pygame.MOUSEWHEEL:
                    if panel is None:slot=(slot-event.y)%9
                    elif panel=='catalogo':page=max(0,page-event.y)
                elif event.type==pygame.MOUSEBUTTONDOWN:
                    if getattr(event,"touch",False):continue
                    if panel:
                        mouse=(event.pos[0]*1280/width,event.pos[1]*720/height)
                        for rect,a in buttons:
                            if rect.collidepoint(mouse):
                                if action(a)=='salir':running=False
                                break
                    elif event.button in (1,2,3):edit(event.button);edit_time=time.monotonic()
            if panel is None:
                touch_up=0
                for finger in list(fingers.values()):
                    kind=finger['kind'];age=time.monotonic()-finger['time']
                    if kind=='mirar' and not finger['moved'] and age>=.38 and time.monotonic()-finger['last']>.26:edit(1);finger['last']=time.monotonic()
                    elif kind=='barra' and age>.55:panel='catalogo';capture();finger['time']=time.monotonic()+10000
                    elif kind=='arriba':touch_up=1
                    elif kind=='abajo':touch_up=-1
                keys=pygame.key.get_pressed();ya=math.radians(yaw);forward=int(keys[pygame.K_w] or keys[pygame.K_UP])-int(keys[pygame.K_s] or keys[pygame.K_DOWN]);side=int(keys[pygame.K_d] or keys[pygame.K_RIGHT])-int(keys[pygame.K_a] or keys[pygame.K_LEFT]);forward+=touch_move[1];side+=touch_move[0];norm=max(1,math.hypot(forward,side));speed=(60 if keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL] else 12) if flying else (5.6 if keys[pygame.K_LCTRL] else 4.3)
                move=[(math.sin(ya)*forward+math.cos(ya)*side)/norm*speed*dt,0,(-math.cos(ya)*forward+math.sin(ya)*side)/norm*speed*dt]
                if flying:move[1]=(keys[pygame.K_SPACE]-keys[pygame.K_LSHIFT]+touch_up)*speed*dt
                else:
                    if (keys[pygame.K_SPACE] or touch_up>0) and grounded:vy=8.6
                    vy-=28*dt;move[1]=vy*dt
                grounded=False
                for _ in range(max(1,math.ceil(max(map(abs,move))/.4))):
                    steps=max(1,math.ceil(max(map(abs,move))/.4))
                    for axis in (0,2,1):
                        trial=pos.copy();trial[axis]+=move[axis]/steps
                        if noclip or not collision(trial):pos=trial
                        elif axis==1:
                            if move[axis]<0:grounded=True
                            vy=0
                        elif not flying:
                            trial[1]+=1
                            if not collision(trial):pos=trial
                pos[0]=max(-1502,min(1502,pos[0]));pos[2]=max(-1006,min(1998,pos[2]));pos[1]=max(2,min(300,pos[1]))
                if pygame.mouse.get_pressed()[0] and time.monotonic()-edit_time>.26:edit(1);edit_time=time.monotonic()
            center=(math.floor(pos[0]/16),math.floor(pos[2]/16));r=int(settings['radio'])
            if center!=last_center:last_center=center
            wanted={(center[0]+x,center[1]+z) for x in range(-r,r+1) for z in range(-r,r+1)}
            for key in list(mesh_lists):
                if max(abs(key[0]-center[0]),abs(key[1]-center[1]))>r+2:
                    for lid in mesh_lists.pop(key):gl.glDeleteLists(lid,1)
            for key in list(pending):
                if key not in wanted:pending.pop(key).cancel()
            for key in sorted(wanted-mesh_lists.keys()-pending.keys(),key=lambda k:(k[0]-center[0])**2+(k[1]-center[1])**2):
                if len(pending)>=10:break
                pending[key]=pool.submit(world.mesh,*key)
            uploads_started=time.monotonic()
            for key,future in list(pending.items()):
                if future.done():
                    del pending[key];mesh_lists[key]=tuple(compile_mesh(a) for a in future.result())
                    if time.monotonic()-uploads_started>.005:break
            camera=([640.,200.,760.],-62.,-8.) if panel=='inicio' else (pos,yaw,pitch)
            renderer.render(*camera,settings,width,height,mesh_lists,world.revision)
            if panel is None:
                hit,_=ray()
                if hit:
                    gl.glColor3f(1,.86,.45);gl.glLineWidth(2);gl.glBegin(gl.GL_LINES)
                    for a in ((0,0,0),(1,0,0),(0,1,0),(1,1,0),(0,0,1),(1,0,1),(0,1,1),(1,1,1)):
                        for axis in range(3):
                            if a[axis]==0:
                                b=list(a);b[axis]=1
                                for v in (a,b):gl.glVertex3f(*(hit[i]-.005+v[i]*1.01 for i in range(3)))
                    gl.glEnd()
            if time.monotonic()-ui_last>.08:
                ui();gl.glBindTexture(gl.GL_TEXTURE_2D,ui_texture);gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MIN_FILTER,gl.GL_LINEAR);gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAG_FILTER,gl.GL_LINEAR);gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA,overlay.get_width(),overlay.get_height(),0,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,pygame.image.tobytes(overlay,'RGBA',True));ui_last=time.monotonic()
            gl.glMatrixMode(gl.GL_PROJECTION);gl.glLoadIdentity();gl.glOrtho(0,1,0,1,-1,1);gl.glMatrixMode(gl.GL_MODELVIEW);gl.glLoadIdentity();gl.glDisable(gl.GL_DEPTH_TEST);gl.glEnable(gl.GL_TEXTURE_2D);gl.glBindTexture(gl.GL_TEXTURE_2D,ui_texture);gl.glEnable(gl.GL_BLEND);gl.glBlendFunc(gl.GL_SRC_ALPHA,gl.GL_ONE_MINUS_SRC_ALPHA);gl.glColor4f(1,1,1,1);gl.glBegin(gl.GL_QUADS)
            for uv in ((0,0),(1,0),(1,1),(0,1)):gl.glTexCoord2f(*uv);gl.glVertex2f(*uv)
            gl.glEnd();gl.glDisable(gl.GL_TEXTURE_2D);gl.glDisable(gl.GL_BLEND);gl.glEnable(gl.GL_DEPTH_TEST)
            pygame.display.flip()
            if time.monotonic()-lastsave>3:persist()
            if args.prueba and frame>=args.prueba:
                if args.captura:
                    pixels=gl.glReadPixels(0,0,width,height,gl.GL_RGB,gl.GL_UNSIGNED_BYTE);image=pygame.image.frombytes(pixels,(width,height),'RGB');pygame.image.save(pygame.transform.flip(image,False,True),args.captura)
                running=False
    finally:
        persist();pool.shutdown(wait=True,cancel_futures=True);world.file.close();pygame.quit()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ventana',action='store_true');parser.add_argument('--resolucion',help='Tamaño de ventana, por ejemplo 1920x1080');parser.add_argument('--prueba',type=int,default=0,help='Cerrar después de N cuadros');parser.add_argument('--captura');parser.add_argument('--sin-guardar',action='store_true');parser.add_argument('--lugar',choices=[p['id'] for p in PLACES]);parser.add_argument('--panel',choices=['inicio','catalogo','lugares','ajustes']);args=parser.parse_args()
    run(args)
