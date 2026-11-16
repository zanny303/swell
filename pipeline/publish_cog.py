#!/usr/bin/env python3
"""Convert a georeferenced raster to a validated Cloud Optimized GeoTIFF.

Requires GDAL command-line utilities. Keeps the source file untouched.
Usage: python pipeline/publish_cog.py input.tif --out data/cog/site-motion.cog.tif --units mm --product NISAR_GUNW
"""
import argparse,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
def run(args):
    p=subprocess.run(args,capture_output=True,text=True)
    if p.returncode: raise SystemExit(p.stderr or p.stdout)
    return p.stdout
def main():
    ap=argparse.ArgumentParser();ap.add_argument("source");ap.add_argument("--out",required=True);ap.add_argument("--units",default="unknown");ap.add_argument("--product",default="unspecified");ap.add_argument("--acquisition-date",default="unknown");ap.add_argument("--maturity",default="unknown");a=ap.parse_args()
    src=Path(a.source).resolve();out=Path(a.out).resolve()
    if not src.exists():ap.error(f"source does not exist: {src}")
    out.parent.mkdir(parents=True,exist_ok=True)
    info=json.loads(run(["gdalinfo","-json",str(src)]))
    if not info.get("coordinateSystem",{}).get("wkt"):raise SystemExit("Input has no CRS. Refuse to publish an unreferenced raster.")
    if not info.get("geoTransform"):raise SystemExit("Input has no geotransform. Refuse to publish a raster without spatial registration.")
    run(["gdal_translate",str(src),str(out),"-of","COG","-co","COMPRESS=DEFLATE","-co","OVERVIEWS=AUTO"])
    check=json.loads(run(["gdalinfo","-json",str(out)]))
    if not check.get("coordinateSystem",{}).get("wkt") or not check.get("geoTransform"):raise SystemExit("Output lost spatial registration.")
    manifest={"created_utc":datetime.now(timezone.utc).isoformat(),"source_file":src.name,"cog_file":out.name,"product":a.product,"units":a.units,"acquisition_date":a.acquisition_date,"maturity":a.maturity,"crs":check.get("coordinateSystem",{}).get("wkt"),"geotransform":check.get("geoTransform"),"size":check.get("size"),"bands":[{"type":b.get("type"),"description":b.get("description"),"noDataValue":b.get("noDataValue")} for b in check.get("bands",[])],"validation":"GDAL metadata/georeferencing check only; scientific QA and GNSS validation remain separate"}
    out.with_suffix(out.suffix+".manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
