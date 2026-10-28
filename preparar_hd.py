"""Construye recursos gráficos HD desde los datos originales. Solo Python."""
from pathlib import Path
import json,zlib,time
import numpy as np
from mapa_datos import MapReader
ROOT=Path(__file__).resolve().parent

def main():
    data=json.loads((ROOT/'giza_catalogo.json').read_text());blocks=data['bloques'];index=json.loads((ROOT/'giza_indice.json').read_text())
    # El terreno lejano no incluye copas, cañas ni objetos pequeños.
    ground=np.array([b['forma'] not in ('nada','cruz','hojas','valla','muro','panel','puerta','trampilla','farol','cartel') and not any(k in b['id'] for k in ('_log','_wood','_stem','_hyphae')) for b in blocks]);ground[0]=False
    height=np.zeros((752,752),np.float32);ids=np.zeros((752,752),np.uint16)
    start=time.monotonic()
    with MapReader(ROOT) as f:
        for key,(offset,size) in index.items():
            cx,cz=map(int,key.split(','));f.seek(offset);tile=np.frombuffer(zlib.decompress(f.read(size)),dtype='<u2').reshape(16,16,256)
            # Alturas estables a intervalos de cuatro metros, sin vegetación.
            sampled=tile[::4,::4,:];valid=ground[sampled];top=np.max(np.where(valid,np.arange(256)[None,None,:],0),axis=2)
            mat=np.take_along_axis(sampled,top[:,:,None],axis=2)[:,:,0]
            a,b=(cx+94)*4,(cz+63)*4;height[a:a+4,b:b+4]=top+1;ids[a:a+4,b:b+4]=mat
    # Un filtro ligero elimina dientes debidos al redondeo del terreno natural.
    protected=np.zeros(height.shape,bool)
    xx,zz=np.meshgrid(np.arange(752)*4-1504,np.arange(752)*4-1008,indexing='ij')
    for p in data['piramides']:
        protected|=(abs(xx-p['cx'])<p['media']+18)&(abs(zz-p['cz'])<p['media']+18)
    for _ in range(2):
        smooth=(height*4+np.roll(height,1,0)+np.roll(height,-1,0)+np.roll(height,1,1)+np.roll(height,-1,1))/8
        height=np.where(protected,height,smooth)
    np.savez_compressed(ROOT/'giza_terreno_hd.npz',height=height,ids=ids)
    print('Terreno HD:',round(time.monotonic()-start,1),'s',flush=True)
    # Las estructuras se dibujan con sus bloques reales incluso desde lejos.
    from giza import World
    world=World();keys=set()
    def area(x0,z0,x1,z1):
        for cx in range(int(x0)//16,int(x1)//16+1):
            for cz in range(int(z0)//16,int(z1)//16+1):keys.add((cx,cz))
    for p in data['piramides']:
        m=p['media']+13;area(p['cx']-m,p['cz']-m,p['cx']+m,p['cz']+m)
    for bounds in [(266,394,397,446),(296,450,346,500),(-224,296,-164,392),(-540,714,-488,772),(116,-28,156,28),(-422,-182,-158,122),(208,-112,342,132),(-472,418,-378,642),(18,588,68,638),(178,818,422,994)]:area(*bounds)
    arrays=[];spans=[];offset=0
    for i,key in enumerate(sorted(keys)):
        meshes=world.mesh(*key);arr=meshes[0];quads=arr.reshape(-1,4,9)
        # El exterior es visible al cielo. Las cámaras se cargan al acercarse.
        arr=quads[quads[:,0,5]>.5].reshape(-1,9).copy()
        spans.append([*key,offset,len(arr)]);arrays.append(arr);offset+=len(arr)
        if i%200==0:print('Monumentos',i,'/',len(keys),flush=True)
    np.savez_compressed(ROOT/'giza_monumentos_hd.npz',vertices=np.concatenate(arrays),spans=np.array(spans,dtype=np.int32))
    print('Recursos HD listos:',offset,'vértices,',len(keys),'sectores',flush=True)
if __name__=='__main__':main()
