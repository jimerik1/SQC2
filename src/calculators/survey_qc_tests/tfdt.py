"""
Total‑Field + Dip Test (TFDT) – Ekseth et al. 2006, Appendix 1 E
----------------------------------------------------------------
Blind‑spots:
* inclination < 10 °  or  > 80 °
* azimuth near cardinal directions (0, 90, 180, 270 °)
* geomagnetic latitude |λ| > 60 °

Inputs (all SI / physical units)
--------------------------------
mag_x / y / z          : nT
accelerometer_x / y / z: m s‑2
expected_geomagnetic_field:
    total_field        : nT
    dip                : degrees
    declination        : degrees (for future use)
sigma                  : k‑σ multiplier (default = 3)

IPM rows used
-------------
* Magnetometer bias   : MBX/Y/Z‑TI1S  (a,s)
* Magnetometer scale  : MSX/Y/Z‑TI1S  (a,s)
* Field‑intensity err.: DECG          (a,g)   – value given in %
* Dip‑angle error     : DBHG          (a,g)   – value deg·nT

Values are converted to 1‑σ in physical units on the fly.
"""

import math
from src.models.qc_result import QCResult
from src.utils.ipm_parser import parse_ipm_file
from src.utils.tolerance import get_error_term_value

# --------------------------------------------------------------------------- #
# Geometry thresholds (degrees)
INC_WARN_LOW  = 10.0
INC_WARN_HIGH = 80.0
AZI_CARD_TOL  = 15.0
LAT_WARN_ABS  = 60.0
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def perform_tfdt(survey, ipm_data, sigma: float = 3.0):
    """Run TFDT for one station and return QCResult.to_dict()."""

    # --- sensor vectors (m s‑2 / nT) --------------------------------------- #
    mx, my, mz = survey["mag_x"],  survey["mag_y"],  survey["mag_z"]
    gx, gy, gz = survey["accelerometer_x"], survey["accelerometer_y"], survey["accelerometer_z"]

    # inclination / toolface from accelerometers (same algo as GET)
    g_tot = math.sqrt(gx*gx + gy*gy + gz*gz)
    inc   = math.degrees(math.acos(max(min(gz / g_tot, 1.0), -1.0)))

    if 10.0 <= inc <= 170.0:
        tf = math.degrees(math.atan2(gy, gx)) % 360.0
    else:
        tf = 0.0  # undefined – not used in TFDT formulae

    # azimuth for warnings only
    num = gx*my - gy*mx
    den = mz*(gx*gx + gy*gy) - gz*(gx*mx + gy*my)
    az  = (math.degrees(math.atan2(num, den)) + 360.0) % 360.0

    lat = survey.get("latitude", 0.0)

    # --- measured total field & dip --------------------------------------- #
    b_tot = math.sqrt(mx*mx + my*my + mz*mz)
    dip_meas = _calc_dip(mx, my, mz, gx, gy, gz)

    # --- theoretical ------------------------------------------------------ #
    field_ref = survey["expected_geomagnetic_field"]
    b_ref  = field_ref["total_field"]     # nT
    dip_ref = field_ref["dip"]            # degrees

    # --- errors ----------------------------------------------------------- #
    err_field = b_tot  - b_ref
    err_dip   = dip_meas - dip_ref

    tol_field, tol_dip, dbg = _tfdt_tolerances(
    ipm_data,
    inc, tf,                # station geometry
    az,                     # NEW: azimuth
    b_ref, dip_ref,         # reference field
    g_tot,                  # NEW: gravity total (only used if formulas need gtot)
    sigma
    )

    is_ok_field = abs(err_field) <= tol_field
    is_ok_dip   = abs(err_dip)   <= tol_dip
    is_valid    = is_ok_field and is_ok_dip

    # --- QCResult --------------------------------------------------------- #
    res = QCResult("TFDT").set_validity(is_valid)

    res.add_measurement("total_field", b_tot)\
       .add_theoretical("total_field", b_ref)\
       .add_error("total_field", err_field)\
       .add_tolerance("total_field", tol_field)

    res.add_measurement("dip", dip_meas)\
       .add_theoretical("dip", dip_ref)\
       .add_error("dip", err_dip)\
       .add_tolerance("dip", tol_dip)

    res.add_detail("is_valid_field", is_ok_field)\
       .add_detail("is_valid_dip",   is_ok_dip)\
       .add_detail("inclination", inc)\
       .add_detail("toolface",   tf)\
       .add_detail("azimuth",    az)\
       .add_detail("latitude",   lat)\
       .add_detail("weighting_functions", _tfdt_weights(inc, tf, dip_ref))\
       .add_detail("debug_ipm_terms", dbg)

    _maybe_add_warnings(res, inc, az, lat)
    return res.to_dict()

# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _is_cardinal(az: float) -> bool:
    az = az % 360.0
    return any(abs(az - c) < AZI_CARD_TOL for c in (0, 90, 180, 270))

def _maybe_add_warnings(res: QCResult, inc, az, lat):
    if inc < INC_WARN_LOW:
        _warn(res, "near_vertical",   f"Inclination {inc:.1f}° < {INC_WARN_LOW}°; TFDT weak.")
    elif inc > INC_WARN_HIGH:
        _warn(res, "near_horizontal", f"Inclination {inc:.1f}° > {INC_WARN_HIGH}°; TFDT weak.")

    if _is_cardinal(az):
        _warn(res, "cardinal_azimuth", f"Azimuth {az:.1f}° near N–S/E–W; TFDT ill‑conditioned.")

    if abs(lat) > LAT_WARN_ABS:
        _warn(res, "high_mag_lat", f"Geomagnetic latitude {lat:.1f}°; TFDT less reliable above 60° North or South.")

