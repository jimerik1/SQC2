# …/stages/04_geomagnetic.py
from typing import List
from models.survey import Survey

def apply(surveys: List[Survey], ctx: dict) -> List[Survey]:
    dec_corr = ctx.get("declination_correction_deg")
    if dec_corr is None:
        return surveys

    out=[]
    for sv in surveys:
        if sv.expected_geomagnetic_field:
            sv.expected_geomagnetic_field["declination"] += dec_corr
        out.append(sv)
    return out