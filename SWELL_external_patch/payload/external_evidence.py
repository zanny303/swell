"""On-demand public evidence; no credentials or generated substitute observations.
GNSS is independent point-position evidence, not a co-referenced LOS validation.
"""
import datetime as dt, hashlib, json, math, re, statistics, concurrent.futures
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

HOLDINGS='https://geodesy.unr.edu/NGLStationPages/DataHoldings.txt'
TENV='https://geodesy.unr.edu/gps_timeseries/IGS20/tenv3/IGS20/'
OPENALEX='https://api.openalex.org/works'
CITATION='Blewitt, Hammond & Kreemer (2018), https://doi.org/10.1029/2018EO104623; cite original station operator as well.'
def stamp(): return dt.datetime.now(dt.timezone.utc).isoformat()
def fetch(url, limit=8_000_000):
    with urlopen(Request(url,headers={'User-Agent':'SWELL research prototype/1.0','Accept':'application/json, text/plain, */*'}),timeout=20) as r:
        b=r.read(limit+1)
    if not b or len(b)>limit: raise ValueError('Empty or oversized provider response')
    return b

def active(root):
    raw=(Path(root)/'site/data/site.json').read_bytes(); s=json.loads(raw)
    if 'NISAR' not in str(s.get('source','')).upper() or 'SYNTH' in str(s.get('source','')).upper(): raise ValueError('Load a real NISAR study first')
    p=json.loads((Path(root)/'out/real_site_provenance.json').read_text()); pairs=p['steps']['radar']['pairs']; dates=[pairs[0]['ref']]+[x['sec'] for x in pairs]
    dates=[dt.date.fromisoformat(d) for d in dates]
    if len(dates)!=len(s['pass_days']) or [(d-dates[0]).days for d in dates]!=s['pass_days'] or any(pairs[i]['sec']!=pairs[i+1]['ref'] for i in range(len(pairs)-1)): raise ValueError('Radar provenance does not match active acquisition timeline')
    if max(abs(float(x)-float(y)) for x,y in zip(p['bbox'],s['bbox']))>.03: raise ValueError('Radar provenance AOI does not match study')
    return s,dates,hashlib.sha256(raw).hexdigest()

def stations(raw,bbox,dates):
    w,s,e,n=bbox; found=[]
    for line in raw.decode().splitlines():
        a=line.split()
        try:
            if len(a)<11 or not re.fullmatch('[A-Z0-9]{4}',a[0]):continue
            lat,lon=map(float,a[1:3]); lon=(lon+180)%360-180
            first,last=map(dt.date.fromisoformat,a[7:9]);
            if w<=lon<=e and s<=lat<=n and first<=dates[-1] and last>=dates[0]:
                found.append({'station':a[0],'lat':lat,'lon':lon,'first':first.isoformat(),'last':last.isoformat(),'covers_full_window':first<=dates[0] and last>=dates[-1]})
        except (ValueError,IndexError):continue
    return sorted(found,key=lambda x:(not x['covers_full_window'],x['station']))

def series(raw,station,dates):
    lines=raw.decode().splitlines(); header=[x.strip('_') for x in lines[0].split()]; cols={x:header.index(x) for x in ('site','YYMMMDD','u0(m)','up(m)','sig_u(m)')}; data={}
    for line in lines[1:]:
        a=line.split()
        try:
            day=dt.datetime.strptime(a[cols['YYMMMDD']],'%y%b%d').date(); up=(float(a[cols['u0(m)']])+float(a[cols['up(m)']]))*1000; sig=float(a[cols['sig_u(m)']])*1000
            if a[cols['site']]!=station or not math.isfinite(up) or not 0<sig<1000:continue
            if day in dates:data[day]=(up,sig)
        except (ValueError,IndexError):continue
    base=next((data[d][0] for d in dates if d in data),None); out=[]
    for day in dates:
        v=data.get(day);out.append({'date':day.isoformat(),'vertical_change_mm':round(v[0]-base,3) if v else None,'daily_formal_sigma_mm':round(v[1],3) if v else None})
    return out

def _save(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    import tempfile,os
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False,mode='w',encoding='utf-8') as f: json.dump(payload,f,allow_nan=False); name=f.name
    os.replace(name,path)

