# services/qc/get.py
"""
Gravity Error Test (GET) – Ekseth et al. 2006, Appendix 1 A
-----------------------------------------------------------
Adds a geometry-quality warning when the test is run outside its
high-discriminatory zone (≈ 10° ≤ I ≤ 80°).

Inputs
------
survey               – dict with accelerometer_x/y/z, inclination, toolface
ipm_data             – raw IPM text *or* a parsed IPMFile instance
theoretical_gravity  – local gravity [g-units].  If None, falls back to
                       survey['expected_gravity'].

Output
------
QCResult.serialised dict
"""
import math
from src.models.qc_result import QCResult
from src.utils.ipm_parser import parse_ipm_file
from src.utils.tolerance import get_error_term_value
from src.utils.ipm_cache import get_ipm


# advisory thresholds (deg)
INC_WARN_LOW  = 10.0
INC_WARN_HIGH = 80.0


# --------------------------------------------------------------------------- #
#  Public API
# --------------------------------------------------------------------------- #
def perform_get(survey: dict, ipm_data, theoretical_gravity: float):
    # ---------- required sensor data --------------------------------------- #
    acc_x = survey["accelerometer_x"]
    acc_y = survey["accelerometer_y"]
    acc_z = survey["accelerometer_z"]
    inc   = survey["inclination"]          # deg
    tf    = survey["toolface"]             # deg

    measured_g = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)

    g_theoretical = theoretical_gravity or survey.get("expected_gravity")
    if g_theoretical is None:
        raise ValueError("GET needs 'expected_gravity' or explicit argument.")

    g_error = measured_g - g_theoretical
    tol, debug_ipm_terms = _get_tolerance(ipm_data, inc, tf, g_theoretical)
    is_ok = abs(g_error) <= tol

    # ---------- QCResult ---------------------------------------------------- #
    res = QCResult("GET")
    (res.set_validity(is_ok)
        .add_measurement("gravity", measured_g)
        .add_theoretical("gravity", g_theoretical)
        .add_error("gravity", g_error)
        .add_tolerance("gravity", tol)
        .add_detail("inclination", inc)
        .add_detail("toolface", tf)
        .add_detail("weighting_functions", _weighting_functions(inc, tf))
        .add_detail("debug_ipm_terms", debug_ipm_terms))  # Add debug info to response

    if inc < INC_WARN_LOW or inc > INC_WARN_HIGH:
        _add_warning(
            res, "weak_geometry",
            f"GET discriminatory power is reduced at inclination {inc:.1f}° "
            "(Ekseth 2006 App. 2 A)"
        )

    return res.to_dict()


# --------------------------------------------------------------------------- #
#  Internals
# --------------------------------------------------------------------------- #
def _weighting_functions(inclination_deg: float, toolface_deg: float):
    I = math.radians(inclination_deg)
    T = math.radians(toolface_deg)
    return {
        "wx": math.sin(I) * math.sin(T),
        "wy": math.sin(I) * math.cos(T),
        "wz": math.cos(I),
    }


def _get_error_term_value(ipm, name, vector="", tie_on=""):
    """Return the error-term value (1 σ). 0.0 if term absent."""
    term = ipm.get_error_term(name, vector, tie_on)
    return term["value"] if term else 0.0


def _get_tolerance(ipm_data, inc_deg: float, tf_deg: float, gt: float) -> float:
    """3-σ gravity-error tolerance δG (Eq. 3, Appendix 1 A)."""
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    w = _weighting_functions(inc_deg, tf_deg)

    # Debug collection - store found error terms
    debug_terms = {}
    
    # 1-σ sigmas
    abx = _get_error_term_value(ipm, "ABXY-TI1S", "e", "s")
    debug_terms["ABXY-TI1S (e,s) - X axis bias"] = abx
    
    aby = _get_error_term_value(ipm, "ABXY-TI1S", "e", "s")
    debug_terms["ABXY-TI1S (e,s) - Y axis bias"] = aby
    
    abz = _get_error_term_value(ipm, "ABZ", "e", "s")
    debug_terms["ABZ (e,s) - Z axis bias"] = abz

    asx = _get_error_term_value(ipm, "ASXY-TI1S", "e", "s")
    debug_terms["ASXY-TI1S (e,s) - X axis scale"] = asx
    
    asy = _get_error_term_value(ipm, "ASXY-TI1S", "e", "s")
    debug_terms["ASXY-TI1S (e,s) - Y axis scale"] = asy
    
    asz = _get_error_term_value(ipm, "ASZ", "e", "s")
    debug_terms["ASZ (e,s) - Z axis scale"] = asz

    var = (
        (abx * w["wx"])**2 +
        (aby * w["wy"])**2 +
        (abz * w["wz"])**2 +
        (2 * asx * w["wx"] * gt)**2 +
        (2 * asy * w["wy"] * gt)**2 +
        (2 * asz * w["wz"] * gt)**2
    )
    
    # Calculate weighted contribution of each term for debugging
    debug_terms["weighted_contributions"] = {
        "abx": (abx * w["wx"])**2,
        "aby": (aby * w["wy"])**2,
        "abz": (abz * w["wz"])**2,
        "asx": (2 * asx * w["wx"] * gt)**2,
        "asy": (2 * asy * w["wy"] * gt)**2,
        "asz": (2 * asz * w["wz"] * gt)**2
    }
    
    tolerance = 3.0 * math.sqrt(var)
    return tolerance, debug_terms

def _add_warning(res: QCResult, code: str, msg: str):
    warn = res.details.get("warnings", [])
    warn.append({"code": code, "message": msg})
    res.add_detail("warnings", warn)