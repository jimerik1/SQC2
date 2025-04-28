# services/qc/rsmt.py
import math
import numpy as np
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

# --------------------------------------------------------------------------- #
#  Top-level entry
# --------------------------------------------------------------------------- #
def perform_rsmt(surveys, ipm_data):
    """
    Rotation-Shot Misalignment Test (RSMT) – Ekseth et al., App. 1 G.
    """
    # ---------------- basic geometry checks ---------------- #
    if len(surveys) < 5:
        return _fail("At least 5 rotation-shot measurements are required for RSMT")
    inc0 = surveys[0]['inclination']
    if inc0 < 5.0:
        return _fail("RSMT is not reliable for inclinations below 5°")

    # quadrant coverage
    quadrants = [0, 0, 0, 0]                     # Q1–Q4 counters
    for s in surveys:
        q = int(s['toolface'] // 90) % 4
        quadrants[q] += 1
    if sum(1 for q in quadrants if q) < 3:
        return _fail("Toolfaces must span at least three quadrants")

    # ---------------- least-squares solve for MX, MY ------- #
    ref_tf = math.radians(surveys[0]['toolface'])
    ref_inc = surveys[0]['inclination']
    A, b = [], []
    for s in surveys[1:]:
        tf_i = math.radians(s['toolface'])
        inc_diff = s['inclination'] - ref_inc
        A.append([math.cos(tf_i) - math.cos(ref_tf),
                  math.sin(tf_i) - math.sin(ref_tf)])
        b.append(inc_diff)

    A, b = np.asarray(A), np.asarray(b)
    try:
        misalignment = np.linalg.lstsq(A, b, rcond=None)[0]  # MX, MY
    except np.linalg.LinAlgError:
        return _fail("Matrix inversion failed – geometry too weak")

    mx, my = misalignment.tolist()
    # cofactor for correlation coefficient
    Q = np.linalg.inv(A.T @ A)
    corr_coeff = Q[0, 1] / math.sqrt(Q[0, 0] * Q[1, 1])
    if abs(corr_coeff) > 0.4:
        return _fail(f"High MX–MY correlation ({corr_coeff:.2f}). Need wider toolface spread")

    # residuals and residual QC (optional but recommended)
    residuals = (A @ misalignment) - b
    if any(abs(res) > 0.10 for res in residuals):   # 0.10° ≈ typical GET 3 σ at 45°
        return _fail("One or more rotation shots have large residuals – check data quality")

    # ---------------- tolerances --------------------------- #
    mx_tol, my_tol = _rsmt_tolerances(ipm_data)
    valid_mx = abs(mx) <= mx_tol
    valid_my = abs(my) <= my_tol
    overall = valid_mx and valid_my

    # ---------------- build QCResult ---------------------- #
    r = QCResult("RSMT")
    r.set_validity(overall)

    r.add_measurement("misalignment_mx", mx)
    r.add_measurement("misalignment_my", my)
    r.add_tolerance("misalignment_mx", mx_tol)
    r.add_tolerance("misalignment_my", my_tol)

    r.add_detail("is_mx_valid", valid_mx)
    r.add_detail("is_my_valid", valid_my)
    r.add_detail("correlation", corr_coeff)
    r.add_detail("residuals", residuals.tolist())
    r.add_detail("inclination", inc0)
    r.add_detail("quadrant_distribution", quadrants)

    return r.to_dict()

# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _rsmt_tolerances(ipm_data):
    """Return (MX_tol, MY_tol) in degrees, 3 σ."""
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    # If your lumped tags are MBXY-TI1S / TI2S, swap the two strings below.
    mx_sigma = get_error_term_value(ipm, 'MX', 'e', 's')
    my_sigma = get_error_term_value(ipm, 'MY', 'e', 's')
    return 3 * mx_sigma, 3 * my_sigma

def _fail(msg):
    return {'is_valid': False, 'error': msg}