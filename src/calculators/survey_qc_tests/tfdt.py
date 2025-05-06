# services/qc/tfdt.py
"""
Total-Field + Dip Test (TFDT) – Ekseth et al. 2006, Appendix 1 E

Blind-spots:
- near-vertical or near-horizontal wells;
- hole direction roughly East–West or North–South;
- high geomagnetic latitude (> 60 °).

We still compute pass/fail but attach geometry warnings so the client can
flag reduced confidence.
"""
import math
from src.models.qc_result import QCResult
from src.utils.ipm_parser import parse_ipm_file
from src.utils.tolerance import get_error_term_value

# Geometry thresholds
INC_WARN_LOW   = 10.0   # deg
INC_WARN_HIGH  = 80.0   # deg
AZI_CARD_TOL   = 15.0   # ± deg around 0, 90, 180, 270
LAT_WARN_ABS   = 60.0   # |latitude| deg

# --------------------------------------------------------------------------- #
def perform_tfdt(survey, ipm_data, sigma: float = 3.0):
    """Run TFDT for one station and return QCResult.to_dict()."""
    # ------------ extract -------------------------------------------------- #
    mag_x, mag_y, mag_z = survey["mag_x"], survey["mag_y"], survey["mag_z"]
    acc_x, acc_y, acc_z = survey["accelerometer_x"], survey["accelerometer_y"], survey["accelerometer_z"]

    # Calculate gravity magnitude
    measured_g = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
    
    # Calculate inclination from accelerometer readings
    inc = math.degrees(math.acos(min(max(acc_z / measured_g, -1.0), 1.0)))
    
    # Calculate toolface from accelerometer readings
    if inc >= 10.0 and inc <= 170.0:  # Not too close to vertical
        tf = math.degrees(math.atan2(acc_y, acc_x))
        # Convert to 0-360 range
        tf = (tf + 360) % 360
    else:
        # Default toolface for near-vertical wells
        tf = 0
    
    # Calculate azimuth
    numerator = acc_x * mag_y - acc_y * mag_x
    denominator = mag_z * (acc_x**2 + acc_y**2) - acc_z * (acc_x * mag_x + acc_y * mag_y)
    azi = math.degrees(math.atan2(numerator, denominator))
    # Ensure 0-360 range
    azi = (azi + 360) % 360
    
    lat = survey.get("latitude", 0.0)  # Default to 0 if not provided
    
    geo = survey["expected_geomagnetic_field"]

    # ------------ measured values ----------------------------------------- #
    meas_total = math.sqrt(mag_x**2 + mag_y**2 + mag_z**2)
    
    # Calculate measured dip angle
    g_norm = [acc_x / measured_g, acc_y / measured_g, acc_z / measured_g]
    b_norm = [mag_x / meas_total, mag_y / meas_total, mag_z / meas_total]
    dot_product = g_norm[0]*b_norm[0] + g_norm[1]*b_norm[1] + g_norm[2]*b_norm[2]
    meas_dip = math.degrees(math.asin(min(max(dot_product, -1.0), 1.0)))

    # ------------ theoretical --------------------------------------------- #
    theo_total = geo["total_field"]
    theo_dip   = geo["dip"]

    # ------------ errors --------------------------------------------------- #
    field_err = meas_total - theo_total
    dip_err   = meas_dip   - theo_dip

    # tolerances - get all three values returned now
    field_tol, dip_tol, debug_ipm_terms = _tfdt_tolerances(ipm_data, inc, tf, theo_total, theo_dip, sigma)

    pass_field = abs(field_err) <= field_tol
    pass_dip   = abs(dip_err)   <= dip_tol
    is_valid   = pass_field and pass_dip

    # ------------ QCResult ------------------------------------------------- #
    res = QCResult("TFDT")
    res.set_validity(is_valid)

    res.add_measurement("total_field", meas_total)
    res.add_theoretical("total_field", theo_total)
    res.add_error("total_field", field_err)
    res.add_tolerance("total_field", field_tol)

    res.add_measurement("dip", meas_dip)
    res.add_theoretical("dip", theo_dip)
    res.add_error("dip", dip_err)
    res.add_tolerance("dip", dip_tol)

    res.add_detail("is_valid_field", pass_field)
    res.add_detail("is_valid_dip",   pass_dip)
    res.add_detail("inclination", inc)
    res.add_detail("toolface",   tf)
    res.add_detail("azimuth",    azi)
    res.add_detail("latitude",   lat)
    res.add_detail("weighting_functions",
                   _tfdt_weights(inc, tf, theo_dip))
    res.add_detail("debug_ipm_terms", debug_ipm_terms)  # Add debug info to response

    # ------------ geometry warnings --------------------------------------- #
    _maybe_add_warnings(res, inc, azi, lat)

    return res.to_dict()

