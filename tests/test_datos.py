"""Integridad del mundo y compatibilidad del mapa dividido."""
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
from mapa_datos import MapReader
from giza import World, DATA, MAT
ROOT=Path(__file__).resolve().parents[1]

class MapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.world=World()
    @classmethod
    def tearDownClass(cls):cls.world.file.close();cls.world.tile.cache_clear()
    def test_partes_integras(self):
        manifest=json.loads((ROOT/'giza_mapa.manifest.json').read_text())
        total=0
        for part in manifest['parts']:
            data=(ROOT/part['file']).read_bytes()
            self.assertEqual(len(data),part['bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(),part['sha256'])
            total+=len(data)
        self.assertEqual(total,manifest['total_bytes'])
    def test_lectura_entre_partes(self):
        manifest=json.loads((ROOT/'giza_mapa.manifest.json').read_text());offset=0
        with MapReader(ROOT) as reader:
            for left,right in zip(manifest['parts'],manifest['parts'][1:]):
                offset+=left['bytes']
                with (ROOT/left['file']).open('rb') as f:f.seek(-37,2);before=f.read()
                with (ROOT/right['file']).open('rb') as f:after=f.read(53)
                reader.seek(offset-37)
                self.assertEqual(reader.read(90),before+after)
            reader.seek(0,2);self.assertEqual(reader.read(1),b'')
    def test_camaras_y_forro(self):
        for position in ((5,104,11),(7,83,0),(-320,72,341),(-590,55,743)):
            self.assertEqual(self.world.block(*position),0,position)
        self.assertEqual(self.world.block(5,101,11),MAT['granito'])
    def test_limites_y_edicion(self):
        self.assertEqual(self.world.block(0,-1,0),0)
        self.assertEqual(self.world.block(0,256,0),0)
        self.assertFalse(self.world.set((0,0,0),1))
        position=(-17,90,-17);before=self.world.block(*position)
        self.assertTrue(self.world.set(position,MAT['tura']))
        self.assertEqual(self.world.block(*position),MAT['tura'])
        self.world.changes.pop(position)
        self.assertEqual(self.world.block(*position),before)
    def test_catalogo_y_mallas(self):
        self.assertEqual(len(DATA['bloques'])-1,872)
        self.assertEqual(len(DATA['lugares']),18)
        self.assertEqual(len(DATA['piramides']),9)
        for cx,cz in ((0,0),(-20,21),(19,26)):
            for mesh in self.world.mesh(cx,cz):
                self.assertEqual(mesh.shape[1],9)
                self.assertEqual(len(mesh)%4,0)
                self.assertTrue(np.isfinite(mesh).all())

if __name__=='__main__':unittest.main()
