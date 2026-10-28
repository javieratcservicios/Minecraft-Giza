"""Interfaz nativa de alta resolución, iconos de materiales y HUD compacto."""
import math,time,textwrap
from pathlib import Path
from functools import lru_cache
import numpy as np
import pygame

class Interface:
    def __init__(self,data,atlas,width,height):
        self.data=data;self.blocks=data['bloques'];self.atlas=atlas;self.scale=max(2,math.ceil(max(width/1280,height/720)));self.surface=pygame.Surface((1280*self.scale,720*self.scale),pygame.SRCALPHA)
        self.fonts={};self.buttons=[];self.mouse=(0,0)
        self.gradient=pygame.Surface(self.surface.get_size(),pygame.SRCALPHA)
        for x in range(1280):pygame.draw.rect(self.gradient,(8,16,22,int(230*max(0,1-x/1050)**1.4)),(x*self.scale,0,self.scale,720*self.scale))
    def rect(self,color,r,border=0,radius=9):
        pygame.draw.rect(self.surface,color,tuple(round(v*self.scale) for v in r),round(border*self.scale),border_radius=round(radius*self.scale))
    def text(self,text,x,y,size=18,color=(237,234,224),font='sans',bold=False):
        key=size,font,bold
        if key not in self.fonts:self.fonts[key]=pygame.font.Font(str(Path(__file__).resolve().parent/'fuentes'/('Serif.ttf' if font=='serif' else 'Semibold.ttf' if bold else 'Regular.ttf')),round(size*self.scale))
        self.surface.blit(self.fonts[key].render(str(text),True,color),(round(x*self.scale),round(y*self.scale)))
    def button(self,label,x,y,w=330,h=44,action=None,primary=False,small=False,selected=False):
        r=pygame.Rect(x,y,w,h);hover=r.collidepoint(self.mouse);bg=(237,225,199,255) if primary else (41,55,62,248) if hover else (21,34,42,238)
        fg=(27,33,34) if primary else (239,235,223);self.rect(bg,r,0,8)
        self.rect((216,183,123,240) if (hover or selected) else (105,119,120,85),r,1,8)
        self.text(label,x+16,y+(h-(15 if small else 18))/2-1,15 if small else 18,fg,bold=primary)
        self.buttons.append((r,action))
    @lru_cache(maxsize=512)
    def icon(self,n,size=64):
        # Proyección isométrica con las texturas reales del material.
        dim=size*self.scale;xy=np.mgrid[:dim,:dim];py=(xy[0]+.5)/dim;px=(xy[1]+.5)/dim;out=np.zeros((dim,dim,4),np.uint8)
        faces=[((.5,.06),(.45,.23),(-.45,.23),0,1.0),((.05,.29),(.45,.23),(0,.43),1,.80),((.5,.52),(.45,-.23),(0,.43),1,.63)]
        for origin,u,v,side,shade in faces:
            inv=np.linalg.inv(np.array([u,v]).T);uv=inv@np.stack([px-origin[0],py-origin[1]]).reshape(2,-1);a,b=uv.reshape(2,dim,dim);mask=(a>=0)&(a<1)&(b>=0)&(b<1)
            layer=self.data['caras'][n*3+side];tile=self.atlas[(layer//32)*136+4:(layer//32)*136+132,(layer%32)*136+4:(layer%32)*136+132]
            colors=tile[np.clip((b*127).astype(int),0,127),np.clip((a*127).astype(int),0,127)].copy();colors[:,:,:3]=(colors[:,:,:3]*shade).astype(np.uint8);out[mask]=colors[mask]
        return pygame.image.frombytes(out.tobytes(),(dim,dim),'RGBA')
    def block_icon(self,n,x,y,size=48):self.surface.blit(self.icon(n,size),(round(x*self.scale),round(y*self.scale)))
    def header(self,title,subtitle=''):
        self.surface.fill((10,20,27,235));self.text('GIZA  /  CREATIVO',38,24,13,(207,181,133),bold=True);self.text(title,38,49,32,bold=True)
        if subtitle:self.text(subtitle,40,91,16,(156,173,179))
    def draw(self,s):
        self.buttons=[];self.mouse=s['mouse'];self.surface.fill((0,0,0,0));panel=s['panel'];blocks=self.blocks;settings=s['settings'];selected=s['selected'];bar=s['bar'];slot=s['slot']
        if panel in ('inicio','pausa'):
            self.surface.blit(self.gradient,(0,0));self.text('GIZA  /  CREATIVO',54,42,15,(224,198,150),bold=True)
            self.text('Giza',48,116,86,font='serif');self.text('Un mundo que merece explorarse.',56,227,22,(222,222,209))
            self.text('Camina entre las pirámides. Descubre sus cámaras.',56,268,16,(169,185,190));self.text('Construye tu propia historia, bloque por bloque.',56,292,16,(169,185,190))
            labels=[('Continuar exploración' if panel=='pausa' else 'Explorar el mundo','jugar'),('Materiales y bloques','catalogo'),('Viajar a un lugar','lugares'),('Ajustes','ajustes')]
            for i,(label,a) in enumerate(labels):self.button(label,56,350+i*57,342,46,a,primary=i==0)
            self.button('Guardar',56,593,163,38,'guardar',small=True);self.button('Salir',235,593,163,38,'salir',small=True)
            self.text('ESC  volver al mundo' if panel=='pausa' else '9 PIRÁMIDES     ·     18 LUGARES     ·     ESCALA 1:1',56,671,12,(193,196,181))
            self.rect((16,30,36,185),(932,573,294,105),0,12);self.text('LA MESETA DE GIZA',950,592,12,(226,199,149),bold=True);self.text('Egipto · 29°58′ N 31°08′ E',950,617,16);self.text('Un bloque, un metro.',950,646,14,(171,187,190))
        elif panel=='lugares':
            self.header('Lugares de Giza','Elige un destino para empezar a explorar.')
            for i,p in enumerate(self.data['lugares']):
                x,y=38+(i%3)*406,143+(i//3)*81;self.button('',x,y,390,70,('lugar',i));self.text(f'{i+1:02}',x+14,y+20,23,(209,179,122),font='serif')
                lines=textwrap.wrap(p['nombre'],29)
                for j,line in enumerate(lines[:2]):self.text(line,x+56,y+13+j*21,16)
                if len(lines)==1:self.text(p['nota'].split('.')[0][:39],x+56,y+39,12,(145,166,174))
            self.button('Volver',1030,662,210,38,'jugar',small=True)
        elif panel=='ajustes':
            self.header('Ajustes','Ajusta la imagen y los controles a tu gusto.')
            self.text('IMAGEN',42,144,13,(211,180,128),bold=True);self.text('MOVIMIENTO',663,144,13,(211,180,128),bold=True)
            rows=[(f'Distancia de detalle   ·   {settings["radio"]*16} m','radio'),(f'Campo de visión   ·   {settings["fov"]}°','fov'),('Iluminación   ·   '+('Día dorado' if settings['dia']>.5 else 'Noche'),'dia'),('Sombras solares   ·   '+('Alta' if settings.get('sombras',True) else 'Desactivadas'),'sombras')]
            for i,(label,a) in enumerate(rows):self.button(label,40,180+i*70,570,54,a)
            self.text('Resolución nativa · materiales HD · antialiasing 4×',44,482,15,(151,171,179));self.text('La distancia al horizonte no limita la exploración.',44,509,14,(151,171,179))
            rows=[(f'Sensibilidad   ·   {settings["sens"]:.2f}','sens'),('Vuelo   ·   '+('Activado' if s['flying'] else 'Desactivado'),'volar'),('Atravesar paredes   ·   '+('Sí' if s['noclip'] else 'No'),'atravesar'),('Restaurar el mapa…','borrar')]
            for i,(label,a) in enumerate(rows):self.button(label,660,180+i*70,570,54,a)
            self.text('WASD moverse   ·   F volar   ·   N atravesar',664,482,15,(151,171,179));self.text('F3 muestra coordenadas y rendimiento.',664,509,14,(151,171,179));self.button('Volver al mundo',930,651,300,46,'jugar',primary=True)
        elif panel=='confirmar':
            self.header('Restaurar el mapa');self.text('¿Borrar todas tus construcciones?',54,230,29,bold=True);self.text('Se restaurará el mapa original de Giza.',56,283,18,(160,180,186));self.button('Restaurar mapa',56,363,340,48,'confirmar_borrar',primary=True);self.button('Cancelar',420,363,240,48,'ajustes')
        elif panel=='catalogo':
            self.header('Materiales','')
            self.rect((18,33,42,255),(40,101,1190,43),0,8);self.text('Buscar por nombre o identificador…' if not s['query'] else s['query']+'▏',55,111,17,(153,173,183) if not s['query'] else (239,234,221))
            for i,c in enumerate(['Todas']+self.data['categorias']):self.button(c,40+(i%8)*150,155+(i//8)*34,143,29,('categoria',c),small=True,selected=s['category']==c)
            for i,(key,label) in enumerate([('','Todos'),('luz','Dan luz'),('gravedad','Caen'),('inflamable','Arden'),('transparente','Transparentes'),('indestructible','Indestructibles')]):self.button(label,40+i*198,231,190,29,('filtro',key),small=True,selected=s['filter_name']==key)
            query=s['query'].lower();found=[b for b in blocks if b['num'] and (s['category']=='Todas' or b['cat']==s['category']) and query in (b['nombre']+' '+b['id']).lower() and (not s['filter_name'] or (b.get('dureza')==-1 if s['filter_name']=='indestructible' else b.get(s['filter_name'])))]
            page=min(s['page'],max(0,math.ceil(len(found)/24)-1))
            for i,b in enumerate(found[page*24:page*24+24]):
                x,y=40+(i%6)*143,277+(i//6)*89;self.button('',x,y,135,81,('bloque',b['num']),selected=b['num']==selected);self.block_icon(b['num'],x+47,y+3,40)
                for j,line in enumerate(textwrap.wrap(b['nombre'],21)[:2]):self.text(line,x+8,y+47+j*14,12)
            self.rect((23,39,47,245),(922,277,310,347),0,12);b=blocks[selected];self.block_icon(selected,1015,285,112)
            for j,line in enumerate(textwrap.wrap(b['nombre'],27)[:2]):self.text(line,942,413+j*23,20,bold=True)
            self.text(b['cat'],944,467,14,(181,193,184));self.text(f'Dureza {b["dureza"]}  ·  Resistencia {b["resistencia"]}',944,495,14,(158,178,185));self.button('Ver ficha completa',942,532,270,35,'ficha',small=True);self.button('Construir con él',942,579,270,35,('usar',selected),primary=True,small=True)
            self.button('‹ Anterior',40,658,150,38,'anterior',small=True);self.button('Siguiente ›',204,658,150,38,('siguiente',len(found)),small=True);self.text(f'{len(found)} materiales  ·  Página {page+1}',380,667,15,(155,177,186));self.button('Volver al mundo',1000,658,232,38,'jugar',small=True)
        elif panel=='ficha':
            b=blocks[selected];self.header(b['nombre'],b['id']);self.block_icon(selected,62,153,150)
            props=[('cat','Categoría'),('dureza','Dureza'),('resistencia','Resistencia a explosiones'),('herramienta','Herramienta'),('nivel','Nivel mínimo'),('luz','Emisión de luz'),('apilable','Apilable'),('renovable','Renovable'),('inflamable','Inflamable'),('gravedad','Cae por gravedad'),('transparente','Transparente'),('forma','Forma'),('version','Versión')]
            for i,(key,label) in enumerate(props):
                v=b.get(key);v='Sí' if v is True else 'No' if v is False else '—' if v is None or v=='' else v;self.text(label,275,154+i*29,16,(156,178,187));self.text(v,500,154+i*29,16)
            self.text('TIEMPOS DE MINADO',785,158,13,(213,184,135),bold=True)
            for i,tier in enumerate(('mano','madera','piedra','hierro','diamante','netherita','oro')):self.text(tier.capitalize(),785,199+i*36,16,(156,178,187));self.text(s['mining_time'](b,tier),927,199+i*36,16)
            for i,line in enumerate(textwrap.wrap(b.get('nota',''),115)[:3]):self.text(line,45,570+i*24,16,(169,188,194))
            self.button('Volver al catálogo',40,658,320,42,'catalogo');self.button('Construir con él',910,658,320,42,('usar',selected),primary=True)
        else:
            self.rect((12,25,32,160),(26,24,258,57),0,10);self.text('MESETA DE GIZA',42,34,12,(220,193,145),bold=True);self.text('Explora · construye · descubre',42,55,14,(223,231,227))
            # Mira pequeña, sin una cruz dominante sobre el paisaje.
            self.rect((245,241,225,230),(638,358,4,4),0,2)
            self.rect((12,25,32,210),(339,628,602,76),0,13)
            for i,n in enumerate(bar):
                x=348+i*65;self.rect((203,173,117,75) if i==slot else (25,39,46,180),(x,635,60,62),0,8)
                if i==slot:self.rect((230,201,144,240),(x,635,60,62),1,8)
                self.block_icon(n,x+8,640,45);self.text(str(i+1),x+5,638,10,(239,230,207) if i==slot else (145,166,176))
            name=blocks[bar[slot]]['nombre'];self.text(name,640-len(name)*4,597,17,(244,238,219))
            self.text('E  Materiales     M  Lugares     ESC  Menú',945,688,12,(220,229,227))
            if s['debug']:
                p=s['pos'];self.rect((10,22,30,190),(26,94,360,62),0,7);self.text(f'{p[0]:.1f} / {p[1]-1.62:.1f} / {p[2]:.1f}  ·  {s["fps"]:.0f} FPS',40,105,14);self.text(f'{"Vuelo" if s["flying"] else "Caminar"}  ·  {s["pending"]} sectores pendientes',40,130,13,(159,181,191))
            if s['fingers']:
                for i,(label,a) in enumerate([('Volar','volar'),('Atravesar','atravesar'),('Bloques','catalogo'),('Lugares','lugares')]):self.button(label,700+i*136,30,130,40,a,small=True)
                self.button('▲',1185,475,75,60,None);self.button('▼',1185,555,75,60,None)
            if s['notice'] and time.monotonic()<s['notice_until']:
                lines=textwrap.wrap(s['notice'],95)[:2]
                self.rect((12,25,32,185),(30,103,690,22+len(lines)*22),0,8)
                for i,line in enumerate(lines):self.text(line,45,114+i*22,14,(229,220,194))
        return self.surface,self.buttons
