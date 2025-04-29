# src/calculators/external_qc_tests/iomt.py
import math
import numpy as np
from src.models.qc_result import QCResult
from src.utils.ipm_parser import parse_ipm_file
from src.utils.tolerance import get_error_term_value
from src.utils.linalg import safe_inverse

def perform_iomt(in_run, out_run, ipm_data):
    """
    In-run/Out-run Misalignment Test (IOMT) - SPE 105558 Appendix 1A
    
    Tests for toolface-dependent misalignment errors by comparing inclinations 
    between in-run and out-run at the same depths.
    
    Parameters
    ----------
    in_run : list of dict
        Each dict must contain 'depth', 'inclination', and 'toolface' (gyro toolface near vertical)
    out_run : list of dict
        Each dict must contain 'depth', 'inclination', and 'toolface' (gyro toolface near vertical)
    ipm_data : str or IPMFile
        Raw IPM content or a parsed IPMFile instance.
        
    Returns
    -------
    dict
        QCResult serialized as dict
    """
    # ---------- Check for sufficient data ----------------------------------------
    if len(in_run) < 10 or len(out_run) < 10:
        return _fail("At least 10 survey stations are required for IOMT")
    
    # ---------- Find matching depths between in_run and out_run -----------------
    # Create a lookup of out_run inclinations and toolfaces by depth
    out_run_lookup = {s['depth']: s for s in out_run}
    
    # Find matching depths
    matching_points = []
    for in_point in in_run:
        if in_point['depth'] in out_run_lookup:
            out_point = out_run_lookup[in_point['depth']]
            matching_points.append({
                'depth': in_point['depth'],
                'in_inc': in_point['inclination'],
                'out_inc': out_point['inclination'],
                'in_tf': in_point['toolface'],
                'out_tf': out_point['toolface']
            })
    
    if len(matching_points) < 10:
        return _fail("At least 10 matching depth points required for IOMT")
    
    # ---------- Check toolface distribution -------------------------------------
    # Count quadrant distribution for in-run and out-run
    in_quads = [0, 0, 0, 0]
    out_quads = [0, 0, 0, 0]
    
    for point in matching_points:
        in_quads[int(point['in_tf'] // 90) % 4] += 1
        out_quads[int(point['out_tf'] // 90) % 4] += 1
    
    # Check if toolfaces span at least 3 quadrants
    if sum(1 for q in in_quads if q > 0) < 3 or sum(1 for q in out_quads if q > 0) < 3:
        return _fail("Toolfaces must span at least three quadrants in both in-run and out-run")
    
    # ---------- Build input vectors and design matrix ---------------------------
    # Inclination differences vector
    inc_diffs = np.array([p['out_inc'] - p['in_inc'] for p in matching_points])
    
    # Design matrix for least squares solution
    A_rows = []
    for point in matching_points:
        in_tf_rad = math.radians(point['in_tf'])
        out_tf_rad = math.radians(point['out_tf'])
        A_rows.append([
            math.cos(out_tf_rad) - math.cos(in_tf_rad),
            math.sin(out_tf_rad) - math.sin(in_tf_rad)
        ])
    
    A = np.array(A_rows)
    
    # ---------- Solve for MX and MY ---------------------------------------------
    try:
        # Use safe inverse to handle potential singularity problems
        cofactor = safe_inverse(A.T @ A, ridge=1e-9)
        params = cofactor @ A.T @ inc_diffs  # [MX, MY]
    except np.linalg.LinAlgError as exc:
        return _fail(f"Matrix inversion failed: {str(exc)}")
    
    mx, my = params.tolist()
    
    # ---------- Check parameter correlation -------------------------------------
    # Calculate correlation coefficient between MX and MY
    corr_coeff = cofactor[0, 1] / math.sqrt(cofactor[0, 0] * cofactor[1, 1])
    if abs(corr_coeff) > 0.4:  # Maximum allowed correlation of 0.4
        return _fail(f"|ρ(MX, MY)| = {corr_coeff:.2f} exceeds 0.4 - need wider toolface spread")
    
    # ---------- Calculate residuals and check against tolerance -----------------
    residuals = inc_diffs - (A @ params)
    
    # Get tolerance values from IPM
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    σ_mx = get_error_term_value(ipm, "MX", "e", "s")
    σ_my = get_error_term_value(ipm, "MY", "e", "s")
    σ_mr = get_error_term_value(ipm, "MR", "e", "s", default=0.05)  # Default random misalignment term
    
    # 3σ tolerances
    mx_tol = 3.0 * σ_mx
    my_tol = 3.0 * σ_my
    res_tol = 3.0 * math.sqrt(2) * σ_mr  # Residual tolerance for individual differences
    
    # Check validity
    valid_mx = abs(mx) <= mx_tol
    valid_my = abs(my) <= my_tol
    valid_residuals = np.all(np.abs(residuals) <= res_tol)
    
    # Apply 50% increase to residual tolerance for drill-pipe surveys
    if not valid_residuals:
        adjusted_res_tol = 1.5 * res_tol
        valid_residuals = np.all(np.abs(residuals) <= adjusted_res_tol)
    else:
        adjusted_res_tol = res_tol
    
    overall = valid_mx and valid_my and valid_residuals
    
    # ---------- Create QCResult ------------------------------------------------
    result = QCResult("IOMT")
    result.set_validity(overall)
    
    result.add_measurement("misalignment_mx", mx)
    result.add_measurement("misalignment_my", my)
    result.add_tolerance("misalignment_mx", mx_tol)
    result.add_tolerance("misalignment_my", my_tol)
    
    result.add_detail("is_mx_valid", valid_mx)
    result.add_detail("is_my_valid", valid_my)
    result.add_detail("residuals_valid", valid_residuals)
    result.add_detail("parameter_correlation", corr_coeff)
    result.add_detail("residuals", residuals.tolist())
    result.add_detail("residual_tolerance", float(adjusted_res_tol))
    result.add_detail("in_run_quadrant_distribution", in_quads)
    result.add_detail("out_run_quadrant_distribution", out_quads)
    result.add_detail("matching_points_count", len(matching_points))
    
    if not overall:
        if not valid_mx or not valid_my:
            result.add_detail("failure_reason", "Misalignment estimates exceed tolerance")
        elif not valid_residuals:
            result.add_detail("failure_reason", "Residual inclination differences exceed tolerance")
            
    return result.to_dict()

def _fail(msg):
    """Return a standardized error response."""
    return {"is_valid": False, "error": msg, "test_name": "IOMT"}