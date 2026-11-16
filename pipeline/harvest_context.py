#!/usr/bin/env python3
"""Harvest public context data and verify NASA GIBS layer availability."""
import argparse,csv,json,os,sys,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
USGS="https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
GIBS="https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
LAYERS={"terra":"MODIS_Terra_CorrectedReflectance_TrueColor","aqua":"MODIS_Aqua_CorrectedReflectance_TrueColor","viirs":"VIIRS_SNPP_CorrectedReflectance_TrueColor","imerg":"IMERG_Precipitation_Rate","fire":"VIIRS_SNPP_Thermal_Anomalies_375m_All","cloud":"MODIS_Terra_Cloud_Top_Pressure"}
def get(url):
 req=urllib.request.Request(url,headers={"User-Agent":"SWELL-Earth-Intelligence/0.1"})
 with urllib.request.urlopen(req,timeout=45) as r:return r.read()
def main():
 p=argparse.ArgumentParser();p.add_argument("--bbox",required=True,help="west,south,east,north");p.add_argument("--out",default="data/live");a=p.parse_args()
 b=[float(x) for x in a.bbox.split(",")]
 if len(b)!=4 or not(-180<=b[0]<b[2]<=180 and -90<=b[1]<b[3]<=90):p.error("invalid bbox")
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 m={"generated_utc":datetime.now(timezone.utc).isoformat(),"bbox":b,"feeds":{}}
 try:
  doc=json.loads(get(USGS));w,s,e,n=b
  fs=[f for f in doc["features"] if len(f["geometry"]["coordinates"])>=2 and w<=f["geometry"]["coordinates"][0]<=e and s<=f["geometry"]["coordinates"][1]<=n]
  (out/"usgs-earthquakes.geojson").write_text(json.dumps({"type":"FeatureCollection","features":fs,"metadata":doc.get("metadata",{})}))
  m["feeds"]["usgs"]={"status":"ok","count":len(fs),"source":USGS,"generated":doc.get("metadata",{}).get("generated")}
 except Exception as ex:m["feeds"]["usgs"]={"status":"error","error":str(ex)}
 try:
  url=GIBS+"?"+urllib.parse.urlencode({"service":"WMS","request":"GetCapabilities","version":"1.3.0"})
  xml=ET.fromstring(get(url));names={e.text for e in xml.iter() if e.tag.endswith("Name") and e.text}
  m["feeds"]["gibs"]={"status":"ok","endpoint":GIBS,"layers":{k:{"name":v,"available":v in names} for k,v in LAYERS.items()}}
 except Exception as ex:m["feeds"]["gibs"]={"status":"error","error":str(ex)}
 key=os.getenv("FIRMS_MAP_KEY")
 if key:
  w,s,e,n=b;url=f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{urllib.parse.quote(key)}/VIIRS_SNPP_NRT/{w},{s},{e},{n}/1"
  try:
   raw=get(url).decode("utf-8-sig");(out/"firms-viirs-nrt.csv").write_text(raw)
   m["feeds"]["firms"]={"status":"ok","count":max(0,len(raw.splitlines())-1),"product":"VIIRS_SNPP_NRT","key_configured":True}
  except Exception as ex:m["feeds"]["firms"]={"status":"error","error":str(ex),"key_configured":True}
 else:m["feeds"]["firms"]={"status":"not_configured","required_env":"FIRMS_MAP_KEY"}
 (out/"context-manifest.json").write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
 if any(v.get("status")=="error" for v in m["feeds"].values()):sys.exit(2)
if __name__=="__main__":main()
