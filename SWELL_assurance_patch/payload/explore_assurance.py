"""Read-only exploration utilities; not a new scientific study or planetary terrain model."""
import argparse,json,hashlib
from pathlib import Path
from science_assurance import plain

def worlds(root):
    from world_mosaics import PRODUCTS
    from PIL import Image
    out=[]
    for body,(name,layer) in PRODUCTS.items():
        path=root/'out/world_mosaics'/f'{body}-trek-z1.jpg';rec={'body':body,'configured_layer':layer,'tile_base':f'https://trek.nasa.gov/tiles/{name}/EQ/{layer}/1.0.0/default/default028mm/1','classification':'Archive imagery, not elevation or planetary physics'}
        if path.exists():
            raw=path.read_bytes();rec['cached_sha256']=hashlib.sha256(raw).hexdigest()
            with Image.open(path) as im:rec['dimensions']=list(im.size);im.verify()
            rec['status']='Cached image verified readable; constituent tile checksums and timing not retained'
        else:rec['status']='Not cached'
        out.append(rec)
    return out

def catalog(bbox):
    from real_site import search_nisar,choose_chain
    if not (-180<=bbox[0]<bbox[2]<=180 and -85<=bbox[1]<bbox[3]<=85):raise ValueError('Invalid bounding box')
    rows=search_nisar(bbox);chain=choose_chain(rows,8)
    return {'bbox':bbox,'catalog_results':len(rows),'candidate_chain':[{k:r.get(k) for k in ('name','ref','sec','maturity','short_name','track','frame','cover')} for r in chain],'status':'Catalog discovery only; not downloaded or processed. Existing study untouched.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',default='.');p.add_argument('--worlds',action='store_true');p.add_argument('--bbox',type=float,nargs=4);a=p.parse_args();root=Path(a.project).resolve();r=worlds(root) if a.worlds else catalog(a.bbox) if a.bbox else p.error('Choose --worlds or --bbox');out=root/'out'/('worlds-assurance.json' if a.worlds else 'candidate-catalog-assurance.json');out.write_text(plain(r));print(plain(r));print(out)
