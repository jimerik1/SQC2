# …/stages/03_sag_misalignment.py
import math, numpy as np
from typing import List
from src.models.survey import Survey

def _rot_x(theta):  # theta rad
    c,s = math.cos(theta), math.sin(theta)
    return np.array([[1,0,0],[0,c,-s],[0,s,c]])
def _rot_y(theta):
    c,s = math.cos(theta), math.sin(theta)
    return np.array([[c,0,s],[0,1,0],[-s,0,c]])

def apply(surveys: List[Survey], ctx: dict) -> List[Survey]:
    mx = math.radians(ctx.get("rsmt_params", {}).get("MX", 0))
    my = math.radians(ctx.get("rsmt_params", {}).get("MY", 0))
    if not (mx or my):
        return surveys

    R = _rot_y(my) @ _rot_x(mx)  # apply X then Y
    out=[]
    for sv in surveys:
        v = np.array([sv.Gx, sv.Gy, sv.Gz])
        sv.Gx, sv.Gy, sv.Gz = (R @ v).tolist()
        out.append(sv)
    return out