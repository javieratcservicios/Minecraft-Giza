"""Lectura transparente del mapa continuo o dividido, sin Git LFS ni descargas."""
from bisect import bisect_right
import json
from pathlib import Path

class MapReader:
    """Interfaz seek/read sobre partes consecutivas; no carga el mapa completo."""
    def __init__(self, root):
        root=Path(root);continuous=root/'giza_mapa.bin'
        if continuous.exists():paths=[continuous];expected=None
        else:
            manifest=json.loads((root/'giza_mapa.manifest.json').read_text())
            paths=[root/p['file'] for p in manifest['parts']]
            expected=[p['bytes'] for p in manifest['parts']]
        sizes=[p.stat().st_size for p in paths]
        if expected is not None and sizes!=expected:raise OSError('El mapa está incompleto: vuelve a descargar el repositorio completo.')
        self.starts=[];self.size=0
        for size in sizes:self.starts.append(self.size);self.size+=size
        self.files=[p.open('rb') for p in paths];self.position=0
    def seek(self,offset,whence=0):
        position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset if whence==2 else -1
        if position<0:raise ValueError('Posición de mapa inválida')
        self.position=position;return position
    def read(self,size=-1):
        remaining=max(0,self.size-self.position) if size<0 else min(size,max(0,self.size-self.position));pieces=[]
        while remaining:
            part=bisect_right(self.starts,self.position)-1
            end=self.starts[part+1] if part+1<len(self.starts) else self.size
            count=min(remaining,end-self.position);f=self.files[part];f.seek(self.position-self.starts[part]);data=f.read(count)
            if len(data)!=count:raise OSError('Una parte del mapa está truncada')
            pieces.append(data);self.position+=count;remaining-=count
        return b''.join(pieces)
    def close(self):
        for f in self.files:f.close()
    def __enter__(self):return self
    def __exit__(self,*exc):self.close()