def gnss(root):
    s,dates,key=active(root); raw=fetch(HOLDINGS,12_000_000); found=stations(raw,s['bbox'],dates); selected=found[:6]
    def load(row):
        url=TENV+row['station']+'.tenv3'
        try:
            b=fetch(url); values=series(b,row['station'],dates)
            return {**row,'url':url,'sha256':hashlib.sha256(b).hexdigest(),'points':values,'matched_dates':sum(x['vertical_change_mm'] is not None for x in values),'station_page':'https://geodesy.unr.edu/NGLStationPages/stations/'+row['station']+'.sta'}
        except Exception as exc:return {**row,'url':url,'error':str(exc)[:200]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: records=list(pool.map(load,selected))
    report={'site_sha256':key,'site':s['name'],'dates':[x.isoformat() for x in dates],'retrieved_utc':stamp(),'catalog':HOLDINGS,'catalog_sha256':hashlib.sha256(raw).hexdigest(),'station_count':len(found),'stations':records,'citation':CITATION,'frame':'IGS20 daily final solutions','warning':'GNSS vertical change relative to first available matched day. Point monument, not grid average. No LOS projection, co-reference, step or stability correction performed. Does not pass T1 or validate clay mechanism. Daily formal sigma is not change uncertainty.'}
    _save(Path(root)/'out/external_evidence'/f'gnss-{key}.json',report);return report

def cached_gnss(root,site_hash):
    if not re.fullmatch('[a-f0-9]{64}',str(site_hash)):return None
    p=Path(root)/'out/external_evidence'/f'gnss-{site_hash}.json'
    return json.loads(p.read_text()) if p.exists() else None

def abstract(index):
    if not isinstance(index,dict):return ''
    positions={}
    for word,loc in index.items():
        if isinstance(loc,list):
            for i in loc:
                if isinstance(i,int) and 0<=i<220:positions[i]=str(word)
    # do not silently assemble discontinuous text
    end=0
    while end in positions:end+=1
    return ' '.join(positions[i] for i in range(end))

def search(root,question):
    q=str(question).strip()
    if not 3<=len(q)<=200:raise ValueError('Use a public scientific search query of 3–200 characters; no private information')
    url=OPENALEX+'?'+urlencode({'search':q,'per_page':8,'filter':'is_oa:true','select':'id,doi,title,publication_year,abstract_inverted_index,is_retracted,type'})
    raw=fetch(url,2_000_000); rows=json.loads(raw)['results']; records=[]
    for r in rows:
        if r.get('is_retracted') is True or r.get('type') in ('retraction','correction','erratum'):continue
        ident=str(r.get('id',''))
        if not re.fullmatch(r'https://openalex.org/W\d+',ident):continue
        text=abstract(r.get('abstract_inverted_index')); title=str(r.get('title') or '')[:400]
        if not title:continue
        records.append({'id':'OA-'+ident.rsplit('/',1)[1],'title':title,'url':ident,'doi':r.get('doi'),'year':r.get('publication_year'),'text':text,'kind':'open-access abstract excerpt' if text else 'bibliographic metadata only','type':r.get('type'),'provider':'OpenAlex','retrieved_utc':stamp()})
    report={'query':q,'retrieved_utc':stamp(),'source':'OpenAlex','sources':records,'response_sha256':hashlib.sha256(raw).hexdigest(),'warning':'Search results are abstracts or metadata, not full-paper assessment or site validation. Query was sent to OpenAlex.'}
    _save(Path(root)/'out/external_evidence'/('papers-'+hashlib.sha256(q.encode()).hexdigest()+'.json'),report);return report

def research_for_question(root,question,k=2):
    # Only explicitly retrieved, locally cached research. Never send chat text to third-party search.
    import literature_rag
    q=set(literature_rag.words(question)); stop={'the','and','for','what','how','with','this','from','are','does','can','was','that','you','why','use','which','of','to','in','is','it','a','an','my','me'};q-=stop
    ranked={}
    for f in sorted((Path(root)/'out/external_evidence').glob('papers-*.json'),key=lambda x:x.stat().st_mtime,reverse=True)[:30]:
        try:
            report=json.loads(f.read_text())
            for r in report['sources']:
                if not r['text']:continue
                terms=set(literature_rag.words(r['title']+' '+r['text'])); score=len(q&terms)
                if score>=2 and (r['id'] not in ranked or score>ranked[r['id']][0]): ranked[r['id']]=(score,{**r,'text':'OpenAlex abstract excerpt (not full text): '+r['text'],'sha256':report['response_sha256']})
        except (OSError,ValueError,KeyError,TypeError):continue
    return [r for _,r in sorted(ranked.values(),key=lambda x:x[0],reverse=True)[:k]]
