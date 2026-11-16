"""Experimental conservative 2D Saint-Venant solver: first-order hydrostatic reconstruction,
local Lax-Friedrichs (Rusanov) flux, adaptive CFL, reflective external boundary.
Research screening only: no inundation field validation, culverts or river inflow.
"""
import numpy as np
G=9.80665
EPS=1e-8

def velocity(q,h):return np.divide(q,h,out=np.zeros_like(q),where=h>EPS)

def faces(h0,m0,n0,z0,h1,m1,n1,z1):
    # In normal/tangential coordinates. Hydrostatic reconstruction preserves lake-at-rest.
    bed=np.maximum(z0,z1);a=np.maximum(0,h0+z0-bed);b=np.maximum(0,h1+z1-bed)
    u=velocity(m0,h0);v=velocity(m1,h1);t=velocity(n0,h0);w=velocity(n1,h1)
    qa=a*u;qb=b*v;ta=a*t;tb=b*w
    speed=np.maximum(abs(u)+np.sqrt(G*a),abs(v)+np.sqrt(G*b))
    hf=.5*(qa+qb-speed*(b-a));mf=.5*(qa*u+.5*G*a*a+qb*v+.5*G*b*b-speed*(qb-qa));tf=.5*(qa*t+qb*w-speed*(tb-ta))
    return hf,mf+.5*G*(h0*h0-a*a),mf+.5*G*(h1*h1-b*b),tf

def step(z,h,mx,my,dx,dt):
    # Reflect wall-normal momentum; tangential momentum unchanged.
    def axis(h,m,n,z):
        H=np.pad(h,((0,0),(1,1)),mode='edge');M=np.pad(m,((0,0),(1,1)),mode='edge');N=np.pad(n,((0,0),(1,1)),mode='edge');Z=np.pad(z,((0,0),(1,1)),mode='edge');M[:,0]*=-1;M[:,-1]*=-1
        f,l,r,t=faces(H[:,:-1],M[:,:-1],N[:,:-1],Z[:,:-1],H[:,1:],M[:,1:],N[:,1:],Z[:,1:]);return f[:,1:]-f[:,:-1],l[:,1:]-r[:,:-1],t[:,1:]-t[:,:-1]
    hx,xx,yx=axis(h,mx,my,z);hy,yy,xy=axis(h.T,my.T,mx.T,z.T);return h-dt/dx*(hx+hy.T),mx-dt/dx*(xx+xy.T),my-dt/dx*(yx+yy.T)

def simulate(z,dx,rain,capacity,drain,roughness=.04,suction_deficit_m=0.,dt=30.,outlet=None,initial_depth=None):
    z=np.asarray(z,float);h=np.zeros_like(z) if initial_depth is None else np.asarray(initial_depth,float).copy();mx=np.zeros_like(z);my=mx.copy();cap=np.broadcast_to(capacity,z.shape);dr=np.broadcast_to(drain,z.shape);area=dx*dx;rain=np.asarray(rain,float)
    if outlet is not None or suction_deficit_m!=0:raise ValueError('Momentum solver currently supports reflective boundaries and constant infiltration only; use diffusive solver for surveyed outlet or Green-Ampt.')
    if z.size*len(rain)>30000:raise ValueError('Momentum solver budget: at most 30,000 cell-hours; reduce area or event duration')
    if h.shape!=z.shape or not all(np.isfinite(x).all() for x in (z,h,cap,dr,rain)) or min(dx,roughness,dt)<=0 or any(np.any(x<0) for x in (h,cap,dr,rain)):raise ValueError('Invalid shallow-water input')
    initial=float(h.sum()*area);total=inf=removed=0.;peak=h.copy();frames=[];mass=[];steps=0;min_dt=dt
    for r in rain:
        elapsed=0.
        while elapsed<3600-1e-9:
            u=velocity(mx,h);v=velocity(my,h);c=np.sqrt(G*h);den=float(np.max(abs(u)+abs(v)+2*c));delta=min(dt,3600-elapsed,.35*dx/max(den,.1))
            if delta<.001 or steps>=100000:raise ArithmeticError('CFL timestep/work budget exceeded; refine domain or use screening solver')
            # Flux step first; source update afterwards prevents CFL from ignoring just-added water.
            h,mx,my=step(z,h,mx,my,dx,delta)
            if np.min(h)<-1e-9 or not all(np.isfinite(x).all() for x in (h,mx,my)):raise ArithmeticError('Momentum solver positivity/stability check failed')
            h=np.maximum(0,h);u=velocity(mx,h);v=velocity(my,h);add=float(r)*delta/3600000;h+=add;total+=add*h.size*area
            take=np.minimum(h,cap*delta/3600000);old=h.copy();h-=take;inf+=float(take.sum()*area);take=np.minimum(h,dr*delta/3600000);h-=take;removed+=float(take.sum()*area);ratio=np.divide(h,old,out=np.zeros_like(h),where=old>EPS);mx*=ratio;my*=ratio
            # Semi-implicit Manning drag on unit-width discharge. Dry cells have zero momentum.
            speed=np.hypot(velocity(mx,h),velocity(my,h));friction=1+delta*G*roughness**2*speed/np.maximum(h,EPS)**(4/3);mx=np.where(h>EPS,mx/friction,0);my=np.where(h>EPS,my/friction,0)
            peak=np.maximum(peak,h);elapsed+=delta;min_dt=min(min_dt,delta);steps+=1
        stored=float(h.sum()*area);err=initial+total-inf-removed-stored
        if abs(err)>max(1e-5,(initial+total)*1e-8):raise ArithmeticError('Shallow-water conservation check failed')
        frames.append(h.copy());mass.append({'rain_m3':total,'infiltrated_m3':inf,'drained_m3':removed,'boundary_outflow_m3':0.,'stored_m3':stored,'balance_error_m3':err,'max_depth_m':float(h.max()),'wet_area_m2':float((h>=.05).sum()*area),'limited_face_fraction':0.,'adaptive_min_dt_s':min_dt,'steps':steps,'max_speed_m_s':float(np.hypot(velocity(mx,h),velocity(my,h)).max())})
    return np.array(frames),peak,mass
