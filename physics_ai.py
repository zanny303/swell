"""Optional physics-informed neural surrogate research pipeline for one registered DEM.
Narrow domain: dry-start, constant uniform net rain, one hour, closed boundary, no drains.
Finite-volume discrete residual plus teacher supervision and hard nonnegative mass.
NOT an operational forecast or classical continuous-coordinate PINN. Never auto-deployed.
"""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
import site_twin as st

def make_model(torch):
    nn=torch.nn
    class Surrogate(nn.Module):
        def __init__(self):
            super().__init__();self.net=nn.Sequential(nn.Conv2d(3,16,3,padding=1),nn.SiLU(),nn.Conv2d(16,16,3,padding=1),nn.SiLU(),nn.Conv2d(16,1,1))
        def forward(self,z,rate,t):
            # Inputs rate mm/h, t seconds. Total depth-volume exact for uniform net forcing.
            b=rate.numel();shape=z.expand(b,1,-1,-1);r=rate.reshape(b,1,1,1);tm=t.reshape(b,1,1,1);zn=(shape-shape.mean(dim=(2,3),keepdim=True))/shape.std(dim=(2,3),keepdim=True).clamp_min(.1)
            logits=self.net(torch.cat([zn,(r/100).expand_as(shape),(tm/3600).expand_as(shape)],dim=1));allocation=torch.softmax(logits.flatten(1),dim=1).reshape_as(logits)*shape.shape[-1]*shape.shape[-2]
            return allocation*r*tm/3600000
    return Surrogate()

def conservative_step(torch,z,h,rate,dx,dt=30.,rough=.04):
    # Same discrete closure and donor limits as original fast solver for net precipitation only.
    h=h+rate.reshape(-1,1,1,1)*dt/3600000;head=h+z
    def flow(a,b,za,zb):
        diff=a-b;dep=torch.relu(torch.maximum(a,b)-torch.maximum(za,zb));raw=dep.pow(5/3)*torch.sqrt(abs(diff)/dx+1e-14)/rough*dt/dx
        return torch.sign(diff)*torch.minimum(raw,abs(diff)/8)
    qx=flow(head[:,:,:,:-1],head[:,:,:,1:],z[:,:,:,:-1],z[:,:,:,1:]);qy=flow(head[:,:,:-1,:],head[:,:,1:,:],z[:,:,:-1,:],z[:,:,1:,:]);F=torch.nn.functional
    outgoing=F.pad(torch.relu(qx),(0,1,0,0))+F.pad(torch.relu(-qx),(1,0,0,0))+F.pad(torch.relu(qy),(0,0,0,1))+F.pad(torch.relu(-qy),(0,0,1,0))
    scale=torch.minimum(torch.ones_like(h),h*.25/outgoing.clamp_min(1e-12));qx=qx*torch.where(qx>=0,scale[:,:,:,:-1],scale[:,:,:,1:]);qy=qy*torch.where(qy>=0,scale[:,:,:-1,:],scale[:,:,1:,:]);return h-F.pad(qx,(0,1,0,0))+F.pad(qx,(1,0,0,0))-F.pad(qy,(0,0,0,1))+F.pad(qy,(0,0,1,0))

def train(root,site_id,out,epochs=100):
    import torch
    torch.manual_seed(19);torch.set_num_threads(min(4,torch.get_num_threads()));d,z=st.load(root,site_id)
    if z.size>4096:raise ValueError('Research surrogate limited to 64² cells')
    if not 1<=epochs<=1000:raise ValueError('Epochs 1–1000')
    train_rates=np.array([5,15,25,40,55,70,85,100],np.float32);test_rates=np.array([10,35,65,95],np.float32)
    def teacher(rates):return torch.tensor(np.stack([st.simulate(z,d['dx'],[float(r)],0,0)[0][-1] for r in rates]),dtype=torch.float32)[:,None]
    y=teacher(train_rates);truth=teacher(test_rates);top=torch.tensor(z,dtype=torch.float32)[None,None];rs=torch.tensor(train_rates);test=torch.tensor(test_rates);net=make_model(torch);opt=torch.optim.AdamW(net.parameters(),lr=.003)
    for ep in range(epochs):
        t=torch.randint(0,120,(len(rs),),dtype=torch.int64).float()*30.;h=net(top,rs,t);next_=net(top,rs,t+30);phys=conservative_step(torch,top,h,rs,d['dx']);pred=net(top,rs,torch.full_like(rs,3600));loss=((pred-y)*100).square().mean()+((next_-phys)*100).square().mean()*10;opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),1.0);opt.step()
    with torch.no_grad():
        pred=net(top,test,torch.full_like(test,3600));mae=float(abs(pred-truth).mean());uniform=float(abs(test[:,None,None,None]/1000-truth).mean());mass=float(abs(pred.mean(dim=(1,2,3))-test/1000).max());res=[]
        for t in (0,900,1800,2700,3570):
            tm=torch.full_like(test,t);a=net(top,test,tm);b=net(top,test,tm+30);res.append(float(abs(b-conservative_step(torch,top,a,test,d['dx'])).mean()))
    out=Path(out);out.mkdir(exist_ok=True,parents=True);weights=out/'research-weights.pt';torch.save(net.state_dict(),weights)
    report={'site_id':site_id,'terrain_sha256':d['source_sha256'],'method':'hard mass-constrained convolutional surrogate with a discrete finite-volume residual; teacher is the fast SWELL solver','training_net_rain_mm_h':train_rates.tolist(),'heldout_net_rain_mm_h':test_rates.tolist(),'heldout_teacher_mae_m':mae,'uniform_baseline_mae_m':uniform,'max_mean_depth_mass_error_m':mass,'heldout_mean_step_residual_m':max(res),'epochs':epochs,'eligible_for_research_review':bool(mae<uniform and mass<1e-6 and max(res)<.001),'field_validated':False,'operational_deployment':False,'weights_sha256':hashlib.sha256(weights.read_bytes()).hexdigest(),'limitations':'Same DEM only, net uniform rain 5–100 mm/h, dry start, closed domain, duration <=1h, no drains, no spatial infiltration or external inflow. Held-out simulation scenarios, not independent measurements. No use for construction, warnings or real-world forecasts.'};(out/'model-card.json').write_text(json.dumps(report,indent=2));return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--site',required=True);p.add_argument('--root',default=str(Path(__file__).parent/'site'));p.add_argument('--out',default='research-ai');p.add_argument('--epochs',type=int,default=100);a=p.parse_args();print(json.dumps(train(a.root,a.site,a.out,a.epochs),indent=2))
