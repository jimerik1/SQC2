# …/stages/01_ipm_sensor.py
from typing import List
from models.survey import Survey
from utils.ipm_parser import parse_ipm_file

_BIAS_TERMS  = ["ABX","ABY","ABZ","MBX","MBY","MBZ","GBX","GBY"]
_SCALE_TERMS = ["ASX","ASY","ASZ","MSX","MSY","MSZ"]

def _value(ipm, name, default=0.0):
    term = ipm.get_error_term(name, "e", "s")
    return term["value"] if term else default

def apply(surveys: List[Survey], ctx: dict) -> List[Survey]:
    ipm = ctx.get("ipm")
    if not ipm:
        raw = ctx.get("ipm_content")
        if raw: ipm = parse_ipm_file(raw)
        else:   return surveys

    g_std = 9.80665
    out = []
    for sv in surveys:
        s = Survey(sv.to_dict())  # deep-copy

        # Bias corrections
        s.Gx -= _value(ipm,"ABX");  s.Gy -= _value(ipm,"ABY");  s.Gz -= _value(ipm,"ABZ")
        s.Bx -= _value(ipm,"MBX");  s.By -= _value(ipm,"MBY");  s.Bz -= _value(ipm,"MBZ")
        s.gyro_x -= _value(ipm,"GBX"); s.gyro_y -= _value(ipm,"GBY")

        # Scale corrections (accelerometers use g, magnetometers use Bt)
        asx = _value(ipm,"ASX"); asy = _value(ipm,"ASY"); asz = _value(ipm,"ASZ")
        if g_std:
            s.Gx /= (1 + asx * g_std)
            s.Gy /= (1 + asy * g_std)
            s.Gz /= (1 + asz * g_std)

        msx = _value(ipm,"MSX"); msy=_value(ipm,"MSY"); msz=_value(ipm,"MSZ")
        Bt  = getattr(sv.expected_geomagnetic_field or {}, "total_field", 0)  # nT
        if Bt:
            s.Bx /= (1 + msx * Bt)
            s.By /= (1 + msy * Bt)
            s.Bz /= (1 + msz * Bt)

        out.append(s)
    return out