def _warn(result: QCResult, code: str, msg: str):
    warnings = result.details.get("warnings", [])
    warnings.append({"code": code, "message": msg})
    result.add_detail("warnings", warnings)

# --------------------------------------------------------------------------- #
# Physics helpers
# --------------------------------------------------------------------------- #
def _calc_dip(mx, my, mz, gx, gy, gz):
    """
    Magnetic dip Θ (deg), positive when the geomagnetic field points downward.
    Implements: Θ = 90° − arccos [(B·G)/(Bt Gt)]
    """
    # magnitudes
    bt = math.sqrt(mx*mx + my*my + mz*mz)
    gt = math.sqrt(gx*gx + gy*gy + gz*gz)

    # dot product B·G
    dot = mx*gx + my*gy + mz*gz

    # clamp to avoid domain errors
    c = max(min(dot / (bt * gt), 1.0), -1.0)

    # 90° − arccos(...)
    return 90.0 - math.degrees(math.acos(c))

def _tfdt_weights(inc_deg, tf_deg, dip_deg):
    I, T, D = map(math.radians, (inc_deg, tf_deg, dip_deg))
    # total‑field weights
    wbx_b = math.sin(I)*math.cos(T)*math.cos(D) - math.sin(T)*math.sin(D)
    wby_b = math.sin(I)*math.sin(T)*math.cos(D) + math.cos(T)*math.sin(D)
    wbz_b = math.cos(I)*math.cos(D)
    # dip weights
    cosD = math.cos(D)
    wbx_d = (math.sin(I)*math.cos(T)*math.sin(D) + math.sin(T)*cosD) / cosD
    wby_d = (math.sin(I)*math.sin(T)*math.sin(D) - math.cos(T)*cosD) / cosD
    wbz_d = math.cos(I)*math.sin(D) / cosD
    return {
        "wbx_b": wbx_b, "wby_b": wby_b, "wbz_b": wbz_b,
        "wbx_d": wbx_d, "wby_d": wby_d, "wbz_d": wbz_d,
    }

# --------------------------------------------------------------------------- #
# Tolerance calculator
# --------------------------------------------------------------------------- #
def _tfdt_tolerances(ipm_data, inc, tf, az, b_ref, dip_ref, g_tot, sigma=3.0):
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    w   = _tfdt_weights(inc, tf, dip_ref)
    dbg = {}

    # -- helper for value selection + logging ----------------------------- #
    def _get(name, vec="a", tie="s", default=0.0):
        val = get_error_term_value(
            ipm, name, vec, tie,
            inc_deg=inc, az_deg=az, dip_deg=dip_ref,
            mtot=b_ref, gtot=g_tot        # helper will use these if the formula needs them
        )
        dbg[f"{name} ({vec},{tie})"] = val
        return val or default
    
    # 1‑σ magnetometer terms (bias nT, scale dimension‑less)
    mbx = _get("MBX")
    mby = _get("MBY")
    mbz = _get("MBZ")
    if mbx == mby == 0.0:          # fall back to combined rows
        mbx = mby = _get("MBXY-TI1S")
    msx = _get("MSX")
    msy = _get("MSY")
    msz = _get("MSZ")
    if msx == msy == 0.0:
        msx = msy = _get("MSXY-TI1S")

    # field‑intensity σ: DECG given in percent → fraction
    mfi_raw = _get("DECG", vec="a", tie="g", default=0.36)  # %
    mfi = abs(mfi_raw) * 0.01               # fraction (e.g. 0.0036)

    # dip‑angle σ: DBHG given in deg·nT → degrees
    mdi_raw = _get("DBHG", vec="a", tie="g", default=5000.) # deg·nT
    mdi = abs(mdi_raw) / b_ref              # degrees

    dbg["final_values_used"] = dict(
        mbx=mbx, mby=mby, mbz=mbz,
        msx=msx, msy=msy, msz=msz,
        mfi=mfi, mdi=mdi
    )

    # -- variance contributions ------------------------------------------ #
    field_terms = {
        "mbx": ((mbx / b_ref) * w["wbx_b"])**2,
        "mby": ((mby / b_ref) * w["wby_b"])**2,
        "mbz": ((mbz / b_ref) * w["wbz_b"])**2,
        "msx": (msx * w["wbx_b"])**2,
        "msy": (msy * w["wby_b"])**2,
        "msz": (msz * w["wbz_b"])**2,
        "mfi": (mfi * b_ref)**2
    }

    dip_terms = {
    # bias terms (nT → deg) divide by B_tot
    "mbx": ((mbx / b_ref) * w["wbx_d"])**2,
    "mby": ((mby / b_ref) * w["wby_d"])**2,
    "mbz": ((mbz / b_ref) * w["wbz_d"])**2,
    # scale‑factor terms are already dimensionless — no B_tot
    "msx": (msx * w["wbx_d"])**2,
    "msy": (msy * w["wby_d"])**2,
    "msz": (msz * w["wbz_d"])**2,
    "mdi":  mdi**2
    }

    dbg["weighted_field_contributions"] = field_terms
    dbg["weighted_dip_contributions"]   = dip_terms

    tol_field = sigma * math.sqrt(sum(field_terms.values()))
    tol_dip   = sigma * math.sqrt(sum(dip_terms.values()))

    dbg["calculated_tolerances"] = {
        "field_tolerance": tol_field,
        "dip_tolerance":   tol_dip,
        "sigma": sigma
    }
    return tol_field, tol_dip, dbg