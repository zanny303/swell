"""Create a seven-slide demo from a successfully completed real SWELL recording.
Uses only captured application screenshots and values from the verified exported ZIP.
Requires python-pptx and Pillow. No generated imagery or test metrics.
"""
from pathlib import Path
import argparse,io,json,zipfile,hashlib
from PIL import Image
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path);p.add_argument('--team',required=True);p.add_argument('--members',required=True,help='Comma-separated team member names');a=p.parse_args()
    folders=sorted(Path('.').glob('demo_stakeholder_*'));d=a.folder or (folders[-1] if folders else None)
    if not d:raise SystemExit('Run record_stakeholder_demo.py first.')
    with zipfile.ZipFile(d/'SWELL-stakeholder-decision.zip') as z:
        man=json.loads(z.read('manifest.json'));assert all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in man['sha256'].items());e=json.loads(z.read('mission/evidence.json'));r=json.loads(z.read('mission/paired-review.json'));dec=json.loads(z.read('mission/decision.json'))
    if 'NISAR' not in e['source'].upper() or 'SYNTH' in e['source'].upper() or not man['mass_balance_passed']:raise SystemExit('A completed real-data package with numerical checks is required.')
    def pic(s):
        a=list(d.glob('*'+s+'.png'))
        if not a:raise SystemExit('Missing actual screenshot: '+s)
        return a[0]
    shots=[pic(x) for x in ['radar_and_role','local_terrain','intervention_footprint','same_storm_comparison','numerical_review','stakeholder_action']]
    ai=list(d.glob('*decision_and_live_ai.png'));shots.append(ai[0] if ai else pic('exported_decision'))
    prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
    BG=RGBColor.from_string('08131D'); FG=RGBColor.from_string('E9F4F6'); MUTED=RGBColor.from_string('A5C2CB'); ACC=RGBColor.from_string('48E1C8'); LINE=RGBColor.from_string('233F50')
    def text(sl,x,y,w,h,content,size=20,color=FG,bold=False):
        sh=sl.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=sh.text_frame;tf.word_wrap=True;tf.margin_left=tf.margin_right=0;tf.margin_top=tf.margin_bottom=0
        for k,line in enumerate(content.split('\n')):
            q=tf.paragraphs[0] if k==0 else tf.add_paragraph();q.text=line;q.font.name='Aptos';q.font.size=Pt(size);q.font.bold=bold;q.font.color.rgb=color;q.space_after=Pt(5)
        return sh
    def box(sl,x,y,w,h):
        s=sl.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(h));s.fill.solid();s.fill.fore_color.rgb=RGBColor.from_string('101F2B');s.line.color.rgb=LINE
    def image(sl,path,x,y,w,h,crop=None):
        im=Image.open(path).convert('RGB');
        if crop:im=im.crop(tuple(round(v*dim) for v,dim in zip(crop,[im.width,im.height,im.width,im.height])))
        buf=io.BytesIO();im.save(buf,format='PNG');buf.seek(0);scale=min(w/im.width,h/im.height);iw,ih=im.width*scale,im.height*scale;sl.shapes.add_picture(buf,Inches(x+(w-iw)/2),Inches(y+(h-ih)/2),width=Inches(iw),height=Inches(ih))
    def slide(i,title,kicker):
        sl=prs.slides.add_slide(prs.slide_layouts[6]);sl.background.fill.solid();sl.background.fill.fore_color.rgb=BG;text(sl,.4,.22,11,.3,'SWELL  /  '+kicker,12,ACC,True);text(sl,.4,.65,12.5,.95,title,31,FG,True);text(sl,.42,7.15,12,.25,'2026 NASA Space Apps Challenge · Dancing with the SARs · '+str(i)+'/7',10,MUTED);return sl
    def side(sl,headline,sub,photo,extra=None):
        box(sl,.4,1.72,3.35,5.18);text(sl,.65,1.95,2.85,1.15,headline,24,ACC,True);text(sl,.65,3.12,2.85,3.4,sub,17,MUTED)
        image(sl,photo,3.97,1.62,8.96,5.17)
        if extra:text(sl,4.05,6.77,8.8,.3,extra,10,MUTED)
    sl=slide(1,'See change. Test a decision. Verify the outcome.','EARTH INTELLIGENCE');side(sl,'Satellite evidence → human action',f'{a.team}\n{a.members}\n\nReal NASA NISAR observations and interactive local terrain experiments.',shots[0]);
    sl=slide(2,'Radar is evidence, not a direct damage measurement.','OBSERVE');side(sl,f"{len(e['dates'])} observation dates",f"{e['valid_cells']:,} of {e['total_cells']:,} cells eligible for latest-pair review.\n{e['dates'][0]} to {e['dates'][-1]}.\nReference effects and moisture can alter phase. SWELL preserves unknowns.",shots[0],e['quality_basis']);
    sl=slide(3,'Move from orbital observations into a real local terrain grid.','LOCALIZE');side(sl,f"{r['terrain']['dx']} m analysis grid",'USGS or Copernicus provider elevation, georeferenced and hashed. Optional D8 drainage analysis identifies contributing area. Regional radar and local hydrology remain separate evidence types.',shots[1]);
    sl=slide(4,'Paint a proposed intervention. Hold the storm constant.','MANIPULATE');side(sl,f"{len(r['edits'])} edited cells",f"Storm: {sum(r['storm_mm_h']):.1f} mm over {len(r['storm_mm_h'])} hours.\nBaseline and edited alternatives use the same DEM and forcing. Idealized drainage / infiltration; not an engineered network.",shots[2]);
    m=r['metrics'];sl=slide(5,'Compare outcomes, not just map colors.','SIMULATE');side(sl,f"{m['baseline_storage_m3']:,.1f} → {m['intervention_storage_m3']:,.1f} m³",f"Final modeled storage.\nPeak depth: {m['baseline_peak_m']:.3f} → {m['intervention_peak_m']:.3f} m.\nSame event, same boundary. Compared on a shared depth scale.",shots[3],'Conditional simulation on real terrain; not observed flood depths.');
    sl=slide(6,'Test whether the result survives different assumptions.','REVIEW');side(sl,'Four paired cases',f"Both alternatives tested at 15 s and with ±20% infiltration sensitivity.\nStorage difference: {r['storage_reduction_range_m3'][0]:,.1f} to {r['storage_reduction_range_m3'][1]:,.1f} m³.\nMass conservation checked; not field accuracy or probability.",shots[4]);
    sl=slide(7,'Deliver a concrete stakeholder investigation plan.','ACT & VERIFY');side(sl,'Evidence-linked draft',f"{dec['role'].replace('_',' ').title()} review package: exact run, observations, physical assumptions, GeoTIFFs, model results and file hashes.\nNext: independent field observations and drainage-capacity verification.\nAI explains; people decide.",shots[6]);
    prs.save(str(d/'SWELL_7_slide_demo.pptx'));print('Created',d/'SWELL_7_slide_demo.pptx','— add disclosures/references on the project page, and verify team names.')
if __name__=='__main__':main()
