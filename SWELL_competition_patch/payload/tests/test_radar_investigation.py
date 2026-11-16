import json
from pathlib import Path
import pytest
from radar_assurance import geometry
from radar_investigation import matching_audit, footprint, within, investigation

def test_geometry_binding_and_outside(tmp_path):
    import numpy as np
    g=geometry(np.arange(500000,500480,80),np.arange(3600480,3600000,-80),2,32614)
    a={'site_hash':'a'*64,'geometry':g,'granules':[{'pair':['a','b']} ]};(tmp_path/'out').mkdir();f=tmp_path/'out'/('radar-assurance-'+a['site_hash']+'.json');f.write_text(json.dumps(a));v=matching_audit(tmp_path,a['site_hash'],2,['a','b']);assert v
    p=footprint(g,0,0);assert within(p,g['lat'][0][0],g['lon'][0][0]);assert not within(p,g['lat'][1][1],g['lon'][1][1]);assert len(p['polygon_lonlat'])==5
    a['geometry']['lat'][0][0]+=.1;f.write_text(json.dumps(a));with_error=False
    with pytest.raises(ValueError,match='centers disagree'):matching_audit(tmp_path,a['site_hash'],2,['a','b'])

def test_audit_no_causal_scores():
    assert investigation(None,{}, {})['hypotheses']==[]