# --------------------------------------------------------------------------- #
#  Geometry helpers
# --------------------------------------------------------------------------- #
def _is_cardinal(az: float) -> bool:
    az = az % 360
    return any(abs(az - c) < AZI_CARD_TOL for c in (0, 90, 180, 270))

def _maybe_add_warnings(res: QCResult, inc, az, lat=None):
    if inc < INC_WARN_LOW:
        _warn(res, "near_vertical",
              f"Inclination {inc:.1f}° (< {INC_WARN_LOW}°); TFDT weak (Ekseth 2006).")
    elif inc > INC_WARN_HIGH:
        _warn(res, "near_horizontal",
              f"Inclination {inc:.1f}° (> {INC_WARN_HIGH}°); TFDT weak.")

    if _is_cardinal(az):
        _warn(res, "cardinal_azimuth",
              f"Azimuth {az:.1f}° near N–S/E–W; TFDT weighting ill-conditioned.")

    if lat is not None and abs(lat) > LAT_WARN_ABS:
        _warn(res, "high_mag_lat",
              f"Geomagnetic latitude {lat:.1f}°; TFDT less reliable (Ekseth 2006).")

def _warn(result: QCResult, code: str, msg: str):
    warnings = result.details.get("warnings", [])
    warnings.append({"code": code, "message": msg})
    result.add_detail("warnings", warnings)

# --------------------------------------------------------------------------- #
#  Physics helpers
# --------------------------------------------------------------------------- #
def _calc_dip(mx, my, mz, gx, gy, gz):
    g = math.sqrt(gx**2 + gy**2 + gz**2)
    b = math.sqrt(mx**2 + my**2 + mz**2)
    g_norm = [gx/g, gy/g, gz/g]
    b_norm = [mx/b, my/b, mz/b]
    dot = g_norm[0]*b_norm[0] + g_norm[1]*b_norm[1] + g_norm[2]*b_norm[2]
    dip = math.degrees(math.asin(min(max(dot, -1.0), 1.0)))
    return dip

def _tfdt_weights(inc_deg, tf_deg, dip_deg):
    I, T, D = map(math.radians, (inc_deg, tf_deg, dip_deg))
    # total-field
    wbx_b = math.sin(I)*math.cos(T)*math.cos(D) - math.sin(T)*math.sin(D)
    wby_b = math.sin(I)*math.sin(T)*math.cos(D) + math.cos(T)*math.sin(D)
    wbz_b = math.cos(I)*math.cos(D)
    # dip
    cosD = math.cos(D)
    wbx_d = (math.sin(I)*math.cos(T)*math.sin(D) + math.sin(T)*cosD) / cosD
    wby_d = (math.sin(I)*math.sin(T)*math.sin(D) - math.cos(T)*cosD) / cosD
    wbz_d = math.cos(I)*math.sin(D) / cosD
    return {
        "wbx_b": wbx_b, "wby_b": wby_b, "wbz_b": wbz_b,
        "wbx_d": wbx_d, "wby_d": wby_d, "wbz_d": wbz_d,
    }

