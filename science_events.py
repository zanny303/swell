"""NASA EONET current curated event geometry — not synthetic risk markers."""
import json,math,datetime
from earth_services import get
URL='https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=30&limit=250'
def normalize(raw):
    features=[]
    def pt(c):return isinstance(c,list) and len(c)>=2 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in c[:2]) and -180<=c[0]<=180 and -90<=c[1]<=90
    for e in raw.get('events',[]):
        valid=[]
        for g in e.get('geometry',[]):
            try:
                when=datetime.datetime.fromisoformat(g['date'].replace('Z','+00:00'))
                if when.tzinfo is None:continue
                c=g['coordinates'];typ=g['type']
                if typ=='Point' and pt(c):coords=c[:2]
                elif typ=='Polygon' and c and all(len(r)>=4 and all(pt(p) for p in r) and r[0]==r[-1] for r in c):coords=[[p[:2] for p in r] for r in c]
                else:continue
                valid.append((when,typ,coords))
            except (ValueError,TypeError,KeyError):continue
        if not valid:continue
        when,typ,c=max(valid,key=lambda x:x[0]);features.append({'type':'Feature','geometry':{'type':typ,'coordinates':c},'properties':{'id':str(e.get('id','')),'title':str(e.get('title','Event')),'observed_utc':when.isoformat(),'categories':[str(x.get('title','')) for x in e.get('categories',[])],'sources':[{'id':str(x.get('id','')),'url':str(x.get('url',''))} for x in e.get('sources',[]) if str(x.get('url','')).startswith('https://')],'status':'curated event location; not a complete hazard boundary or risk estimate'}})
    return {'type':'FeatureCollection','features':features}
def events():
    raw,t,status=get(URL,300);return {'source':'NASA EONET v3','retrieved_utc':t,'status':status,'collection':normalize(json.loads(raw)),'note':'Latest reported geometry per open event, last 30 days, up to 250 events. Not a global hazard census.'}
