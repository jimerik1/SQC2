# services/qc/msgt.py
import math
import numpy as np
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value


EARTH_RATE_DPH = 15.041067  # deg/hr  (sidereal)

# --------------------------------------------------------------------------- #
#  top-level entry
# --------------------------------------------------------------------------- #
def perform_msgt(surveys, ipm_data):
    """
    Multi-Station Gyro Test (MSGT) – Ekseth et al., Appendix 1 D
    Each survey dict must contain:
        gyro_x, gyro_y           [deg/hr]  (Earth-fixed x,y components)
        inclination, azimuth     [deg]
        toolface                 [deg]     (used only for geometry checks)
        latitude                 [deg]
    """
    if len(surveys) < 10:
        return _fail("At least 10 survey stations are required for MSGT")

    incs = np.radians([s['inclination'] for s in surveys])
    azms = np.radians([s['azimuth']     for s in surveys])
    tfs  = np.radians([s['toolface']    for s in surveys])

    # ---------- geometry checks ------------------------------------------------
    inc_var = incs.max() - incs.min()

    quad_hits = [0, 0, 0, 0]
    for deg in (s['toolface'] % 360 for s in surveys):
        quad_hits[int(deg // 90)] += 1
    if inc_var < math.radians(30) or sum(1 for q in quad_hits if q) < 3:
        return _fail("Need ≥30° inclination spread and toolfaces in ≥3 quadrants")

    ew_hits = sum(1 for deg in (s['azimuth'] % 360 for s in surveys)
                  if 60 <= deg <= 120 or 240 <= deg <= 300)
    if ew_hits / len(surveys) > 0.5:
        return _fail("More than 50 % of stations lie in east–west sector; geometry too weak")

    # ---------- horizontal-rate errors & design matrix ------------------------
    omega_h_err = []
    A_rows = []

    for s, I, A in zip(surveys, incs, azms):
        # measured Ω_h
        Ωh_meas = math.hypot(s['gyro_x'], s['gyro_y'])

        # theoretical Ω cos φ
        Ωh_theo = EARTH_RATE_DPH * math.cos(math.radians(s['latitude']))
        omega_h_err.append(Ωh_meas - Ωh_theo)

        # weighting functions (App. 1 C)
        w_gbx = math.cos(I) * math.cos(A) + math.sin(A) / math.sin(I)
        w_gby = math.cos(I) * math.sin(A) - math.cos(A) / math.sin(I)
        w_m   = -math.cos(I) * math.cos(A)
        w_q   =  math.cos(I) * math.sin(A)
        A_rows.append([w_gbx, w_gby, w_m, w_q])

    A = np.asarray(A_rows)
    dΩ = np.asarray(omega_h_err)

    # ---------- least-squares solution ---------------------------------------
    X, *_ = np.linalg.lstsq(A, dΩ, rcond=None)          # GBX*, GBY*, M, Q

    residuals = dΩ - A @ X
    cofactor = np.linalg.inv(A.T @ A)
    corr = cofactor / np.sqrt(np.outer(np.diag(cofactor), np.diag(cofactor)))
    max_corr = np.abs(corr - np.eye(4)).max()

    # ---------- tolerance build ----------------------------------------------
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    σ_gbx = get_error_term_value(ipm, 'GBX', 'e', 's')
    σ_gby = get_error_term_value(ipm, 'GBY', 'e', 's')
    σ_m   = get_error_term_value(ipm, 'M',   'e', 's')
    σ_q   = get_error_term_value(ipm, 'Q',   'e', 's')
    σ_gsx = get_error_term_value(ipm, 'GSX', 'e', 's')
    σ_gsy = get_error_term_value(ipm, 'GSY', 'e', 's')
    σ_gr  = get_error_term_value(ipm, 'GR',  'e', 's')

    param_tol = (3*σ_gbx, 3*σ_gby, 3*σ_m, 3*σ_q)
    params_valid = all(abs(x) <= t for x, t in zip(X, param_tol))

    res_tol = []
    for I, A, s in zip(incs, azms, surveys):
        w_gbx = math.cos(I) * math.cos(A) + math.sin(A) / math.sin(I)
        w_gby = math.cos(I) * math.sin(A) - math.cos(A) / math.sin(I)
        w_m   = -math.cos(I) * math.cos(A)
        w_q   =  math.cos(I) * math.sin(A)

        Ωcosφ = EARTH_RATE_DPH * math.cos(math.radians(s['latitude']))
        tol = 3 * math.sqrt(
            (σ_gbx * w_gbx)**2 +
            (σ_gby * w_gby)**2 +
            (σ_m   * w_m  )**2 +
            (σ_q   * w_q  )**2 +
            (2 * σ_gsx * w_gbx * Ωcosφ)**2 +
            (2 * σ_gsy * w_gby * Ωcosφ)**2 +
            σ_gr**2
        )
        res_tol.append(tol)
    residuals_valid = np.all(np.abs(residuals) <= res_tol)

    overall = params_valid and residuals_valid and max_corr <= 0.4

    # ---------- QCResult ------------------------------------------------------
    r = QCResult("MSGT")
    r.set_validity(overall)

    for name, val, tol in zip(['GBX*', 'GBY*', 'M', 'Q'], X, param_tol):
        r.add_measurement(name, float(val))
        r.add_tolerance(name, tol)

    r.add_detail("residuals", residuals.tolist())
    r.add_detail("residual_tolerances", res_tol)
    r.add_detail("correlation_matrix", corr.tolist())
    r.add_detail("max_nondiagonal_correlation", float(max_corr))
    r.add_detail("inclination_variation_deg", math.degrees(inc_var))
    r.add_detail("quadrant_distribution", quad_hits)
    r.add_detail("east_west_ratio", ew_hits / len(surveys))

    if not overall:
        if max_corr > 0.4:
            r.add_detail("failure_reason", "High parameter correlations")
        elif not params_valid:
            r.add_detail("failure_reason", "Parameter estimate exceeds tolerance")
        else:
            r.add_detail("failure_reason", "Residual error exceeds tolerance")

    return r.to_dict()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _fail(msg):
    return {'is_valid': False, 'error': msg}