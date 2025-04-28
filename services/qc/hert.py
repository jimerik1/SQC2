# services/qc/hert.py
"""
Horizontal Earth-Rate Test (HERT)
---------------------------------
Implements Ekseth et al. 2006, Appendix 1 C.

•  < 3 ° or > 177 ° inclination  →   **hard reject**  (mathematical singularity).
•  3–10 ° or 80–177 ° inclination, OR azimuth near cardinal
   → returns normal pass/fail **plus** geometry warning.

The warning pattern mirrors GET and TFDT so front-end code can treat it
uniformly.
"""
import math
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

EARTH_RATE_DPH = 15.041067  # deg / hr  (sidereal)

# Advisory thresholds (deg)
INC_WARN_LOW  = 10.0
INC_WARN_HIGH = 80.0
AZI_CARDINAL_TOL = 15.0      # warn if azimuth within ±15° of 0, 90, 180, 270


# --------------------------------------------------------------------------- #
#  Public entry point
# --------------------------------------------------------------------------- #
def perform_hert(survey: dict, ipm_data):
    """
    Horizontal Earth-Rate Test for xy-gyro systems.
    """
    gyro_x = survey["gyro_x"]
    gyro_y = survey["gyro_y"]
    inc    = survey["inclination"]   # deg
    az     = survey["azimuth"]       # deg
    tf     = survey["toolface"]      # deg (for information)
    lat    = survey["latitude"]      # deg

    # ----- singularity: refuse truly vertical wells ------------------------- #
    if inc < 3.0 or inc > 177.0:
        return _fail(
            "HERT is undefined for inclinations below 3 ° or above 177 °. "
            "See Ekseth 2006 App. 1 C."
        )

    # 1. measured horizontal rate |Ω_h|
    measured_h_rate = math.hypot(gyro_x, gyro_y)

    # 2. theoretical Ω cos φ
    theoretical_h_rate = EARTH_RATE_DPH * math.cos(math.radians(lat))

    # 3. error
    h_rate_error = measured_h_rate - theoretical_h_rate

    # 4. tolerance
    tol = _hert_tolerance(ipm_data, inc, az, lat)

    # 5. verdict
    is_valid = abs(h_rate_error) <= tol

    # 6. QCResult
    res = QCResult("HERT")
    res.set_validity(is_valid)
    res.add_measurement("horizontal_rate", measured_h_rate)
    res.add_theoretical("horizontal_rate", theoretical_h_rate)
    res.add_error("horizontal_rate", h_rate_error)
    res.add_tolerance("horizontal_rate", tol)
    res.add_detail("inclination", inc)
    res.add_detail("azimuth", az)
    res.add_detail("toolface", tf)
    res.add_detail("weighting_functions", _hert_weights(inc, az))

    # ----- geometry advisories --------------------------------------------- #
    if inc < INC_WARN_LOW or inc > INC_WARN_HIGH:
        _add_warning(
            res,
            "weak_geometry",
            f"HERT discriminatory power reduced at inclination {inc:.1f} °."
        )

    if _is_cardinal_azimuth(az):
        _add_warning(
            res,
            "cardinal_azimuth",
            f"Azimuth {az:.1f} ° is near a cardinal direction; "
            "weights become ill-conditioned (Ekseth 2006)."
        )

    return res.to_dict()


# --------------------------------------------------------------------------- #
#  Core math
# --------------------------------------------------------------------------- #
def _hert_weights(inclination_deg: float, azimuth_deg: float):
    """
    Weighting functions ∂ΔΩ_h/∂error_term  (Ekseth App. 1 C)
    """
    I = math.radians(inclination_deg)
    A = math.radians(azimuth_deg)

    sinI = math.sin(I) or 1e-6  # never 0 here (guarded earlier)
    w_gbx = math.cos(I) * math.cos(A) + math.sin(A) / sinI
    w_gby = math.cos(I) * math.sin(A) - math.cos(A) / sinI
    return w_gbx, w_gby


def _hert_tolerance(ipm_data,
                    inclination_deg: float,
                    azimuth_deg: float,
                    latitude_deg: float) -> float:
    """3 σ tolerance δΩ_h  (deg / hr)."""
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data

    # 1 σ sigmas
    gbx = get_error_term_value(ipm, "GBX", "e", "s")
    gby = get_error_term_value(ipm, "GBY", "e", "s")
    gsx = get_error_term_value(ipm, "GSX", "e", "s")
    gsy = get_error_term_value(ipm, "GSY", "e", "s")
    m   = get_error_term_value(ipm, "M",   "e", "s")
    q   = get_error_term_value(ipm, "Q",   "e", "s")
    gr  = get_error_term_value(ipm, "GR",  "e", "s")

    w_gbx, w_gby = _hert_weights(inclination_deg, azimuth_deg)
    omega_cos_phi = EARTH_RATE_DPH * math.cos(math.radians(latitude_deg))
    sf_x = 2.0 * w_gbx * omega_cos_phi
    sf_y = 2.0 * w_gby * omega_cos_phi

    I = math.radians(inclination_deg)
    A = math.radians(azimuth_deg)
    w_m = -math.cos(I) * math.cos(A)
    w_q =  math.cos(I) * math.sin(A)

    var = (
        (gbx * w_gbx) ** 2 +
        (gby * w_gby) ** 2 +
        (gsx * sf_x)  ** 2 +
        (gsy * sf_y)  ** 2 +
        (m   * w_m)   ** 2 +
        (q   * w_q)   ** 2 +
        gr ** 2
    )
    return 3.0 * math.sqrt(var)


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _is_cardinal_azimuth(azimuth_deg: float) -> bool:
    """Return True if azimuth is within ±15 ° of 0, 90, 180, or 270."""
    az = azimuth_deg % 360
    return any(abs(az - c) < AZI_CARDINAL_TOL for c in (0, 90, 180, 270))


def _add_warning(res: QCResult, code: str, msg: str):
    warn = res.details.get("warnings", [])
    warn.append({"code": code, "message": msg})
    res.add_detail("warnings", warn)


def _fail(msg):
    """Uniform error payload."""
    return {"is_valid": False, "error": msg}