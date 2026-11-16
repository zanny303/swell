#!/usr/bin/env python3
"""Search ASF's NISAR catalog. Download/stream separately with Earthdata Login."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
PRODUCTS={"GUNW","GCOV","GSLC","GOFF","SME2","RIFG","RUNW","ROFF","RSLC"}
def main():
 p=argparse.ArgumentParser();p.add_argument("--bbox",required=True);p.add_argument("--product",choices=sorted(PRODUCTS),default="GUNW");p.add_argument("--maturity",choices=["VALIDATED","PROVISIONAL","BETA","ALL"],default="VALIDATED");p.add_argument("--start");p.add_argument("--end");p.add_argument("--limit",type=int,default=100);p.add_argument("--out",default="data/nisar");a=p.parse_args()
 b=[float(x) for x in a.bbox.split(",")]
 if len(b)!=4 or not(-180<=b[0]<b[2]<=180 and -90<=b[1]<b[3]<=90):p.error("invalid bbox")
 try:import asf_search as asf
 except ImportError:raise SystemExit("Install requirements-api.txt to add asf_search.")
 w,s,e,n=b;wkt=f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"
 q={"dataset":"NISAR","processingLevel":a.product,"intersectsWith":wkt,"maxResults":a.limit}
 if a.start:q["start"]=a.start
 if a.end:q["end"]=a.end
 if a.maturity!="ALL":q["dataMaturity"]=a.maturity
 try:
  results=asf.search(**q);geo=results.geojson()
 except Exception as ex:raise SystemExit(f"ASF search failed: {type(ex).__name__}: {ex}")
 if not isinstance(geo,dict):geo=json.loads(geo)
 geo.setdefault("type","FeatureCollection");out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 fn=f"nisar-{a.product.lower()}-inventory.geojson";(out/fn).write_text(json.dumps(geo,indent=2))
 manifest={"created_utc":datetime.now(timezone.utc).isoformat(),"provider":"ASF Search","query":q,"count":len(geo.get("features",[])),"inventory":fn,"download_note":"Download/stream requires NASA Earthdata Login; use ~/.netrc, never browser credentials."}
 (out/"nisar-inventory-manifest.json").write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
