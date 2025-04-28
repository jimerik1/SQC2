# …/stages/02_multistation.py
from typing import List
from models.survey import Survey

_MS_KEYS = {"msat_params","msgt_params","msmt_params"}  # put these in ctx

def apply(surveys: List[Survey], ctx: dict) -> List[Survey]:
    params = {}
    for k in _MS_KEYS:
        params.update(ctx.get(k, {}))
    if not params:
        return surveys

    g_std = 9.80665
    out = []
    for sv in surveys:
        s = Survey(sv.to_dict())
        # accelerometer
        if "ABX" in params: s.Gx -= params["ABX"]
        if "ABY" in params: s.Gy -= params["ABY"]
        if "ABZ" in params: s.Gz -= params["ABZ"]
        if "ASX" in params: s.Gx /= (1 + params["ASX"] * g_std)
        if "ASY" in params: s.Gy /= (1 + params["ASY"] * g_std)
        if "ASZ" in params: s.Gz /= (1 + params["ASZ"] * g_std)
        # magnetometer
        Bt = getattr(sv.expected_geomagnetic_field or {}, "total_field", 0)
        if Bt:
            for axis,prefix in (("Bx","M"),("By","M"),("Bz","M")):
                b = params.get(f"{prefix}{axis[-1].upper()}"); s.__dict__[axis] -= b or 0
            for axis,prefix in (("Bx","MS"),("By","MS"),("Bz","MS")):
                sf = params.get(f"{prefix}{axis[-1].upper()}"); 
                if sf: s.__dict__[axis] /= (1 + sf * Bt*2)
        # gyro
        if "GBX*" in params: s.gyro_x -= params["GBX*"]
        if "GBY*" in params: s.gyro_y -= params["GBY*"]
        out.append(s)
    return out