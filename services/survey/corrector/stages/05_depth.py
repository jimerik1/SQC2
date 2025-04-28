# …/stages/05_depth.py
from typing import List
from models.survey import Survey
import math

def apply(surveys: List[Survey], ctx: dict) -> List[Survey]:
    dd = ctx.get("dddt_params")
    if not dd:
        return surveys
    dref = dd.get("DREF", 0); dsf = dd.get("DSF", 0); dst = dd.get("DST", 0)
    out=[]
    for sv in surveys:
        sv.depth = sv.depth - dref - dsf*sv.depth - dst*sv.depth*math.cos(math.radians(sv.inclination))
        out.append(sv)
    return out