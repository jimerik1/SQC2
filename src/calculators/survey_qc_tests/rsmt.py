# services/qc/rsmt.py
"""
Rotation-Shot Misalignment Test (RSMT)
-------------------------------------
Implements Appendix 1 G of Ekseth et al. (2006).

Key production-safety rules applied here
---------------------------------------
* ≥ 5 rotation-shot stations, inclination ≥ 5 deg.
* Toolfaces must populate ≥ 3 quadrants.
* Parameter-correlation limit |ρMX,MY| ≤ 0.40  (paper, Sect. G).
* Each residual ≤ 0.10 deg by default (guard against “rogue” shots).
* Robust LSQ:  (AᵀA + λI)⁻¹  with tiny ridge λ to avoid singularities.
"""
from __future__ import annotations

import math
from typing import List, Dict, Any, Tuple

import numpy as np

from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from utils.tolerance import get_error_term_value

# -----------------------------------------------------------------------------
# Tunables (override from app config if desired)
# -----------------------------------------------------------------------------
MAX_PARAM_CORR = 0.40     # |ρMX,MY| threshold
MAX_RESIDUAL   = 0.10     # deg
RIDGE_EPS      = 1e-9     # regularisation strength


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def perform_rsmt(surveys: List[Dict[str, float]], ipm_data: Any) -> Dict[str, Any]:
    """
    Rotation-Shot Misalignment Test (RSMT).

    Parameters
    ----------
    surveys : list of dict
        Each dict must contain: inclination (deg) and toolface (deg).
        *All* stations must be measured at *one depth* (rotation shots).
    ipm_data : str | IPMFile
        Raw IPM content or a parsed IPMFile instance.

    Returns
    -------
    dict
        QCResult serialised as dict.
    """
    # ---------- geometry sanity ------------------------------------------------
    if len(surveys) < 5:
        return _fail("At least 5 rotation-shot measurements are required")

    inc0 = surveys[0]["inclination"]
    if inc0 < 5.0:
        return _fail("Inclination must be ≥ 5° for reliable toolface readings")

    # quadrant coverage
    quads = [0, 0, 0, 0]
    for s in surveys:
        quads[int(s["toolface"] // 90) % 4] += 1
    if sum(bool(q) for q in quads) < 3:
        return _fail("Toolfaces must span at least three quadrants")

    # ---------- build LSQ system ΔI = A·[MX MY]ᵀ ------------------------------
    ref_tf_rad = math.radians(surveys[0]["toolface"])
    ref_inc    = inc0

    A_rows, b = [], []
    for s in surveys[1:]:
        tf_rad = math.radians(s["toolface"])
        A_rows.append([math.cos(tf_rad) - math.cos(ref_tf_rad),
                       math.sin(tf_rad) - math.sin(ref_tf_rad)])
        b.append(s["inclination"] - ref_inc)

    A = np.asarray(A_rows)
    b = np.asarray(b)

    # ---------- solve with tiny ridge to avoid singularities -------------------
    try:
        cofactor = np.linalg.inv(A.T @ A + RIDGE_EPS * np.eye(2))
        params   = cofactor @ A.T @ b          # [MX, MY]
    except np.linalg.LinAlgError:
        return _fail("Normal-matrix inversion failed – geometry too weak")

    mx, my = params.tolist()

    # ---------- correlation check ---------------------------------------------
    corr_coeff = cofactor[0, 1] / math.sqrt(cofactor[0, 0] * cofactor[1, 1])
    if abs(corr_coeff) > MAX_PARAM_CORR:
        return _fail(
            f"|ρ(MX, MY)| = {corr_coeff:.2f} exceeds {MAX_PARAM_CORR:.2f} – "
            "need wider toolface spread"
        )

    # ---------- residual QC ----------------------------------------------------
    residuals = (A @ params) - b
    if np.any(np.abs(residuals) > MAX_RESIDUAL):
        return _fail("One or more rotation shots have residual > "
                     f"{MAX_RESIDUAL:.2f} deg – check data quality")

    # ---------- tolerances from IPM -------------------------------------------
    mx_tol, my_tol = _rsmt_tolerances(ipm_data)
    valid_mx = abs(mx) <= mx_tol
    valid_my = abs(my) <= my_tol
    overall  = valid_mx and valid_my

    # ---------- package result -------------------------------------------------
    r = QCResult("RSMT")
    r.set_validity(overall)
    r.add_measurement("misalignment_mx", mx).add_tolerance("misalignment_mx", mx_tol)
    r.add_measurement("misalignment_my", my).add_tolerance("misalignment_my", my_tol)

    r.add_detail("is_mx_valid", valid_mx)
    r.add_detail("is_my_valid", valid_my)
    r.add_detail("parameter_correlation", corr_coeff)
    r.add_detail("residuals", residuals.tolist())
    r.add_detail("residual_gate_deg", MAX_RESIDUAL)
    r.add_detail("inclination_deg", inc0)
    r.add_detail("quadrant_distribution", quads)

    return r.to_dict()


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _rsmt_tolerances(ipm_data: Any) -> Tuple[float, float]:
    """Return (MX_tol, MY_tol) in degrees, 3 σ."""
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    σ_mx = get_error_term_value(ipm, "MX", "e", "s")
    σ_my = get_error_term_value(ipm, "MY", "e", "s")
    return 3.0 * σ_mx, 3.0 * σ_my


def _fail(msg: str) -> Dict[str, Any]:
    """Consistent failure payload."""
    return {"is_valid": False, "error": msg}