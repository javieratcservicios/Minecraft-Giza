"""Renderizado HD nativo: materiales, terreno, sombras solares y cielo atmosférico."""
from pathlib import Path
import ctypes, math, time
import numpy as np
from OpenGL import GL as gl
from OpenGL.GLU import gluPerspective, gluLookAt
from OpenGL.GL.shaders import compileProgram, compileShader
ROOT=Path(__file__).resolve().parent
SUN=np.array([-.48,.72,.5],np.float32);SUN/=np.linalg.norm(SUN)

def program(vertex,fragment):
    return compileProgram(compileShader(vertex,gl.GL_VERTEX_SHADER),compileShader(fragment,gl.GL_FRAGMENT_SHADER))

VERTEX='''#version 120
varying vec2 uv; varying vec2 tileCell; varying vec4 color; varying vec3 point;
void main(){ uv=gl_MultiTexCoord0.xy; tileCell=floor(uv*vec2(32,19)); color=gl_Color; point=gl_Vertex.xyz; gl_Position=gl_ModelViewProjectionMatrix*gl_Vertex; }
'''
FRAGMENT='''#version 120
uniform sampler2D atlas, coverage, shadowTex, materialPalette;
uniform vec3 eye, sun; uniform float day, lamp, clockTime, shadowSize;
uniform mat4 lightMatrix; uniform int mode, staticMesh, depthPass;
uniform float waterLayer, shadowsEnabled;
varying vec2 uv; varying vec2 tileCell; varying vec4 color; varying vec3 point;
float hash(vec3 p){ return fract(sin(dot(p,vec3(127.1,311.7,74.7)))*43758.5453); }
float noise(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);}
vec3 sky(vec3 dir){float h=pow(clamp(dir.y,0.0,1.0),0.45);return mix(vec3(.78,.79,.72),vec3(.20,.45,.68),h)*mix(.11,1.0,day);}
float shadow(vec3 n){
 if(shadowsEnabled<.5)return 1.0;
 vec4 lp=lightMatrix*vec4(point,1.0);vec3 p=lp.xyz/lp.w*.5+.5;
 if(p.x<0.0||p.x>1.0||p.y<0.0||p.y>1.0||p.z>1.0)return 1.0;
 float bias=max(.00012,.0005*(1.0-dot(n,sun)));float sum=0.0;
 for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)sum+=p.z-bias<=texture2D(shadowTex,p.xy+vec2(x,y)/shadowSize).r?1.0:0.0;
 return sum/9.0;
}
void main(){
 vec2 mapUV=(point.xz-vec2(-1504.0,-1008.0))/3008.0;
 vec4 occupied=texture2D(coverage,mapUV);
 if(mode==1&&occupied.r>.5)discard;
 if(staticMesh==1&&occupied.g>.5)discard;
 vec4 tex;float water=0.0;
 if(mode==0){vec2 cell=tileCell;vec2 local=clamp(uv*vec2(32,19)-cell,vec2(.01),vec2(.99));vec2 atlasUV=(cell*136.0+vec2(4.0)+local*128.0)/vec2(4352.0,2584.0);vec4 average=texture2D(materialPalette,(cell+.5)/vec2(32,19));float footprint=max(length(dFdx(uv)*vec2(32,19)),length(dFdy(uv)*vec2(32,19)));float fade=smoothstep(.10,.55,footprint);tex=mix(texture2D(atlas,atlasUV),average,fade);if(tex.a<.2)discard;water=abs(cell.y*32.0+cell.x-waterLayer)<.2?1.0:0.0;}
 else {float grain=noise(point*.7)*.05+noise(point*.055)*.055;tex=vec4(color.rgb*(.94+grain),1);water=color.b>color.r*1.12&&point.y<18.0?1.0:0.0;}
 if(depthPass==1){gl_FragColor=vec4(1);return;}
 vec3 normal=normalize(cross(dFdx(point),dFdy(point)));if(dot(normal,eye-point)<0.0)normal=-normal;
 float distance=length(point-eye), skyAccess=mode==1?1.0:color.r, ao=mode==1?1.0:color.g;
 ao=mix(ao,1.0,smoothstep(100.0,450.0,distance));
 float shade=shadow(normal),diffuse=max(dot(normal,sun),0.0);
 vec3 sunColor=vec3(1.0,.88,.68);vec3 ambient=mix(vec3(.07,.09,.14),vec3(.31,.36,.42),day);
 vec3 light=(ambient*.75+sunColor*diffuse*shade*day*1.1)*skyAccess*ao;
 float torch=lamp*pow(max(0.0,1.0-distance/22.0),1.5);light+=vec3(1.0,.83,.59)*torch*(.12+.88*max(dot(normal,normalize(eye-point)),0.0));
 if(mode==0)light=max(light,vec3(color.b*1.2));
 vec3 linear=pow(tex.rgb,vec3(2.2))*light*1.4;
 vec3 rgb=pow(linear/(linear+vec3(.64)),vec3(1.0/2.2));
 float alpha=mode==0?tex.a*color.a:1.0;
 if(water>.5){
   vec3 wave=vec3(sin(point.x*.9+clockTime*.7)*.035,1.0,cos(point.z*.7-clockTime*.5)*.035);normal=normalize(wave);
   vec3 view=normalize(eye-point);float fresnel=.08+.75*pow(1.0-max(dot(view,normal),0.0),4.0);
   vec3 reflected=sky(reflect(-view,normal));vec3 base=vec3(.15,.42,.43)*mix(.24,1.0,day);
   float shine=pow(max(dot(reflect(-sun,normal),view),0.0),150.0)*shade;
   rgb=mix(base,reflected,fresnel)+vec3(1,.84,.53)*shine*.8;alpha=.88;
 }
 vec3 dir=normalize(point-eye);float haze=1.0-exp(-pow(distance/2100.0,1.35));
 rgb=mix(rgb,sky(dir),haze*.85);gl_FragColor=vec4(rgb,alpha);
}
'''
SKY_VERTEX='''#version 120
varying vec2 screen; void main(){screen=gl_Vertex.xy;gl_Position=vec4(gl_Vertex.xy,.9999,1);}
'''
SKY_FRAGMENT='''#version 120
uniform float yaw,pitch,fov,aspect,day;uniform vec3 sun;varying vec2 screen;
void main(){vec3 d=normalize(vec3(screen.x*aspect*tan(fov*.5),screen.y*tan(fov*.5),-1));float y=d.y*cos(pitch)-d.z*sin(pitch),z=d.y*sin(pitch)+d.z*cos(pitch);d=vec3(d.x*cos(yaw)-z*sin(yaw),y,d.x*sin(yaw)+z*cos(yaw));
 float h=pow(clamp(d.y,0.0,1.0),.45);vec3 rgb=mix(vec3(.78,.79,.72),vec3(.20,.45,.68),h);float s=max(dot(d,sun),0.0);
 rgb+=vec3(1,.74,.4)*pow(s,28.0)*.16;rgb+=vec3(1,.93,.74)*smoothstep(.9994,.9998,s)*2.0;rgb*=mix(.1,1.0,day);
 gl_FragColor=vec4(rgb,1);}
'''

