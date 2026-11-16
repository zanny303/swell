"""Explicit Earthdata download helper. Never embeds credentials or claims product availability."""
import argparse,os,json,hashlib,pathlib
p=argparse.ArgumentParser();p.add_argument('--collection',required=True,help='CMR collection short name, from Site Twin catalog or Earthdata Search');p.add_argument('--bbox',nargs=4,type=float,required=True,metavar=('WEST','SOUTH','EAST','NORTH'));p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--out',default='nasa-downloads');p.add_argument('--download',action='store_true');a=p.parse_args();w,s,e,n=a.bbox
if not -180<=w<e<=180 or not -90<=s<n<=90: p.error('Invalid bbox')
import earthaccess
rows=earthaccess.search_data(short_name=a.collection,bounding_box=tuple(a.bbox),temporal=(a.start,a.end),count=10)
print('Granules returned:',len(rows));print('\n'.join(str(r) for r in rows))
if a.download and rows:
    auth=earthaccess.login();out=pathlib.Path(a.out);out.mkdir(exist_ok=True,parents=True);paths=earthaccess.download(rows,str(out),threads=2);manifest=[]
    for f in paths:
        if f is None:continue
        f=pathlib.Path(f)
        if not f.is_file():continue
        with f.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
        manifest.append({'filename':f.name,'sha256':sha,'bytes':f.stat().st_size})
    (out/'download-manifest.json').write_text(json.dumps({'collection':a.collection,'bbox':a.bbox,'start':a.start,'end':a.end,'files':manifest},indent=2))
