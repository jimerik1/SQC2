# services/qc/tfdt.py
"""
Total-Field + Dip Test (TFDT) – Ekseth et al. 2006, Appendix 1 E

Blind-spots:
• near-vertical or near-horizontal wells;
• hole direction roughly East–West or North–South;
• high geomagnetic latitude (> 60 °).

We still compute pass/fail but attach geometry warnings so the client can
flag reduced confidence.
"""
import math
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

# Geometry thresholds
INC_WARN_LOW   = 10.0   # deg
INC_WARN_HIGH  = 80.0   # deg
AZI_CARD_TOL   = 15.0   # ± deg around 0, 90, 180, 270
LAT_WARN_ABS   = 60.0   # |latitude| deg

# --------------------------------------------------------------------------- #
def perform_tfdt(survey, ipm_data):
    """Run TFDT for one station and return QCResult.to_dict()."""
    # ------------ extract -------------------------------------------------- #
    mag_x, mag_y, mag_z = survey["mag_x"], survey["mag_y"], survey["mag_z"]
    acc_x, acc_y, acc_z = survey["accelerometer_x"], survey["accelerometer_y"], survey["accelerometer_z"]

    inc = survey["inclination"]     # deg
    tf  = survey["toolface"]        # deg
    azi = survey.get("azimuth", 0)  # deg – optional but used for warnings
    lon, lat, depth = survey["longitude"], survey["latitude"], survey["depth"]

    geo = (
        survey.get("expected_geomagnetic_field")
        or survey.get("geomagnetic_field")
        or _get_geomagnetic_field(lon, lat, depth)
    )

    # ------------ measured values ----------------------------------------- #
    meas_total = math.sqrt(mag_x**2 + mag_y**2 + mag_z**2)
    meas_dip   = _calc_dip(mag_x, mag_y, mag_z, acc_x, acc_y, acc_z)

    # ------------ theoretical --------------------------------------------- #
    theo_total = geo["total_field"]
    theo_dip   = geo["dip"]

    # ------------ errors --------------------------------------------------- #
    field_err = meas_total - theo_total
    dip_err   = meas_dip   - theo_dip

    # tolerances
    field_tol, dip_tol = _tfdt_tolerances(ipm_data, inc, tf, theo_total, theo_dip)

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

    # ------------ geometry warnings --------------------------------------- #
    _maybe_add_warnings(res, inc, azi, lat)

    return res.to_dict()

# --------------------------------------------------------------------------- #
#  Geometry helpers
# --------------------------------------------------------------------------- #
def _is_cardinal(az: float) -> bool:
    az = az % 360
    return any(abs(az - c) < AZI_CARD_TOL for c in (0, 90, 180, 270))

def _maybe_add_warnings(res: QCResult, inc, az, lat):
    if inc < INC_WARN_LOW:
        _warn(res, "near_vertical",
              f"Inclination {inc:.1f}° (< {INC_WARN_LOW}°); TFDT weak (Ekseth 2006).")
    elif inc > INC_WARN_HIGH:
        _warn(res, "near_horizontal",
              f"Inclination {inc:.1f}° (> {INC_WARN_HIGH}°); TFDT weak.")

    if _is_cardinal(az):
        _warn(res, "cardinal_azimuth",
              f"Azimuth {az:.1f}° near N–S/E–W; TFDT weighting ill-conditioned.")

    if abs(lat) > LAT_WARN_ABS:
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
    dot = mx*gx + my*gy + mz*gz
    dip = math.degrees(
        math.asin(dot / (g * math.sqrt(mx**2 + my**2 + mz**2)))
    )
    return dip

def _get_geomagnetic_field(lon, lat, depth):
    # Placeholder – replace with IGRF/WMM call in production
    return {"total_field": 48_000.0, "dip": 65.0, "declination": 4.0}

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
def _tfdt_tolerances(ipm_data, inc, tf, total_field, dip):
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    w = _tfdt_weights(inc, tf, dip)

    mbx = get_error_term_value(ipm, "MBX", "e", "s")
    mby = get_error_term_value(ipm, "MBY", "e", "s")
    mbz = get_error_term_value(ipm, "MBZ", "e", "s")
    msx = get_error_term_value(ipm, "MSX", "e", "s")
    msy = get_error_term_value(ipm, "MSY", "e", "s")
    msz = get_error_term_value(ipm, "MSZ", "e", "s")
    mfi = get_error_term_value(ipm, "MFI", "e", "s")
    mdi = get_error_term_value(ipm, "MDI", "e", "s")

    field_tol = 3 * math.sqrt(
        (mbx * w["wbx_b"])**2 +
        (mby * w["wby_b"])**2 +
        (mbz * w["wbz_b"])**2 +
        (2*msx * w["wbx_b"] * total_field)**2 +
        (2*msy * w["wby_b"] * total_field)**2 +
        (2*msz * w["wbz_b"] * total_field)**2 +
        (mfi * total_field)**2
    )

    dip_tol = 3 * math.sqrt(
        (mbx * w["wbx_d"])**2 +
        (mby * w["wby_d"])**2 +
        (mbz * w["wbz_d"])**2 +
        (2*msx * w["wbx_d"] * total_field)**2 +
        (2*msy * w["wby_d"] * total_field)**2 +
        (2*msz * w["wbz_d"] * total_field)**2 +
        mdi**2
    )
    return field_tol, dip_tol