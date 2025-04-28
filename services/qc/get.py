# services/qc/get.py
"""
Gravity Error Test (GET) – Ekseth et al. 2006, Appendix 1 A

Adds a geometry-quality warning when the test is run outside its high-discriminatory
zone (≈ 10° ≤ I ≤ 80°).  The test still returns pass/fail, but `details.warnings`
will contain an entry with code 'weak_geometry'.
"""
import math
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

# --- advisory thresholds (deg) ------------------------------------------------
INC_WARN_LOW  = 10.0   # below this → near-vertical   (weak GET)
INC_WARN_HIGH = 80.0   # above this → near-horizontal (weak GET)


# --------------------------------------------------------------------------- #
#  Public driver
# --------------------------------------------------------------------------- #
def perform_get(survey: dict, ipm_data, theoretical_gravity: float):
    """
    Gravity Error Test for a single station.

    Parameters
    ----------
    survey : dict   – must include accelerometer components, inclination, toolface
    ipm_data        – raw IPM string or parsed IPMFile
    theoretical_gravity : float
        Local gravity [g-units] supplied by caller.  If both this argument and
        survey['expected_gravity'] are present, the explicit argument wins.

    Returns
    -------
    dict – QCResult.to_dict()
    """
    # ----- required sensor data --------------------------------------------- #
    acc_x = survey["accelerometer_x"]
    acc_y = survey["accelerometer_y"]
    acc_z = survey["accelerometer_z"]
    inc   = survey["inclination"]    # deg
    tf    = survey["toolface"]       # deg

    # ----- measured quantity ------------------------------------------------- #
    measured_g = math.sqrt(acc_x ** 2 + acc_y ** 2 + acc_z ** 2)

    # explicit argument overrides survey field (avoids silent mismatch)
    g_theoretical = theoretical_gravity or survey.get("expected_gravity")
    if g_theoretical is None:
        raise ValueError("GET requires 'expected_gravity' or explicit argument.")

    g_error = measured_g - g_theoretical

    tol = _get_tolerance(ipm_data, inc, tf, g_theoretical)
    is_valid = abs(g_error) <= tol

    # ----- build QCResult ---------------------------------------------------- #
    res = QCResult("GET")
    res.set_validity(is_valid)
    res.add_measurement("gravity", measured_g)
    res.add_theoretical("gravity", g_theoretical)
    res.add_error("gravity", g_error)
    res.add_tolerance("gravity", tol)
    res.add_detail("inclination", inc)
    res.add_detail("toolface", tf)
    res.add_detail("weighting_functions", _weighting_functions(inc, tf))

    # ----- geometry advisory ------------------------------------------------- #
    if inc < INC_WARN_LOW or inc > INC_WARN_HIGH:
        _add_warning(
            res,
            "weak_geometry",
            f"GET discriminating power is reduced at inclination {inc:.1f}°. "
            "See Ekseth 2006 Appendix 2 A."
        )
    return res.to_dict()


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _weighting_functions(inclination: float, toolface: float):
    """Return weighting-function dict (wx, wy, wz)."""
    I = math.radians(inclination)
    T = math.radians(toolface)
    wx = math.sin(I) * math.sin(T)
    wy = math.sin(I) * math.cos(T)
    wz = math.cos(I)
    return {"wx": wx, "wy": wy, "wz": wz}


def _get_tolerance(ipm_data, inclination: float, toolface: float, gt: float) -> float:
    """3-σ tolerance δG (Eq. 3 in paper)."""
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    w = _weighting_functions(inclination, toolface)

    # 1-σ sigmas
    abx = get_error_term_value(ipm, "ABXY-TI1S", "e", "s")
    aby = get_error_term_value(ipm, "ABXY-TI1S", "e", "s")
    abz = get_error_term_value(ipm, "ABZ",        "e", "s")

    asx = get_error_term_value(ipm, "ASXY-TI1S", "e", "s")
    asy = get_error_term_value(ipm, "ASXY-TI1S", "e", "s")
    asz = get_error_term_value(ipm, "ASZ",        "e", "s")

    var = (
        (abx * w["wx"]) ** 2 +
        (aby * w["wy"]) ** 2 +
        (abz * w["wz"]) ** 2 +
        (2 * asx * w["wx"] * gt) ** 2 +
        (2 * asy * w["wy"] * gt) ** 2 +
        (2 * asz * w["wz"] * gt) ** 2
    )
    return 3.0 * math.sqrt(var)


def _add_warning(res: QCResult, code: str, msg: str):
    """Attach a warning dict to QCResult.details."""
    warnings = res.details.get("warnings", [])
    warnings.append({"code": code, "message": msg})
    res.add_detail("warnings", warnings)