# services/qc/get.py
"""
Gravity Error Test (GET) – Ekseth et al. 2006, Appendix 1 A
-----------------------------------------------------------
Adds a geometry-quality warning when the test is run outside its
high-discriminatory zone (≈ 10° ≤ I ≤ 80°).

Inputs
------
survey               – dict with accelerometer_x/y/z, inclination (optional), toolface (optional)
ipm_data             – raw IPM text *or* a parsed IPMFile instance
theoretical_gravity  – local gravity [m/s2].  Sourced externally by gravity field models like EGM2008

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

# Define optimal toolface ranges
TF_OPTIMAL = [(45, 15), (135, 15), (225, 15), (315, 15)]  # (center, +/- range)


# --------------------------------------------------------------------------- #
#  Public API
# --------------------------------------------------------------------------- #
def perform_get(survey: dict, ipm_data, theoretical_gravity: float, sigma: float = 3.0):
    # ---------- required sensor data --------------------------------------- #
    acc_x = survey["accelerometer_x"] # m/s²
    acc_y = survey["accelerometer_y"] # m/s²
    acc_z = survey["accelerometer_z"] # m/s²
    
    # Calculate gravity magnitude
    measured_g = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)  # m/s²
    
    # Calculate inclination from accelerometer readings
    calc_inc = math.degrees(math.acos(min(max(acc_z / measured_g, -1.0), 1.0)))
    
    # Calculate toolface from accelerometer readings (if inclination is sufficient)
    if calc_inc >= 10.0 and calc_inc <= 170.0:  # Not too close to vertical
        calc_tf = math.degrees(math.atan2(acc_y, acc_x))
        # Convert to 0-360 range
        calc_tf = (calc_tf + 360) % 360
    else:
        # Toolface is undefined in near-vertical wells
        calc_tf = None  # Use None instead of 0 to indicate undefined
    
    # Use calculated values or provided values for internal calculations
    inc = survey.get("inclination", calc_inc)
    tf = survey.get("toolface", calc_tf)
    
    # Check for inclination discrepancy if provided
    inc_discrepancy = None
    if "inclination" in survey:
        inc_discrepancy = abs(survey["inclination"] - calc_inc)
    
    # Check for toolface discrepancy if provided
    tf_discrepancy = None
    if "toolface" in survey:
        # Account for circular nature of angles (e.g., 359° vs 1°)
        tf_diff = abs((survey["toolface"] % 360) - (calc_tf % 360))
        tf_discrepancy = min(tf_diff, 360 - tf_diff)

    g_theoretical = theoretical_gravity or survey.get("expected_gravity")

    if g_theoretical is None:
        raise ValueError("GET needs 'expected_gravity' in m/s² or explicit argument.")


    g_error = measured_g - g_theoretical
    tol, debug_ipm_terms = _get_tolerance(ipm_data, inc, tf, g_theoretical, sigma)
    is_ok = abs(g_error) <= tol

    # ---------- QCResult ---------------------------------------------------- #
    res = QCResult("GET")
    (res.set_validity(is_ok)
        .add_measurement("gravity", measured_g)
        .add_theoretical("gravity", g_theoretical)
        .add_error("gravity", g_error)
        .add_tolerance("gravity", tol)
        .add_detail("calculated_inclination", calc_inc)
        .add_detail("calculated_toolface", calc_tf)
        .add_detail("weighting_functions", _weighting_functions(inc, tf))
        .add_detail("debug_ipm_terms", debug_ipm_terms))  # Add debug info to response
    
    # Add provided values if they exist
    if "inclination" in survey:
        res.add_detail("provided_inclination", survey["inclination"])
    
    if "toolface" in survey:
        res.add_detail("provided_toolface", survey["toolface"])
    
    # Add angle discrepancy warnings if needed
    if inc_discrepancy is not None and inc_discrepancy > 0.5:  # Half a degree threshold
        _add_warning(
            res, "inclination_discrepancy",
            f"Provided inclination ({survey['inclination']:.2f}°) differs from calculated ({calc_inc:.2f}°) by {inc_discrepancy:.2f}°"
        )
    
    if tf_discrepancy is not None and tf_discrepancy > 2.0:  # 2 degree threshold for toolface
        _add_warning(
            res, "toolface_discrepancy",
            f"Provided toolface ({survey['toolface']:.2f}°) differs from calculated ({calc_tf:.2f}°) by {tf_discrepancy:.2f}°"
        )

    # Check inclination range
    if calc_inc < INC_WARN_LOW or calc_inc > INC_WARN_HIGH:
        _add_warning(
            res, "weak_geometry",
            f"GET discriminatory power is reduced at inclination {calc_inc:.1f}° "
            "(Ekseth 2006 App. 2 A)"
        )
    
    # Check toolface optimization (only if toolface is defined)
    if calc_tf is not None:
        is_optimal_tf = False
        for center, range_val in TF_OPTIMAL:
            tf_diff = min(abs((calc_tf % 360) - center), abs(360 - abs((calc_tf % 360) - center)))
            if tf_diff <= range_val:
                is_optimal_tf = True
                break
                
        if not is_optimal_tf:
            _add_warning(
                res, "suboptimal_toolface",
                f"GET effectiveness is reduced at toolface {calc_tf:.1f}°. Optimal values are near 45°, 135°, 225°, or 315° "
                "(Ekseth 2006)"
            )
    else:
        # Add warning about undefined toolface
        _add_warning(
            res, "undefined_toolface",
            f"Toolface is undefined at inclination {calc_inc:.1f}° (below 10° threshold)"
        )
    
    # Check for cardinal azimuth if available
    if "azimuth" in survey:
        az = survey["azimuth"]
        if (abs(az % 180) < 10) or (abs((az % 180) - 90) < 10):
            _add_warning(
                res, "cardinal_direction",
                f"GET reliability may be reduced in wells running near cardinal directions (azimuth {az:.1f}°)"
            )
    
    # Combined geometry warning
    if abs(calc_inc - 45) > 15 and not is_optimal_tf:
        _add_warning(
            res, "suboptimal_geometry",
            f"GET has reduced discriminatory power at this combination of inclination ({calc_inc:.1f}°) and toolface ({calc_tf:.1f}°)"
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


def _get_error_term_value(ipm, name, vec, tie_on, inc_deg=None,
                          az_deg=None, gt=None):
    term = ipm.get_error_term(name, vec, tie_on)
    if not term:
        return 0.0

    sigma = term["value"]            # already in m/s²
    formula = term.get("formula", "").strip()
    if formula and inc_deg is not None:
        # minimal sandbox for eval – only the symbols that appear in OWSG formulas
        env = {
            "inc": math.radians(inc_deg),
            "azm": math.radians(az_deg) if az_deg is not None else 0.0,
            "dip": 0.0,
            "gtot": gt or 9.81,
            # math helpers
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "sqrt": math.sqrt, "abs": abs
        }
        try:
            sigma *= abs(eval(formula, {"__builtins__": None}, env))
        except Exception:
            pass     # fall back to un‑scaled value if the eval fails
    return sigma


def _get_tolerance(ipm_data, inc_deg: float, tf_deg: float, gt: float, sigma: float = 3.0):
    """3-σ gravity-error tolerance δG (Eq. 3, Appendix 1 A)."""
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    w = _weighting_functions(inc_deg, tf_deg)


    # Debug collection - store found error terms
    debug_terms = {}
    
    # 1-σ sigmas
    # -----------------------------------------------------------------
    # 1‑σ σ values in SI units (m s‑2 for biases, dimension‑less for scale)
    # – choose “i,s” when the station is > 3.0° from vertical,
    #   otherwise fall back to the conservative “e,s” row.
    # -----------------------------------------------------------------
    vec = "i" if inc_deg > 3.0 else "e"          # inclination‑dependent or constant
    tie = "s"                                     # ‘single‑station’ rows only

    # --- bias terms ---------------------------------------------------
    abx = _get_error_term_value(ipm, "ABXY-TI1S", vec, tie,
                                inc_deg=inc_deg, gt=gt)
    debug_terms[f"ABXY-TI1S ({vec},{tie}) - X axis bias"] = abx

    aby = _get_error_term_value(ipm, "ABXY-TI1S", vec, tie,
                                inc_deg=inc_deg, gt=gt)
    debug_terms[f"ABXY-TI1S ({vec},{tie}) - Y axis bias"] = aby

    abz = _get_error_term_value(ipm, "ABZ", vec, tie,
                                inc_deg=inc_deg, gt=gt)
    debug_terms[f"ABZ ({vec},{tie}) - Z axis bias"] = abz

    # --- scale‑factor terms -------------------------------------------
    asx = _get_error_term_value(ipm, "ASXY-TI1S", vec, tie,
                                inc_deg=inc_deg, gt=gt)
    debug_terms[f"ASXY-TI1S ({vec},{tie}) - X axis scale"] = asx

    asy = _get_error_term_value(ipm, "ASXY-TI1S", vec, tie,
                                inc_deg=inc_deg, gt=gt)
    debug_terms[f"ASXY-TI1S ({vec},{tie}) - Y axis scale"] = asy

    asz = _get_error_term_value(ipm, "ASZ", vec, tie,
                                inc_deg=inc_deg, gt=gt)
    debug_terms[f"ASZ ({vec},{tie}) - Z axis scale"] = asz

    wx2 = w["wx"] ** 2
    wy2 = w["wy"] ** 2
    wz2 = w["wz"] ** 2
    var = (
        (abx * w["wx"])**2 +
        (aby * w["wy"])**2 +
        (abz * w["wz"])**2 +
        (asx * gt * wx2)**2 +
        (asy * gt * wy2)**2 +
        (asz * gt * wz2)**2
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
    
    tolerance = sigma * math.sqrt(var)
    return tolerance, debug_terms

def _add_warning(res: QCResult, code: str, msg: str):
    warn = res.details.get("warnings", [])
    warn.append({"code": code, "message": msg})
    res.add_detail("warnings", warn)