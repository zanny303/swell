import io,json,hashlib,zipfile,unittest
from unittest.mock import patch
import location_services as l
P={'lat':32.7767,'lon':-96.797,'rain_mm':[20,30,50],'cn':80,'proposed_cn':70,'area_m2':10000,'extra_rain_mm':0,'retention_m3':0,'review_radius_m':100,'role':'engineer'}
class LocationTests(unittest.TestCase):
 def test_zero(self): self.assertEqual(l.runoff(0,80),0)
 def test_formula(self): self.assertAlmostEqual(l.runoff(100,80),50.539058,places=4)
 def test_monotonic(self):
  for cn in [40,60,80,98]:
   vals=[l.runoff(p,cn) for p in range(201)];self.assertTrue(all(a<=b for a,b in zip(vals,vals[1:])));self.assertTrue(all(0<=v<=p for p,v in enumerate(vals)))
 def test_scenario(self):
  a=l.screen(P);b=l.screen({**P,'proposed_cn':80});c=l.screen({**P,'retention_m3':100});d=l.screen({**P,'extra_rain_mm':50});self.assertLess(a['daily'][-1]['scenario_runoff_m3'],a['daily'][-1]['baseline_runoff_m3']);self.assertEqual(b['daily'][-1]['scenario_runoff_m3'],b['daily'][-1]['baseline_runoff_m3']);self.assertLess(c['daily'][-1]['scenario_runoff_m3'],a['daily'][-1]['scenario_runoff_m3']);self.assertGreater(d['daily'][-1]['scenario_runoff_m3'],a['daily'][-1]['scenario_runoff_m3']);self.assertAlmostEqual(sum(x['baseline_increment_m3'] for x in a['daily']),a['daily'][-1]['baseline_runoff_m3'])
 def test_invalid(self):
  for edit in [{'lat':91},{'rain_mm':[float('nan')]},{'cn':0},{'rain_mm':[]},{'area_m2':-1},{'lon':None}]:
   with self.assertRaises((ValueError,TypeError)):l.screen({**P,**edit})
 def test_fail_closed(self):
  with patch.multiple(l,alerts=lambda *a:1/0,gauges=lambda *a:1/0,river=lambda *a:1/0,moisture=lambda *a:1/0,soils=lambda *a:1/0,forecast=lambda *a:1/0):
   d=l.snapshot({'lat':['32'],'lon':['-96']});self.assertEqual(len(d['sources']),6);self.assertTrue(all(x['status']=='unavailable' for x in d['sources'].values()))
 def test_adapters(self):
  with patch.object(l,'fetch',return_value=({'type':'FeatureCollection','features':[{'properties':{'event':'Flood Warning'}}]},'stamp','retrieved')):self.assertEqual(l.alerts(32,-96)['data'][0]['event'],'Flood Warning')
  with patch.object(l,'fetch',return_value=({'daily':{'time':['2026-11-15'],'river_discharge':[5]},'daily_units':{'river_discharge':'m³/s'}},'stamp','retrieved')):self.assertEqual(l.river(32,-96)['data']['daily'][0]['discharge_m3s'],5)
 def test_package(self):
  import ezdxf
  z=zipfile.ZipFile(io.BytesIO(l.export(P)));m=json.loads(z.read('manifest.json'));self.assertFalse(m['checks']['engineering_approved']);self.assertFalse(m['checks']['machine_execution_approved']);self.assertTrue(m['checks']['dxf_reopened_audited'])
  for k,v in m['sha256'].items():self.assertEqual(hashlib.sha256(z.read(k)).hexdigest(),v)
  doc=ezdxf.read(io.StringIO(z.read('review-area.dxf').decode()));self.assertEqual(doc.units,6);self.assertFalse(doc.audit().errors);self.assertTrue(not any(x.endswith('.gcode') for x in z.namelist()))
  g=json.loads(z.read('review-area.geojson'));self.assertEqual(g['features'][0]['geometry']['coordinates'],[P['lon'],P['lat']]);ring=g['features'][1]['geometry']['coordinates'][0];self.assertEqual(ring[0],ring[-1])
 def test_antimeridian(self):
  with self.assertRaises(ValueError):l.export({**P,'lon':179.9999})
 def test_exposure(self):
  self.assertIsNone(l.screen(P)['structural_exposure_screen']);a=l.screen({**P,'water_depth_m':2})['structural_exposure_screen'];self.assertAlmostEqual(a['base_pressure_kpa'],19.6133);self.assertAlmostEqual(a['resultant_kn_per_m_width'],19.6133)
