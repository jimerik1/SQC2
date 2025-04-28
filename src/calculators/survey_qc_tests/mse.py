# services/qc/mse.py
import math, numpy as np
from src.models.qc_result import QCResult
from src.utils.ipm_parser import parse_ipm_file
from src.utils.tolerance import get_error_term_value
from src.utils.linalg import safe_inverse


# --------------------------------------------------------------------------- #
def perform_mse(surveys, ipm_data):
    """
    Multi-Station Estimation (MSE) – simultaneously solves station angles and
    systematic sensor errors.  Caller *must* embed:
        expected_geomagnetic_field = { total_field [nT], dip [deg] }
        expected_gravity           = g-units (≈1.0)
    """
    if len(surveys) < 10:
        return _fail("At least 10 survey stations are required for MSE")

    incs = [s['inclination'] for s in surveys]
    azis = [s['azimuth']     for s in surveys]
    tfs  = [s['toolface']    for s in surveys]
    inc_var = max(incs) - min(incs)
    azi_var = max(abs((a1-a2+180)%360-180) for a1 in azis for a2 in azis)

    quad_hits = [0,0,0,0]
    for d in tfs: quad_hits[int(d//90)%4]+=1
    q_cnt = sum(1 for q in quad_hits if q)

    geom = ("excellent" if inc_var>45 and azi_var>45 and q_cnt>=4 else
            "good"      if inc_var>30 and azi_var>30 and q_cnt>=3 else
            "fair"      if inc_var>15 and azi_var>15 and q_cnt>=2 else
            "poor")
    if geom=="poor":
        return _fail("Survey geometry insufficient for reliable MSE",
                     extra={'inclination_variation':inc_var,
                            'azimuth_variation':azi_var,
                            'quadrant_distribution':quad_hits})

    if   geom=="excellent":
        pnames=['MBX','MBY','MBZ','MSX','MSY','MSZ','ABX','ABY','ABZ','ASX','ASY']
    elif geom=="good":
        pnames=['MBX','MBY','MBZ','MSX','MSY','ABX','ABY']
    else:
        pnames=['MBX','MBY','ABX','ABY']

    ns, np_ = len(surveys), len(pnames)

    # measurement vector (Bx,By,Bz,Gx,Gy,Gz) per station
    y=np.zeros(ns*6)
    for i,s in enumerate(surveys):
        y[i*6+0:i*6+3]=[s['mag_x'],s['mag_y'],s['mag_z']]
        y[i*6+3:i*6+6]=[s['accelerometer_x'],s['accelerometer_y'],s['accelerometer_z']]

    # parameter vector: 3*ns station angles + np_ error terms
    x=np.zeros(ns*3+np_)
    for i,s in enumerate(surveys):
        x[i*3:i*3+3]=np.radians([s['inclination'],s['azimuth'],s['toolface']])

    geo=[s['expected_geomagnetic_field'] for s in surveys]
    grav=[s['expected_gravity']          for s in surveys]

    ipm=parse_ipm_file(ipm_data) if isinstance(ipm_data,str) else ipm_data

    # ---- Gauss-Newton -------------------------------------------------------
    for it in range(20):
        ypred=_predict(x,geo,grav,ns,pnames)
        res=y-ypred
        J  =_jacobian(x,geo,grav,ns,pnames)
        try:
            dx=np.linalg.solve(J.T@J+1e-6*np.eye(J.shape[1]),J.T@res)
        except np.linalg.LinAlgError:
            return _fail("Normal matrix singular – geometry too weak")
        x+=dx
        if np.linalg.norm(dx)<1e-6: break
    converged=it<19

    JTJ=J.T@J+1e-6*np.eye(J.shape[1])
    
    # robust inverse
    try:
        cov = safe_inverse(JTJ, ridge=1e-6)     
    except np.linalg.LinAlgError as exc:
        return _fail(str(exc))                   # abort with a clear message
        
    err_cov=cov[-np_:,-np_:]
    err_std=np.sqrt(np.diag(err_cov))
    corr=err_cov/np.sqrt(np.outer(err_std,err_std))
    max_corr=np.nanmax(np.abs(corr-np.eye(np_)))

    # tolerances
    tol={n:3*get_error_term_value(ipm,n,'e','s') for n in pnames}
    err_vals=x[-np_:]

    ep_out={}
    for val,std,name in zip(err_vals,err_std,pnames):
        t=abs(val/std) if std and not np.isnan(std) else float('nan')
        ep_out[name]={
            'value':float(val),'std_dev':float(std),
            't_statistic':float(t),
            'significant': False if np.isnan(t) else t>2,
            'within_tolerance':True if tol[name] is None else abs(val)<=tol[name]
        }

    ok_params=all(v['within_tolerance'] for v in ep_out.values() if not np.isnan(v['std_dev']))
    valid=converged and ok_params and max_corr<=0.4

    corrected=[]
    for i in range(ns):
        inc,az,tf=np.degrees(x[i*3:i*3+3])%360
        corrected.append({**surveys[i],
            'inclination':inc,'azimuth':az,'toolface':tf})

    out=QCResult("MSE").to_dict()  # simple wrapper for uniformity
    out.update({
        'is_valid':valid,
        'error_parameters':ep_out,
        'corrected_surveys':corrected,
        'correlations':corr.tolist(),
        'statistics':{
            'max_correlation':float(max_corr),
            'converged':converged,
            'iterations':it+1,
            'final_residual_norm':float(np.linalg.norm(res))
        },
        'details':{
            'geometry_quality':geom,
            'inclination_variation':inc_var,
            'azimuth_variation':azi_var,
            'quadrant_distribution':quad_hits
        }
    })
    if not valid:
        if max_corr>0.4: out['details']['failure_reason']="High parameter correlations"
        elif not ok_params: out['details']['failure_reason']="Error parameter outside tolerance"
        else: out['details']['failure_reason']="Estimation did not converge"
    return out


# --------------------------------------------------------------------------- #
#  helpers
# --------------------------------------------------------------------------- #
def _predict(x, geo, grav, ns, pnames):
    """Return 6·ns vector of predicted sensor outputs."""
    y=np.zeros(ns*6); err={n:x[ns*3+i] for i,n in enumerate(pnames)}
    g_get=lambda n:err.get(n,0.0)
    for i in range(ns):
        inc,az,tf=x[i*3:i*3+3]
        Bt=geo[i]['total_field']; dip=math.radians(geo[i]['dip']); g=grav[i]

        bx_ideal = Bt*(math.sin(inc)*math.cos(az)*math.cos(dip)-math.sin(dip)*math.sin(az))
        by_ideal = Bt*(math.sin(inc)*math.sin(az)*math.cos(dip)+math.sin(dip)*math.cos(az))
        bz_ideal = Bt*(math.cos(inc)*math.cos(dip)+math.sin(inc)*math.sin(dip))
        gx_ideal = math.sin(inc)*math.sin(tf)
        gy_ideal = math.sin(inc)*math.cos(tf)
        gz_ideal = math.cos(inc)

        bx=bx_ideal*(1+g_get('MSX')*Bt*2)+g_get('MBX')
        by=by_ideal*(1+g_get('MSY')*Bt*2)+g_get('MBY')
        bz=bz_ideal*(1+g_get('MSZ')*Bt*2)+g_get('MBZ')
        gx=gx_ideal*(1+g_get('ASX')*g*2)+g_get('ABX')
        gy=gy_ideal*(1+g_get('ASY')*g*2)+g_get('ABY')
        gz=gz_ideal*(1+g_get('ASZ')*g*2)+g_get('ABZ')

        y[i*6:i*6+6]=[bx,by,bz,gx,gy,gz]
    return y

def _jacobian(x,geo,grav,ns,pnames):
    """Finite-difference Jacobian."""
    h=1e-6; y0=_predict(x,geo,grav,ns,pnames)
    J=np.zeros((ns*6,len(x)))
    for j in range(len(x)):
        xp=x.copy(); xp[j]+=h
        J[:,j]=(_predict(xp,geo,grav,ns,pnames)-y0)/h
    return J

def _fail(msg,extra=None):
    res={'is_valid':False,'error':msg}
    if extra: res['details']=extra
    return res