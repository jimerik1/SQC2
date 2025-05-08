# services/qc/msat.py
import math
import numpy as np
from src.models.qc_result import QCResult
from src.utils.ipm_parser import parse_ipm_file
from src.utils.tolerance import get_error_term_value
from src.utils.linalg import safe_inverse


def perform_msat(surveys, ipm_data, sigma: float = 3.0):
    """
    Multi-Station Accelerometer Test (MSAT) – Ekseth et al., Appendix 1 B
    --------------------------------------------------------------------
    Each survey dict *must* contain:
        accelerometer_x / y / z   (m/s²)
        inclination, toolface     (deg)
        expected_gravity          (m/s²)   ← provided by caller
        
    Parameters:
    -----------
    surveys : list
        List of dictionaries containing survey data
    ipm_data : str or object
        IPM file content as string or parsed object
    sigma : float, optional
        Sigma multiplier for tolerances, default is 3.0
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

    Gt = np.asarray([s['expected_gravity'] for s in surveys])  # m/s²
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
    
    # Try to get accelerometer terms with fallbacks for different naming conventions
    # For X/Y bias, check both with and without Z-axis correction
    σ_abx = get_error_term_value(ipm, 'ABXY-TI1S', 'e', 's') or \
            get_error_term_value(ipm, 'ABIXY-TI1S', 'e', 's') or \
            get_error_term_value(ipm, 'ABIX', 'e', 's')
    
    σ_aby = σ_abx  # Same term for both X and Y
    
    # For Z bias, check both with and without Z-axis correction
    σ_abz = get_error_term_value(ipm, 'ABZ', 'e', 's') or \
            get_error_term_value(ipm, 'ABIZ', 'e', 's')
    
    # For X/Y scale factor, check both with and without Z-axis correction
    σ_asx = get_error_term_value(ipm, 'ASXY-TI1S', 'e', 's') or \
            get_error_term_value(ipm, 'ASIXY-TI1S', 'e', 's') or \
            get_error_term_value(ipm, 'ASIX', 'e', 's')
    
    σ_asy = σ_asx  # Same term for both X and Y
    
    # For Z scale factor, check both with and without Z-axis correction
    σ_asz = get_error_term_value(ipm, 'ASZ', 'e', 's') or \
            get_error_term_value(ipm, 'ASIZ', 'e', 's')
    
    # Apply sigma multiplier to tolerances
    param_tol = (sigma*σ_abx, sigma*σ_aby, sigma*σ_abz) if use_reduced else \
                (sigma*σ_abx, sigma*σ_aby, sigma*σ_abz, sigma*σ_asx, sigma*σ_asy)
    params_valid = all(abs(x) <= t for x, t in zip(X, param_tol))

    # residual-by-station tolerance (GET formula incl. factor 2)
    if use_reduced:
        res_tol = sigma * np.sqrt((σ_abx*wx)**2 + (σ_aby*wy)**2 + (σ_abz*wz)**2)
    else:
        res_tol = sigma * np.sqrt(
            (σ_abx*wx)**2 + (σ_aby*wy)**2 + (σ_abz*wz)**2 +
            (2*σ_asx*wx*Gt)**2 + (2*σ_asy*wy*Gt)**2 + (σ_asz*wz*Gt)**2)
    
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


def perform_msat_with_corrections(surveys, ipm_data, sigma: float = 3.0):
    """
    Multi-Station Accelerometer Test (MSAT) with corrections – Ekseth et al., Appendix 1 B
    ----------------------------------------------------------------------------------
    Performs MSAT analysis and applies corrections to the survey data if the test passes.
    
    Parameters:
    -----------
    surveys : list
        List of dictionaries containing survey data with accelerometer values in m/s²
    ipm_data : str or object
        IPM file content as string or parsed object
    sigma : float, optional
        Sigma multiplier for tolerances, default is 3.0
        
    Returns:
    --------
    dict
        Standard MSAT result dict with additional 'corrected_surveys' field
    """
    # First, perform standard MSAT analysis
    msat_results = perform_msat(surveys, ipm_data, sigma)
    
    # If test is not valid, return results without corrections
    if not msat_results.get('is_valid', False):
        msat_results['corrected_surveys'] = None
        msat_results['correction_applied'] = False
        return msat_results
    
    # Extract error parameters
    measurements = msat_results.get('measurements', {})
    model_type = msat_results.get('details', {}).get('model_type', 'full')
    
    # Prepare for corrections
    corrected_surveys = []
    
    # Extract parameters based on model type
    if model_type == 'reduced':
        abx = measurements.get('ABX*', 0.0)
        aby = measurements.get('ABY*', 0.0)
        abz = measurements.get('ABZ*', 0.0)
        asx = 0.0  # Scale factors not used in reduced model
        asy = 0.0  # Scale factors not used in reduced model
    else:  # full model
        abx = measurements.get('ABX', 0.0)
        aby = measurements.get('ABY', 0.0)
        abz = measurements.get('ABZ*', 0.0)  # Note ABZ* is always lumped
        asx = measurements.get('ASX', 0.0)
        asy = measurements.get('ASY', 0.0)
    
    # Apply corrections to each survey
    for i, survey in enumerate(surveys):
        # Extract original measurements
        acc_x = survey['accelerometer_x']
        acc_y = survey['accelerometer_y']
        acc_z = survey['accelerometer_z']
        
        # Apply bias corrections
        acc_x_corr = acc_x - abx
        acc_y_corr = acc_y - aby
        acc_z_corr = acc_z - abz
        
        # Apply scale factor corrections if using full model
        if model_type == 'full':
            # Scale factors affect gravity-proportional terms
            # Scale factor correction: original / (1 + scale_error)
            acc_x_corr = acc_x_corr / (1 + asx)
            acc_y_corr = acc_y_corr / (1 + asy)
            # Z scale not corrected as it's lumped with bias in ABZ*
        
        # Calculate corrected gravity magnitude
        corrected_g = math.sqrt(acc_x_corr**2 + acc_y_corr**2 + acc_z_corr**2)
        
        # Recalculate inclination from corrected accelerometer readings
        calc_inc_corr = math.degrees(math.acos(min(max(acc_z_corr / corrected_g, -1.0), 1.0)))
        
        # Recalculate toolface from corrected readings (if inclination is sufficient)
        if calc_inc_corr >= 10.0 and calc_inc_corr <= 170.0:
            calc_tf_corr = math.degrees(math.atan2(acc_y_corr, acc_x_corr))
            # Convert to 0-360 range
            calc_tf_corr = (calc_tf_corr + 360) % 360
        else:
            # Toolface is undefined in near-vertical wells
            calc_tf_corr = None
        
        # Create corrected survey record
        corrected_surveys.append({
            'original_index': i,
            'original': {
                'accelerometer_x': acc_x,
                'accelerometer_y': acc_y,
                'accelerometer_z': acc_z,
                'gravity': math.sqrt(acc_x**2 + acc_y**2 + acc_z**2),
                'inclination': survey.get('inclination'),
                'toolface': survey.get('toolface')
            },
            'corrected': {
                'accelerometer_x': acc_x_corr,
                'accelerometer_y': acc_y_corr,
                'accelerometer_z': acc_z_corr,
                'gravity': corrected_g,
                'inclination': calc_inc_corr,
                'toolface': calc_tf_corr
            }
        })
    
    # Add corrected surveys to the results
    msat_results['corrected_surveys'] = corrected_surveys
    msat_results['correction_applied'] = True
    msat_results['correction_parameters'] = {
        'model_type': model_type,
        'abx': abx,
        'aby': aby,
        'abz': abz,
        'asx': asx if model_type == 'full' else None,
        'asy': asy if model_type == 'full' else None
    }
    
    return msat_results


# ------------------------------------------------------------------- #
# helpers
# ------------------------------------------------------------------- #
def _fail(msg):
    return {'is_valid': False, 'error': msg}