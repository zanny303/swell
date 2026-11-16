"""Fetch real NASA Trek map tiles, stitch a low-resolution global context mosaic.
Only fixed, allowlisted NASA mission sources. No generated texture on errors.
"""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import os, tempfile, urllib.request

PRODUCTS = {'mars': ('Mars','Mars_Viking_MDIM21_ClrMosaic_global_232m'), 'moon': ('Moon','LRO_WAC_Mosaic_Global_303ppd_v02')}

def mosaic(body, root):
    from PIL import Image
    if body not in PRODUCTS: raise ValueError('Only Mars and Moon have configured global mosaics.')
    name, layer = PRODUCTS[body]
    cache = Path(root)/'out'/'world_mosaics'; cache.mkdir(parents=True,exist_ok=True)
    path = cache/(body+'-trek-z1.jpg')
    if path.exists():
        with Image.open(path) as src: src.verify()
        return path.read_bytes()
    base=f'https://trek.nasa.gov/tiles/{name}/EQ/{layer}/1.0.0/default/default028mm/1'
    def get(rc):
        row,col=rc
        url=f'{base}/{row}/{col}.jpg'
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'SWELL/1.0'}),timeout=18) as r:
            raw=r.read(4_000_001)
        if len(raw)>4_000_000: raise ValueError('Tile too large')
        with Image.open(BytesIO(raw)) as im:
            if im.width>1024 or im.height>1024: raise ValueError('Unexpected tile dimensions')
            return row,col,im.convert('RGB')
    with ThreadPoolExecutor(max_workers=4) as pool: tiles=list(pool.map(get,[(r,c) for r in range(2) for c in range(4)]))
    w,h=tiles[0][2].size
    if any(im.size!=(w,h) for _,_,im in tiles):raise ValueError('Inconsistent tile shape')
    out=Image.new('RGB',(w*4,h*2));
    for r,c,im in tiles:out.paste(im,(c*w,r*h))
    f=BytesIO();out.save(f,'JPEG',quality=92);data=f.getvalue()
    fd,tmp=tempfile.mkstemp(dir=cache,suffix='.part');os.close(fd)
    try:Path(tmp).write_bytes(data);os.replace(tmp,path)
    finally:Path(tmp).unlink(missing_ok=True)
    return data
