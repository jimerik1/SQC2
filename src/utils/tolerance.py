# src/utils/tolerance.py   (or wherever the helper lives)
import math

def get_error_term_value(ipm_data,
                         term_name,
                         vector="e",
                         tie_on="s",
                         default=0.0,
                         *,
                         inc_deg=None,
                         az_deg=None,
                         dip_deg=None,
                         mtot=None,          # total magnetic field (nT) – TFDT
                         gtot=None):         # total gravity (m/s²) – GET
    """
    Return the 1‑σ value for an IPM error term, evaluating its Formula if present.

    Parameters
    ----------
    ipm_data   : str | IPMFile
    term_name  : base name (e.g. 'MBX', 'ABXY-TI1S')
    vector     : 'e', 'i', 'a'  (error vector code)
    tie_on     : 's', 'g', 'r'  (systematic, global, random …)
    default    : value to return if term not found
    inc_deg    : station inclination  (optional)
    az_deg     : station azimuth      (optional)
    dip_deg    : local magnetic dip   (optional)
    mtot       : total magnetic field (nT)  – for formulas using mtot
    gtot       : total gravity        (m/s²) – for formulas using gtot
    """

    # --- ensure we have an IPMFile object ---------------------------------
    if isinstance(ipm_data, str):
        from .ipm_parser import parse_ipm_file
        ipm_data = parse_ipm_file(ipm_data)

    # --- try common name variants ----------------------------------------
    variants = {
        term_name,
        term_name.upper(),
        term_name.lower(),
        term_name.replace('-', '_'),
        term_name.replace('_', '-')
    }

    # ABXY-TI1S ↔ ABXY_TI1S shorthand
    if "-TI" in term_name:
        base = term_name.split("-TI")[0]
        variants.update({f"{base}_TI1S", f"{base}_TI1"})

    for name in variants:
        term = ipm_data.get_error_term(name, vector, tie_on)
        if not term:
            continue

        sigma = term.get("value", 0.0)
        formula = (term.get("formula") or "").strip()

        # ---------- evaluate Formula, if any ------------------------------
        if formula:
            env = {
                # geometry (radians)
                "inc": math.radians(inc_deg) if inc_deg is not None else 0.0,
                "azm": math.radians(az_deg) if az_deg is not None else 0.0,
                "dip": math.radians(dip_deg) if dip_deg is not None else 0.0,
                # totals
                "mtot": mtot or 1.0,
                "gtot": gtot or 9.80665,
                # safe math
                "sin": math.sin, "cos": math.cos, "tan": math.tan,
                "sqrt": math.sqrt, "abs": abs
            }
            try:
                factor = abs(eval(formula, {"__builtins__": None}, env))
                sigma *= factor
            except Exception:
                # leave sigma as-is if eval fails
                pass

        return sigma

    # -------- not found anywhere -----------------------------------------
    return default