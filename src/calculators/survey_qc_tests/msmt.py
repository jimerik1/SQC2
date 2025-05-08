# services/qc/msmt.py
import math
import numpy as np
from src.models.qc_result import QCResult
from src.utils.ipm_parser import parse_ipm_file
from src.utils.tolerance import get_error_term_value
from src.utils.linalg import safe_inverse

def perform_msmt(surveys, ipm_data, sigma: float = 3.0):
    """
    Multi-Station Magnetometer Test (MSMT) – Ekseth et al., App. 1 F
    Each survey dict *must* include:
        mag_x / y / z         [nT]
        accelerometer_x / y / z [m/s²]
        inclination, azimuth, toolface [deg]  (toolface only used for sagged tools)
        expected_geomagnetic_field: { total_field [nT], dip [deg] }
        
    Parameters:
    -----------
    surveys : list
        List of dictionaries containing survey data
    ipm_data : str or object
        IPM file content as string or parsed object
    sigma : float, optional
        Sigma multiplier for tolerances, default is 3.0
    """
    if len(surveys) < 10:
        return _fail("At least 10 survey stations are required for MSMT")

    # ------------------------------------------------------------------ #
    #   1. Build combined error vector (ΔB  and  Bt · ΔΘ)
    # ------------------------------------------------------------------ #
    field_err, dip_err, Bt_list = [], [], []
    for sv in surveys:
        Bt = sv['expected_geomagnetic_field']['total_field']
        dip_t = sv['expected_geomagnetic_field']['dip']          # deg

        bx, by, bz = sv['mag_x'], sv['mag_y'], sv['mag_z']
        B_meas = math.sqrt(bx*bx + by*by + bz*bz)

        gx, gy, gz = sv['accelerometer_x'], sv['accelerometer_y'], sv['accelerometer_z']
        g_norm = math.sqrt(gx*gx + gy*gy + gz*gz)
        dip_meas = math.degrees(math.asin((bx*gx + by*gy + bz*gz) / (g_norm * B_meas)))

        field_err.append(B_meas - Bt)
        dip_err.append(dip_meas - dip_t)
        Bt_list.append(Bt)

    comb_err = np.empty(2*len(surveys))
    comb_err[0::2] = field_err
    comb_err[1::2] = np.multiply(Bt_list, dip_err)          # Bt·ΔΘ

    # ------------------------------------------------------------------ #
    #   2. Design matrix  (MBX, MBY, MBZ, MSX, MSY, MSZ)
    # ------------------------------------------------------------------ #
    A = np.zeros((2*len(surveys), 6))

    for idx, sv in enumerate(surveys):
        bx, by, bz = sv['mag_x'], sv['mag_y'], sv['mag_z']
        B = math.sqrt(bx*bx + by*by + bz*bz)
        nx, ny, nz = bx/B, by/B, bz/B

        Bt = Bt_list[idx]
        dip_rad = math.radians(sv['expected_geomagnetic_field']['dip'])

        # ----- total-field row ----------------------------------------
        r = 2*idx
        A[r, 0:3] = [nx, ny, nz]
        A[r, 3:]  = [2*nx*Bt, 2*ny*Bt, 2*nz*Bt]     # factor 2

        # ----- dip row -------------------------------------------------
        r += 1
        gx, gy, gz = sv['accelerometer_x'], sv['accelerometer_y'], sv['accelerometer_z']
        g_norm = math.sqrt(gx*gx + gy*gy + gz*gz)
        kx, ky, kz = gx/g_norm, gy/g_norm, gz/g_norm

        cosd, sind = math.cos(dip_rad), math.sin(dip_rad)
        wx = (kx*cosd - nx*sind) / cosd
        wy = (ky*cosd - ny*sind) / cosd
        wz = (kz*cosd - nz*sind) / cosd

        A[r, 0:3] = [wx, wy, wz]
        A[r, 3:]  = [2*wx*Bt, 2*wy*Bt, 2*wz*Bt]     # factor 2

    # ------------------------------------------------------------------ #
    #   3. Least-squares solution
    # ------------------------------------------------------------------ #
    X, *_ = np.linalg.lstsq(A, comb_err, rcond=None)   # MB/ MS vector
    residuals = comb_err - A @ X

    try:
        cof = safe_inverse(A.T @ A)
    except np.linalg.LinAlgError as exc:
        return _fail(str(exc))
    
    corr = cof / np.sqrt(np.outer(np.diag(cof), np.diag(cof)))
    max_corr = np.abs(corr - np.eye(6)).max()

    # ------------------------------------------------------------------ #
    #   4. Tolerances from IPM
    # ------------------------------------------------------------------ #
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    
    # Try to get magnetometer terms with fallbacks for different naming conventions
    σ_mbx = get_error_term_value(ipm, 'MBX', 'e', 's') or \
            get_error_term_value(ipm, 'MBIX', 'e', 's') or \
            get_error_term_value(ipm, 'MBXY-TI1S', 'e', 's') or \
            get_error_term_value(ipm, 'MBIXY-TI1S', 'e', 's')
    
    σ_mby = get_error_term_value(ipm, 'MBY', 'e', 's') or \
            get_error_term_value(ipm, 'MBIY', 'e', 's') or \
            get_error_term_value(ipm, 'MBXY-TI1S', 'e', 's') or \
            get_error_term_value(ipm, 'MBIXY-TI1S', 'e', 's')
    
    σ_mbz = get_error_term_value(ipm, 'MBZ', 'e', 's') or \
            get_error_term_value(ipm, 'MBIZ', 'e', 's')
    
    σ_msx = get_error_term_value(ipm, 'MSX', 'e', 's') or \
            get_error_term_value(ipm, 'MSIX', 'e', 's') or \
            get_error_term_value(ipm, 'MSXY-TI1S', 'e', 's') or \
            get_error_term_value(ipm, 'MSIXY-TI1S', 'e', 's')
    
    σ_msy = get_error_term_value(ipm, 'MSY', 'e', 's') or \
            get_error_term_value(ipm, 'MSIY', 'e', 's') or \
            get_error_term_value(ipm, 'MSXY-TI1S', 'e', 's') or \
            get_error_term_value(ipm, 'MSIXY-TI1S', 'e', 's')
    
    σ_msz = get_error_term_value(ipm, 'MSZ', 'e', 's') or \
            get_error_term_value(ipm, 'MSIZ', 'e', 's')
    
    σ_mfi = get_error_term_value(ipm, 'MFI', 'e', 's')
    σ_mdi = get_error_term_value(ipm, 'MDI', 'e', 's')

    # Apply sigma multiplier to tolerances
    param_tol = (sigma*σ_mbx, sigma*σ_mby, sigma*σ_mbz, 
                 sigma*σ_msx, sigma*σ_msy, sigma*σ_msz)
    params_valid = all(abs(p) <= t for p, t in zip(X, param_tol))

    # residual tolerances station-by-station
    res_tol, row = [], 0
    for Bt, sv in zip(Bt_list, surveys):
        # total-field row
        nx, ny, nz = [c/math.sqrt(sv['mag_x']**2 + sv['mag_y']**2 + sv['mag_z']**2)
                      for c in (sv['mag_x'], sv['mag_y'], sv['mag_z'])]

        tf_tol = sigma*math.sqrt(
            (σ_mbx*nx)**2 + (σ_mby*ny)**2 + (σ_mbz*nz)**2 +
            (2*σ_msx*nx*Bt)**2 + (2*σ_msy*ny*Bt)**2 + (2*σ_msz*nz*Bt)**2 +
            (σ_mfi*Bt)**2
        )
        res_tol.append(tf_tol); row += 1

        # dip row
        dip_rad = math.radians(sv['expected_geomagnetic_field']['dip'])
        g_norm = math.sqrt(sv['accelerometer_x']**2 +
                           sv['accelerometer_y']**2 +
                           sv['accelerometer_z']**2)
        kx, ky, kz = (sv['accelerometer_x']/g_norm,
                      sv['accelerometer_y']/g_norm,
                      sv['accelerometer_z']/g_norm)
        cosd, sind = math.cos(dip_rad), math.sin(dip_rad)
        wx = (kx*cosd - nx*sind) / cosd
        wy = (ky*cosd - ny*sind) / cosd
        wz = (kz*cosd - nz*sind) / cosd

        dp_tol = sigma*math.sqrt(
            (σ_mbx*wx)**2 + (σ_mby*wy)**2 + (σ_mbz*wz)**2 +
            (2*σ_msx*wx*Bt)**2 + (2*σ_msy*wy*Bt)**2 + (2*σ_msz*wz*Bt)**2 +
            σ_mdi**2
        )
        res_tol.append(Bt*dp_tol); row += 1

    residuals_valid = np.all(np.abs(residuals) <= res_tol)
    overall = params_valid and residuals_valid and max_corr <= 0.4

    # ------------------------------------------------------------------ #
    #   5. QCResult
    # ------------------------------------------------------------------ #
    r = QCResult("MSMT")
    r.set_validity(overall)

    for name, val, tol in zip(['MBX','MBY','MBZ','MSX','MSY','MSZ'],
                               X, param_tol):
        r.add_measurement(name, float(val))
        r.add_tolerance(name, tol)

    r.add_detail("field_residuals", residuals[0::2].tolist())
    r.add_detail("dip_residuals",   residuals[1::2].tolist())
    r.add_detail("field_tolerances", res_tol[0::2])
    r.add_detail("dip_tolerances",   [rt/Bt for rt, Bt in zip(res_tol[1::2], Bt_list)])
    r.add_detail("correlation_matrix", corr.tolist())
    r.add_detail("max_nondiagonal_correlation", float(max_corr))
    r.add_detail("sigma", sigma)

    if not overall:
        if max_corr > 0.4:
            r.add_detail("failure_reason", "High parameter correlations")
        elif not params_valid:
            r.add_detail("failure_reason", "Parameter estimate exceeds tolerance")
        else:
            r.add_detail("failure_reason", "Residual error exceeds tolerance")

    return r.to_dict()


# ------------------------------------------------------------------ #
# helpers
# ------------------------------------------------------------------ #
def _fail(msg):
    return {'is_valid': False, 'error': msg}