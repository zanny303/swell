"""Compare independently validated site result JSON files by fitted behaviour signature.

Usage:
  python -m swell.compare out/dallas/results.json out/toulouse/results.json
Only sites whose preregistered tests all pass are ranked as sisters.
"""
from __future__ import annotations
import argparse, json, pathlib
import numpy as np
from .similarity import KEYS

def compare(paths):
    rows = {}
    for name in paths:
        p = pathlib.Path(name)
        d = json.loads(p.read_text())
        rows[d.get("site", p.stem)] = d
    passed = {k:v for k,v in rows.items() if all(t.get("passed") in (True, None) for t in v.get("tests", []))}
    if len(passed) < 2:
        return {"status":"INSUFFICIENT_VALIDATED_SITES","eligible_sites":list(passed),"message":"At least two sites with passing validation are required."}
    names=list(passed)
    X=np.array([[passed[n]["signature"][k] for k in KEYS] for n in names],dtype=float)
    mu=X.mean(0); sd=np.where(X.std(0)>0,X.std(0),1)
    Z=(X-mu)/sd
    D=np.sqrt(((Z[:,None,:]-Z[None,:,:])**2).sum(-1))
    return {"status":"EXPLORATORY_SIMILARITY_NOT_CAUSAL_TRANSFER","features":list(KEYS),
            "warning":"Similarity is descriptive. It does not prove parameter transfer or forecast validity.",
            "rankings":{n:[{"site":names[j],"standardized_distance":round(float(D[i,j]),4)}
                           for j in np.argsort(D[i]) if j!=i] for i,n in enumerate(names)}}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("results",nargs="+");ap.add_argument("--out",default="out/sister_sites.json")
    a=ap.parse_args(); result=compare(a.results)
    pathlib.Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