def make_atlas(data,raw):
    import pygame
    path=ROOT/'giza_atlas_hd.npy'
    version=ROOT/'giza_atlas_hd.version'
    if path.exists() and version.exists() and version.read_text().strip()=='2':return np.load(path)
    atlas=np.zeros((19*136,32*136,4),np.uint8)
    tile_ids={}
    for b in data['bloques']:
        for face in data['caras'][b['num']*3:b['num']*3+3]:tile_ids.setdefault(face,[]).append(b['id'])
    rng=np.random.default_rng(1842);yy,xx=np.mgrid[:128,:128]
    palettes={'giza_limestone':(205,185,148),'giza_limestone_dark':(177,156,118),'giza_casing':(228,218,190),'giza_granite':(164,119,104),'sand':(208,183,133),'sandstone':(204,179,132),'smooth_sandstone':(214,193,153),'cut_sandstone':(204,183,143),'chiseled_sandstone':(198,176,135),'polished_granite':(170,132,116),'grass_block':(115,133,76),'jungle_leaves':(76,110,56)}
    def smooth_noise(n):
        a=np.uint8(rng.random((n,n))*255);surface=pygame.surfarray.make_surface(np.repeat(a[:,:,None],3,axis=2));surface=pygame.transform.smoothscale(surface,(128,128));return pygame.surfarray.array3d(surface)[:,:,0].T.astype(float)/255-.5
    for i,pixels in enumerate(raw):
        image=pygame.image.frombytes(pixels.tobytes(),(16,16),'RGBA');image=pygame.transform.smoothscale(image,(128,128));tile=np.frombuffer(pygame.image.tobytes(image,'RGBA'),np.uint8).reshape(128,128,4).copy()
        names=tile_ids.get(i,[]);name=next((n for n in names if n in palettes),None)
        low=smooth_noise(6);medium=smooth_noise(24);grain=rng.normal(0,1,(128,128))
        if name:
            palette=palettes[name]
            # Mantener el costado de tierra del bloque de hierba.
            if name=='grass_block' and np.mean(pixels[:,:,:3],axis=(0,1))[0]>np.mean(pixels[:,:,:3],axis=(0,1))[1]:name=None
        if name:
            base=np.array(palette)[None,None,:];variation=low*14+medium*8+grain*1.6
            if name in ('giza_granite','polished_granite'):
                variation=low*8+medium*15+grain*5
                edges=np.minimum.reduce([xx,yy,127-xx,127-yy]);variation-=np.maximum(0,1.3-edges)*5
            if name=='sand':variation+=np.sin(yy*.43+low*5)*1.4
            if 'limestone' in name or name in ('giza_casing','cut_sandstone'):
                edges=np.minimum.reduce([xx,yy,127-xx,127-yy]);variation-=np.maximum(0,1.6-edges)*6
                variation-=np.maximum(0,-grain-1.8)*4
            tile[:,:,:3]=np.clip(base+variation[:,:,None],0,255)
        else:
            tile[:,:,:3]=np.clip(tile[:,:,:3].astype(float)+(medium*3+grain*.8)[:,:,None],0,255)
        padded=np.pad(tile,((4,4),(4,4),(0,0)),mode='edge');y,x=(i//32)*136,(i%32)*136;atlas[y:y+136,x:x+136]=padded
    np.save(path,atlas);version.write_text('2');return atlas

class HDRenderer:
    def __init__(self,world,data,raw):
        self.world=world;self.data=data;self.start=time.monotonic();self.shader=program(VERTEX,FRAGMENT);self.sky_shader=program(SKY_VERTEX,SKY_FRAGMENT)
        self.uniform={n:gl.glGetUniformLocation(self.shader,n) for n in ('atlas','coverage','shadowTex','eye','sun','day','lamp','clockTime','shadowSize','lightMatrix','mode','staticMesh','depthPass','waterLayer','materialPalette','shadowsEnabled')}
        self.atlas_pixels=make_atlas(data,raw);self.texture=gl.glGenTextures(1);gl.glBindTexture(gl.GL_TEXTURE_2D,self.texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA,self.atlas_pixels.shape[1],self.atlas_pixels.shape[0],0,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,self.atlas_pixels);gl.glGenerateMipmap(gl.GL_TEXTURE_2D);gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAX_LEVEL,4);gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MIN_FILTER,gl.GL_LINEAR_MIPMAP_LINEAR);gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAG_FILTER,gl.GL_LINEAR)
        try:
            max_aniso=gl.glGetFloatv(0x84FF);gl.glTexParameterf(gl.GL_TEXTURE_2D,0x84FE,min(8,float(max_aniso)))
        except Exception:pass
        palette=np.zeros((19,32,4),np.uint8)
        for i in range(len(raw)):
            palette[i//32,i%32]=np.mean(self.atlas_pixels[(i//32)*136+4:(i//32)*136+132,(i%32)*136+4:(i%32)*136+132],axis=(0,1))
        self.palette=gl.glGenTextures(1);gl.glBindTexture(gl.GL_TEXTURE_2D,self.palette);gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA,32,19,0,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,palette)
        gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MIN_FILTER,gl.GL_NEAREST);gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAG_FILTER,gl.GL_NEAREST)
        self.coverage=gl.glGenTextures(1);gl.glBindTexture(gl.GL_TEXTURE_2D,self.coverage)
        self.mask=np.zeros((188,188,4),np.uint8);self.keys=frozenset();self.last_shadow=-100;self.revision=-1
        for param in (gl.GL_TEXTURE_MIN_FILTER,gl.GL_TEXTURE_MAG_FILTER):gl.glTexParameteri(gl.GL_TEXTURE_2D,param,gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_WRAP_S,gl.GL_CLAMP_TO_EDGE);gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_WRAP_T,gl.GL_CLAMP_TO_EDGE)
        with np.load(ROOT/'giza_monumentos_hd.npz') as m:
            self.landmark=self.vbo(m['vertices']);self.landmark_keys={(int(row[0]),int(row[1])) for row in m['spans']}
        for cx,cz in self.landmark_keys:self.mask[cz+63,cx+94,0]=255
        self.base_mask=self.mask.copy();self.upload_mask()
        self.terrain=self.make_terrain(raw)
        renderer=gl.glGetString(gl.GL_RENDERER).decode(errors='replace').lower();self.shadow_size=1024 if ('llvmpipe' in renderer or 'soft' in renderer) else 4096
        self.shadow=gl.glGenTextures(1);gl.glBindTexture(gl.GL_TEXTURE_2D,self.shadow);gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_DEPTH_COMPONENT24,self.shadow_size,self.shadow_size,0,gl.GL_DEPTH_COMPONENT,gl.GL_FLOAT,None)
        for param in (gl.GL_TEXTURE_MIN_FILTER,gl.GL_TEXTURE_MAG_FILTER):gl.glTexParameteri(gl.GL_TEXTURE_2D,param,gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_WRAP_S,gl.GL_CLAMP_TO_BORDER);gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_WRAP_T,gl.GL_CLAMP_TO_BORDER);gl.glTexParameterfv(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_BORDER_COLOR,[1,1,1,1])
        self.fbo=gl.glGenFramebuffers(1);gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,self.fbo);gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,gl.GL_DEPTH_ATTACHMENT,gl.GL_TEXTURE_2D,self.shadow,0);gl.glDrawBuffer(gl.GL_NONE);gl.glReadBuffer(gl.GL_NONE)
        if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)!=gl.GL_FRAMEBUFFER_COMPLETE:raise RuntimeError('No se pudo crear el mapa de sombras')
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,0);gl.glDrawBuffer(gl.GL_BACK);gl.glReadBuffer(gl.GL_BACK)
        gl.glUseProgram(self.shader)
        for name,unit in [('atlas',0),('coverage',1),('shadowTex',2),('materialPalette',3)]:gl.glUniform1i(self.uniform[name],unit)
        gl.glUniform3f(self.uniform['sun'],*SUN);gl.glUniform1f(self.uniform['shadowSize'],self.shadow_size);gl.glUniform1f(self.uniform['waterLayer'],data['caras'][data['materiales']['agua']*3+1]);gl.glUseProgram(0)
    def vbo(self,arr):
        arr=np.ascontiguousarray(arr,dtype=np.float32);handle=gl.glGenBuffers(1);gl.glBindBuffer(gl.GL_ARRAY_BUFFER,handle);gl.glBufferData(gl.GL_ARRAY_BUFFER,arr.nbytes,arr,gl.GL_STATIC_DRAW);gl.glBindBuffer(gl.GL_ARRAY_BUFFER,0);return handle,len(arr)
    def draw(self,buffer):
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER,buffer[0]);gl.glEnableClientState(gl.GL_VERTEX_ARRAY);gl.glEnableClientState(gl.GL_TEXTURE_COORD_ARRAY);gl.glEnableClientState(gl.GL_COLOR_ARRAY)
        gl.glVertexPointer(3,gl.GL_FLOAT,36,ctypes.c_void_p(0));gl.glTexCoordPointer(2,gl.GL_FLOAT,36,ctypes.c_void_p(12));gl.glColorPointer(4,gl.GL_FLOAT,36,ctypes.c_void_p(20));gl.glDrawArrays(gl.GL_QUADS,0,buffer[1]);gl.glDisableClientState(gl.GL_VERTEX_ARRAY);gl.glDisableClientState(gl.GL_TEXTURE_COORD_ARRAY);gl.glDisableClientState(gl.GL_COLOR_ARRAY);gl.glBindBuffer(gl.GL_ARRAY_BUFFER,0)
    def upload_mask(self):
        gl.glBindTexture(gl.GL_TEXTURE_2D,self.coverage);gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA,188,188,0,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,self.mask)
    def make_terrain(self,raw):
        with np.load(ROOT/'giza_terreno_hd.npz') as f:h=f['height'];ids=f['ids']
        faces=np.asarray(self.data['caras']).reshape(-1,3);avg=np.mean(raw[:,:,:,:3],axis=(1,2))/255
        palette=avg[faces[:,0]]
        for key,color in [('arena',(0.80,.70,.52)),('arenisca',(.76,.65,.48)),('hierba',(.43,.48,.28)),('cultivo',(.47,.49,.29)),('trigo',(.52,.52,.29)),('agua',(.15,.40,.44)),('caliza',(.8,.72,.57)),('calizaGastada',(.70,.61,.46))]:palette[self.data['materiales'][key]]=color
        palette[self.data['materiales']['grava']]=(.74,.66,.52)
        palette[self.data['materiales']['piedra']]=(.70,.64,.53)
        i,j=np.meshgrid(np.arange(751),np.arange(751),indexing='ij');cx=i//4-94;cz=j//4-63
        tiles_visible=np.ones((188,188),bool)
        for a,b in self.landmark_keys:tiles_visible[a+94,b+63]=False
        visible=tiles_visible[i//4,j//4]
        i,j=i[visible],j[visible];verts=np.zeros((len(i),4,9),np.float32)
        for k,(a,b) in enumerate(((0,1),(1,1),(1,0),(0,0))):
            verts[:,k,0]=(i+a)*4-1504;verts[:,k,1]=h[i+a,j+b]-.04;verts[:,k,2]=(j+b)*4-1008
            verts[:,k,5:8]=palette[ids[i,j]];verts[:,k,8]=1
        return self.vbo(verts.reshape(-1,9))
    def bind_scene_textures(self,shadow=True):
        for unit,tex in [(0,self.texture),(1,self.coverage),(2,self.shadow if shadow else 0),(3,self.palette)]:gl.glActiveTexture(gl.GL_TEXTURE0+unit);gl.glBindTexture(gl.GL_TEXTURE_2D,tex)
        gl.glActiveTexture(gl.GL_TEXTURE0)
    def geometry(self,meshes,transparent=False):
        gl.glUniform1i(self.uniform['mode'],1);gl.glUniform1i(self.uniform['staticMesh'],0);self.draw(self.terrain)
        gl.glUniform1i(self.uniform['mode'],0);gl.glUniform1i(self.uniform['staticMesh'],1);self.draw(self.landmark)
        gl.glUniform1i(self.uniform['staticMesh'],0)
        for lists in meshes.values():gl.glCallList(lists[0])
    def render(self,pos,yaw,pitch,settings,width,height,meshes,revision):
        keys=frozenset(meshes)
        if keys!=self.keys:
            self.mask=self.base_mask.copy()
            for cx,cz in keys:
                if 0<=cx+94<188 and 0<=cz+63<188:self.mask[cz+63,cx+94,:2]=255
            self.upload_mask();self.keys=keys
        gl.glDisable(gl.GL_FOG);gl.glDisable(gl.GL_BLEND);gl.glEnable(gl.GL_DEPTH_TEST);gl.glEnable(gl.GL_MULTISAMPLE);gl.glDisable(gl.GL_ALPHA_TEST)
        gl.glUseProgram(self.shader);self.bind_scene_textures(False)
        gl.glUniform3f(self.uniform['eye'],*pos);gl.glUniform1f(self.uniform['day'],settings['dia']);gl.glUniform1f(self.uniform['clockTime'],time.monotonic()-self.start);gl.glUniform1f(self.uniform['shadowsEnabled'],float(settings.get('sombras',True)))
        indoor=any(self.world.block(math.floor(pos[0]),math.floor(pos[1])+up,math.floor(pos[2])) for up in range(1,41))
        gl.glUniform1f(self.uniform['lamp'],float(indoor))
        if revision!=self.revision or time.monotonic()-self.last_shadow>3:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,self.fbo);gl.glViewport(0,0,self.shadow_size,self.shadow_size);gl.glClear(gl.GL_DEPTH_BUFFER_BIT);gl.glColorMask(False,False,False,False);gl.glEnable(gl.GL_POLYGON_OFFSET_FILL);gl.glPolygonOffset(2,4)
            gl.glMatrixMode(gl.GL_PROJECTION);gl.glLoadIdentity();gl.glOrtho(-1650,1650,-1650,1650,100,4500);projection=gl.glGetFloatv(gl.GL_PROJECTION_MATRIX)
            gl.glMatrixMode(gl.GL_MODELVIEW);gl.glLoadIdentity();center=np.array([-80.,60.,420.]);light=center+SUN*2400;gluLookAt(*light,*center,0,1,0);model=gl.glGetFloatv(gl.GL_MODELVIEW_MATRIX);self.light_matrix=np.asarray(model@projection,np.float32)
            gl.glUniform1i(self.uniform['depthPass'],1);self.geometry(meshes);gl.glUniform1i(self.uniform['depthPass'],0);gl.glDisable(gl.GL_POLYGON_OFFSET_FILL);gl.glColorMask(True,True,True,True);gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,0);gl.glDrawBuffer(gl.GL_BACK);gl.glReadBuffer(gl.GL_BACK);self.last_shadow=time.monotonic();self.revision=revision
        gl.glViewport(0,0,width,height);gl.glClearColor(.61,.68,.69,1);gl.glClear(gl.GL_COLOR_BUFFER_BIT|gl.GL_DEPTH_BUFFER_BIT)
        gl.glDisable(gl.GL_DEPTH_TEST);gl.glDepthMask(False);gl.glUseProgram(self.sky_shader)
        for name,value in [('yaw',math.radians(yaw)),('pitch',math.radians(pitch)),('fov',math.radians(settings['fov'])),('aspect',width/height),('day',settings['dia'])]:gl.glUniform1f(gl.glGetUniformLocation(self.sky_shader,name),value)
        gl.glUniform3f(gl.glGetUniformLocation(self.sky_shader,'sun'),*SUN);gl.glBegin(gl.GL_QUADS)
        for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]:gl.glVertex2f(x,y)
        gl.glEnd();gl.glDepthMask(True);gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glMatrixMode(gl.GL_PROJECTION);gl.glLoadIdentity();gluPerspective(settings['fov'],width/height,.1,4600);gl.glMatrixMode(gl.GL_MODELVIEW);gl.glLoadIdentity();gl.glRotatef(-pitch,1,0,0);gl.glRotatef(yaw,0,1,0);gl.glTranslatef(-pos[0],-pos[1],-pos[2])
        gl.glUseProgram(self.shader);self.bind_scene_textures();gl.glUniformMatrix4fv(self.uniform['lightMatrix'],1,False,self.light_matrix);self.geometry(meshes)
        gl.glEnable(gl.GL_BLEND);gl.glBlendFunc(gl.GL_SRC_ALPHA,gl.GL_ONE_MINUS_SRC_ALPHA);gl.glDepthMask(False)
        for key in sorted(meshes,key=lambda k:-((k[0]*16-pos[0])**2+(k[1]*16-pos[2])**2)):gl.glCallList(meshes[key][1])
        gl.glDepthMask(True);gl.glDisable(gl.GL_BLEND);gl.glUseProgram(0);gl.glActiveTexture(gl.GL_TEXTURE0);gl.glBindTexture(gl.GL_TEXTURE_2D,0)
