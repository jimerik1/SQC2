import math
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

EARTH_RATE_DPH = 15.041067  # deg/hr  (sidereal, matches Ekseth et al.)

# --------------------------------------------------------------------------- #
#  Top-level driver
# --------------------------------------------------------------------------- #
def perform_hert(survey: dict, ipm_data):
    """
    Horizontal Earth-Rate Test (HERT) for xy-gyro systems.
    """
    # --- survey inputs
    gyro_x  = survey['gyro_x']          # deg/hr, gyro sensitive axis ≈ earth-fixed X
    gyro_y  = survey['gyro_y']          # deg/hr, gyro sensitive axis ≈ earth-fixed Y
    inc     = survey['inclination']     # deg
    az      = survey['azimuth']         # deg
    tf      = survey['toolface']        # deg (kept as info; not used here)
    lat     = survey['latitude']        # deg

    # 1. measured horizontal rate |Ω_h|
    measured_h_rate = math.hypot(gyro_x, gyro_y)   # √(ωx²+ωy²)

    # 2. theoretical horizontal rate Ω·cosφ
    theoretical_h_rate = EARTH_RATE_DPH * math.cos(math.radians(lat))

    # 3. error
    h_rate_error = measured_h_rate - theoretical_h_rate

    # 4. tolerance
    tol = _hert_tolerance(ipm_data, inc, az, lat)

    # 5. QC verdict
    is_valid = abs(h_rate_error) <= tol

    # 6. build QCResult
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
    return res.to_dict()

# --------------------------------------------------------------------------- #
#  Core math
# --------------------------------------------------------------------------- #
def _hert_weights(inclination_deg: float, azimuth_deg: float):
    """
    Partial derivatives of ΔΩ_h w.r.t gyro error terms (App. 1 C).
    """
    I = math.radians(inclination_deg)
    A = math.radians(azimuth_deg)

    # Bias weights
    w_gbx =  math.cos(I) * math.cos(A) + math.sin(A) / math.sin(I)
    w_gby =  math.cos(I) * math.sin(A) - math.cos(A) / math.sin(I)

    return w_gbx, w_gby

def _hert_tolerance(ipm_data, inclination_deg: float, azimuth_deg: float,
                    latitude_deg: float) -> float:
    """
    3-sigma tolerance δΩ_h (deg/hr) following Ekseth et al., App. 1 C.
    """
    # ---- load IPM
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    gbx = get_error_term_value(ipm, 'GBX', 'e', 's')
    gby = get_error_term_value(ipm, 'GBY', 'e', 's')
    gsx = get_error_term_value(ipm, 'GSX', 'e', 's')
    gsy = get_error_term_value(ipm, 'GSY', 'e', 's')
    m   = get_error_term_value(ipm, 'M',   'e', 's')
    q   = get_error_term_value(ipm, 'Q',   'e', 's')
    gr  = get_error_term_value(ipm, 'GR',  'e', 's')   # random component (1-σ)

    # ---- weighting functions
    w_gbx, w_gby = _hert_weights(inclination_deg, azimuth_deg)

    # factor for scale-factor terms (2 · Ω · cosφ)
    omega_cos_phi = EARTH_RATE_DPH * math.cos(math.radians(latitude_deg))
    sf_factor_x = 2 * w_gbx * omega_cos_phi
    sf_factor_y = 2 * w_gby * omega_cos_phi

    # M & Q weights (App. 1 C)
    I = math.radians(inclination_deg)
    A = math.radians(azimuth_deg)
    # denominator Ω_h cancels because weights used inside quadratic form;
    w_m = -math.cos(I) * math.cos(A)
    w_q =  math.cos(I) * math.sin(A)

    # ---- 3-σ tolerance
    var = (
        (gbx * w_gbx)**2 +
        (gby * w_gby)**2 +
        (gsx * sf_factor_x)**2 +
        (gsy * sf_factor_y)**2 +
        (m   * w_m)**2 +
        (q   * w_q)**2 +
        gr**2            # random term already 1-σ
    )
    return 3.0 * math.sqrt(var)