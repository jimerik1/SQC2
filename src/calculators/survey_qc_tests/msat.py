# services/qc/msat.py
import math
import numpy as np
from src.models.qc_result import QCResult
from src.utils.ipm_parser import parse_ipm_file
from src.utils.tolerance import get_error_term_value
from src.utils.linalg import safe_inverse


def perform_msat(surveys, ipm_data):
    """
    Multi-Station Accelerometer Test (MSAT) – Ekseth et al., Appendix 1 B
    --------------------------------------------------------------------
    Each survey dict *must* contain:
        accelerometer_x / y / z   (g)
        inclination, toolface     (deg)
        expected_gravity          (g)   ← provided by caller
    """
    # ---------------- geometry sanity -------------------------------- #
    if len(surveys) < 10:
        return _fail("At least 10 survey stations are required for MSAT")

    incs  = np.radians([s['inclination'] for s in surveys])
    tfs   = np.radians([s['toolface']    for s in surveys])
    inc_variation = incs.max() - incs.min()

    quadrant_hits = [0, 0, 0, 0]
    for deg in (s['toolface'] % 360 for s in surveys):
        quadrant_hits[int(deg // 90)] += 1
    if sum(1 for q in quadrant_hits if q) < 3:
        return _fail("Toolfaces must cover at least three quadrants")

    use_reduced = inc_variation < math.radians(45)

    # ---------------- build design matrix & ΔG vector ---------------- #
    wx = np.sin(incs) * np.sin(tfs)
    wy = np.sin(incs) * np.cos(tfs)
    wz = np.cos(incs)

    Gt = np.asarray([s['expected_gravity'] for s in surveys])  # g-units
    meas_g = np.sqrt([s['accelerometer_x']**2 +
                      s['accelerometer_y']**2 +
                      s['accelerometer_z']**2 for s in surveys])
    dG = meas_g - Gt                                           # ΔG vector

    if use_reduced:  # 3-parameter model
        A = np.column_stack((wx, wy, wz))
        names = ['ABX*', 'ABY*', 'ABZ*']
    else:            # 5-parameter model
        A = np.column_stack((wx,
                             wy,
                             wz,
                             2 * wx * Gt,      # 2·wx·G  (ASX)
                             2 * wy * Gt))     # 2·wy·G  (ASY)
        names = ['ABX', 'ABY', 'ABZ*', 'ASX', 'ASY']

    # ---------------- least-squares solution ------------------------- #
    X, *_ = np.linalg.lstsq(A, dG, rcond=None)          # parameter vector
    residuals = dG - A @ X

    # correlation matrix
    try:
        cofactor = safe_inverse(A.T @ A)
    except np.linalg.LinAlgError as exc:
        return _fail(str(exc))

    corr = cofactor / np.sqrt(np.outer(np.diag(cofactor), np.diag(cofactor)))
    max_corr = np.abs(corr - np.eye(corr.shape[0])).max()

    # ---------------- IPM tolerances (3 σ) --------------------------- #
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    σ_abx = get_error_term_value(ipm, 'ABXY-TI1S', 'e', 's')
    σ_aby = get_error_term_value(ipm, 'ABXY-TI1S', 'e', 's')
    σ_abz = get_error_term_value(ipm, 'ABZ',        'e', 's')
    σ_asx = get_error_term_value(ipm, 'ASXY-TI1S',  'e', 's')
    σ_asy = get_error_term_value(ipm, 'ASXY-TI1S',  'e', 's')

    param_tol = (3*σ_abx, 3*σ_aby, 3*σ_abz) if use_reduced else \
                (3*σ_abx, 3*σ_aby, 3*σ_abz, 3*σ_asx, 3*σ_asy)
    params_valid = all(abs(x) <= t for x, t in zip(X, param_tol))

    # residual-by-station tolerance (GET formula incl. factor 2)
    σ_asz = get_error_term_value(ipm, 'ASZ', 'e', 's')
    res_tol = 3 * np.sqrt((σ_abx*wx)**2 +
                          (σ_aby*wy)**2 +
                          (σ_abz*wz)**2 +
                          (2*σ_asx*wx*Gt)**2 +
                          (2*σ_asy*wy*Gt)**2 +
                          (σ_asz*wz*Gt)**2)
    residuals_valid = np.all(np.abs(residuals) <= res_tol)

    overall = params_valid and residuals_valid and max_corr <= 0.4

    # ---------------- build QCResult ------------------------------- #
    r = QCResult("MSAT")
    r.set_validity(overall)

    for name, val, tol in zip(names, X, param_tol):
        r.add_measurement(name, float(val))
        r.add_tolerance(name, tol)

    r.add_detail("residuals", residuals.tolist())
    r.add_detail("residual_tolerances", res_tol.tolist())
    r.add_detail("correlation_matrix", corr.tolist())
    r.add_detail("max_nondiagonal_correlation", float(max_corr))
    r.add_detail("model_type", "reduced" if use_reduced else "full")
    r.add_detail("inclination_variation_deg", math.degrees(inc_variation))
    r.add_detail("quadrant_distribution", quadrant_hits)

    if not overall:
        if max_corr > 0.4:
            r.add_detail("failure_reason", "High parameter correlations")
        elif not params_valid:
            r.add_detail("failure_reason", "One or more parameter estimates exceed tolerance")
        else:
            r.add_detail("failure_reason", "Residual gravity errors exceed tolerance")

    return r.to_dict()


# ------------------------------------------------------------------- #
# helpers
# ------------------------------------------------------------------- #
def _fail(msg):
    return {'is_valid': False, 'error': msg}