# --------------------------------------------------------------------------- #
#  Tolerance calculator
# --------------------------------------------------------------------------- #
def _tfdt_tolerances(ipm_data, inc, tf, total_field, dip, sigma: float = 3.0):
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    w = _tfdt_weights(inc, tf, dip)

    # Debug collection - store found error terms
    debug_terms = {}
    
    # Try different term name variations for magnetometer bias
    mbx_vars = ["MBX", "MBXY-TI1S", "MBXY_TI1S", "MBIX"]
    mby_vars = ["MBY", "MBXY-TI2S", "MBXY_TI2S", "MBIY"]
    mbz_vars = ["MBZ", "MBIZ"]
    
    # Try different term name variations for magnetometer scale
    msx_vars = ["MSX", "MSXY-TI1S", "MSXY_TI1S", "MSIX"]
    msy_vars = ["MSY", "MSXY-TI2S", "MSXY_TI2S", "MSIY"]
    msz_vars = ["MSZ", "MSIZ"]
    
    # Try different field and dip error terms
    mfi_vars = ["MFI", "DECG", "FI"]
    mdi_vars = ["MDI", "DBH", "DBHG", "DI"]
    
    # Try different error vectors and tie-ons
    vectors = ["a", "e", "as", "es"]
    tie_ons = ["s", "g"]
    
    # Function to try multiple variations of a term
    def try_term_variants(variants, vectors, tie_ons, debug_name):
        for variant in variants:
            for vector in vectors:
                for tie_on in tie_ons:
                    val = get_error_term_value(ipm, variant, vector, tie_on)
                    if val > 0:
                        debug_terms[f"{variant} ({vector},{tie_on}) - {debug_name}"] = val
                        return val
        # Not found, record a debug entry
        debug_terms[f"Not found - {debug_name}"] = 0.0
        return 0.0
    
    # Get values with fallbacks for different formats
    mbx = try_term_variants(mbx_vars, vectors, tie_ons, "X magnetometer bias")
    mby = try_term_variants(mby_vars, vectors, tie_ons, "Y magnetometer bias")
    mbz = try_term_variants(mbz_vars, vectors, tie_ons, "Z magnetometer bias")
    
    msx = try_term_variants(msx_vars, vectors, tie_ons, "X magnetometer scale")
    msy = try_term_variants(msy_vars, vectors, tie_ons, "Y magnetometer scale")
    msz = try_term_variants(msz_vars, vectors, tie_ons, "Z magnetometer scale")
    
    mfi = try_term_variants(mfi_vars, vectors, tie_ons, "Field intensity error")
    mdi = try_term_variants(mdi_vars, vectors, tie_ons, "Dip angle error")
    
    # Add a sample of the raw IPM for debugging
    if isinstance(ipm_data, str):
        debug_terms["raw_ipm_sample"] = ipm_data[:200] + "..."
    else:
        debug_terms["ipm_type"] = str(type(ipm_data))
    
    # Default values if nothing is found
    if mbx == 0: mbx = 70.0  # Default to 70 nT
    if mby == 0: mby = 70.0  # Default to 70 nT
    if mbz == 0: mbz = 70.0  # Default to 70 nT
    
    if msx == 0: msx = 0.0016  # Default to 0.0016 (scale)
    if msy == 0: msy = 0.0016  # Default to 0.0016 (scale)
    if msz == 0: msz = 0.0016  # Default to 0.0016 (scale)
    
    if mfi == 0: mfi = 0.0036  # Default to 0.36% field
    if mdi == 0: mdi = 0.5     # Default to 0.5° dip
    
    # Record final values used
    debug_terms["final_values_used"] = {
        "mbx": mbx, "mby": mby, "mbz": mbz,
        "msx": msx, "msy": msy, "msz": msz,
        "mfi": mfi, "mdi": mdi
    }

    # Calculate weighted terms for total field tolerance
    field_terms = {
        "mbx": (mbx * w["wbx_b"])**2,
        "mby": (mby * w["wby_b"])**2,
        "mbz": (mbz * w["wbz_b"])**2,
        "msx": (2*msx * w["wbx_b"] * total_field)**2,
        "msy": (2*msy * w["wby_b"] * total_field)**2,
        "msz": (2*msz * w["wbz_b"] * total_field)**2,
        "mfi": (mfi * total_field)**2
    }
    
    # Calculate weighted terms for dip tolerance
    dip_terms = {
        "mbx": (mbx * w["wbx_d"])**2,
        "mby": (mby * w["wby_d"])**2,
        "mbz": (mbz * w["wbz_d"])**2,
        "msx": (2*msx * w["wbx_d"] * total_field)**2,
        "msy": (2*msy * w["wby_d"] * total_field)**2,
        "msz": (2*msz * w["wbz_d"] * total_field)**2,
        "mdi": mdi**2
    }
    
    debug_terms["weighted_field_contributions"] = field_terms
    debug_terms["weighted_dip_contributions"] = dip_terms

    field_tol = sigma * math.sqrt(sum(field_terms.values()))
    dip_tol = sigma * math.sqrt(sum(dip_terms.values()))
    
    debug_terms["calculated_tolerances"] = {
        "field_tolerance": field_tol,
        "dip_tolerance": dip_tol,
        "sigma": sigma
    }
    
    return field_tol, dip_tol, debug_terms