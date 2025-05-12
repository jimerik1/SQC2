import math
from typing import List, Dict, Any, Tuple, Optional, Union

import numpy as np

from src.models.qc_result import QCResult
from src.utils.ipm_parser import parse_ipm_file
from src.utils.tolerance import get_error_term_value
from src.utils.linalg import safe_inverse

###############################################################################
# Helper utilities
###############################################################################

def _norm(vec: Tuple[float, float, float]) -> float:
    """Return Euclidean norm of a 3-vector."""
    x, y, z = vec
    return math.sqrt(x * x + y * y + z * z)


def _unit(vec: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Return unit vector; raises ValueError if ‖vec‖ ≈ 0."""
    n = _norm(vec)
    if n < 1e-9:
        raise ValueError("Zero-length vector encountered")
    return vec[0] / n, vec[1] / n, vec[2] / n


def _validate_accel(ax: float, ay: float, az: float) -> None:
    """Ensure accelerometer magnitude is within a plausible gravity band (7-12 m/s²)."""
    g = _norm((ax, ay, az))
    if not (7.0 <= g <= 12.0):
        raise ValueError(
            f"Accelerometer magnitude {g:.2f} m/s² outside 7-12 m/s²; "
            "did you supply g-units instead of m/s²?"
        )

# Add this function to msmt.py to reduce the condition number
def _reduce_condition_number(A: np.ndarray, threshold: float = 1e15) -> np.ndarray:
    """Apply Tikhonov regularization to improve the condition number of matrix A."""
    # First check unmodified condition number
    try:
        cond = np.linalg.cond(A)
        if cond < threshold:
            return A  # Already well-conditioned
            
        # Apply regularization
        ATA = A.T @ A
        n = ATA.shape[0]
        # Start with a small regularization parameter
        alpha = 1e-8
        
        # Gradually increase regularization until condition number is acceptable
        for _ in range(10):  # Try up to 10 times
            reg_matrix = ATA + alpha * np.eye(n)
            if np.linalg.cond(reg_matrix) < threshold:
                # Create regularized pseudoinverse
                return np.linalg.inv(reg_matrix) @ A.T
            alpha *= 10  # Increase regularization
            
        # If we get here, return best attempt
        return np.linalg.inv(ATA + alpha * np.eye(n)) @ A.T
    except:
        # Fallback to standard pseudoinverse with warnings disabled
        with np.errstate(all='ignore'):
            return np.linalg.pinv(A)


def _safe_asin(x: float) -> float:
    """Safely compute arcsin, clamping input to [-1, 1] to avoid math domain errors."""
    return math.asin(max(-1.0, min(1.0, x)))


# map canonical σ-terms to alias lists seen in various IPM revisions
_SIGMA_ALIASES: Dict[str, Tuple[str, ...]] = {
    "MBX": (
        "MBX",
        "MBIX",
        "MBXY-TI1S",
        "MBXY-TI2S",
        "MBXY-TI3S",
        "MBIXY-TI1S",
        "MBIXY-TI2S",
        "MBIXY-TI3S",
    ),
    "MBY": (
        "MBY",
        "MBIY",
        "MBXY-TI1S",
        "MBXY-TI2S",
        "MBXY-TI3S",
        "MBIXY-TI1S",
        "MBIXY-TI2S",
        "MBIXY-TI3S",
    ),
    "MBZ": ("MBZ", "MBIZ", "MBZ-TI1S"),
    "MSX": (
        "MSX",
        "MSIX",
        "MSXY-TI1S",
        "MSXY-TI2S",
        "MSXY-TI3S",
        "MSIXY-TI1S",
        "MSIXY-TI2S",
        "MSIXY-TI3S",
    ),
    "MSY": (
        "MSY",
        "MSIY",
        "MSXY-TI1S",
        "MSXY-TI2S",
        "MSXY-TI3S",
        "MSIXY-TI1S",
        "MSIXY-TI2S",
        "MSIXY-TI3S",
    ),
    "MSZ": ("MSZ", "MSIZ", "MSZ-TI1S"),
    "MFI": (
        "MFI",
        "MFI-U",
        "MFI-CH",
        "MFI-OH",
        "MFI-OI",
        "MFIR",
    ),
    "MDI": (
        "MDI",
        "MDI-U",
        "MDI-CH",
        "MDI-OH",
        "MDI-OI",
        "MDIR",
    ),
}


def _require_sigma(ipm: Dict[str, Any], canonical: str) -> float:
    """Return σ value for *canonical* term; raise if not present."""
    for alias in _SIGMA_ALIASES[canonical]:
        val = get_error_term_value(ipm, alias, "e", "s")
        if val is not None:
            return float(val)
    raise ValueError(f"Required IPM term '{canonical}' (aliases: {_SIGMA_ALIASES[canonical]}) not found")


###############################################################################
# Main entry point
###############################################################################

def perform_msmt(surveys: List[Dict[str, Any]], ipm_data: Any, *, sigma: float = 3.0) -> Dict[str, Any]:
    """Multi-Station Magnetometer Test (Ekseth 2006 App 1 F)."""
    if len(surveys) < 10:
        return {"is_valid": False, "error": "At least 10 survey stations are required for MSMT"}

    # Parse IPM parameters
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    
    try:
        σ_mbx = _require_sigma(ipm, "MBX")
        σ_mby = _require_sigma(ipm, "MBY")
        σ_mbz = _require_sigma(ipm, "MBZ")
        σ_msx = _require_sigma(ipm, "MSX")
        σ_msy = _require_sigma(ipm, "MSY")
        σ_msz = _require_sigma(ipm, "MSZ")
        σ_mfi = _require_sigma(ipm, "MFI")
        σ_mdi = _require_sigma(ipm, "MDI")
    except ValueError as e:
        return {"is_valid": False, "error": str(e)}

    # Parameter tolerances
    param_tol = sigma * np.array([σ_mbx, σ_mby, σ_mbz, σ_msx, σ_msy, σ_msz])

    # Build combined error vector (magnetic field and dip errors)
    n = len(surveys)
    ΔBΘ = np.zeros(2 * n)  # Combined field and dip errors
    Bt_list = []
    
    # Pre-calculate measured field magnitudes and unit vectors
    B_meas_list = []
    unit_vectors = []
    grav_vectors = []
    
    # Calculate reference data first to prevent potential calculation inconsistencies
    for i, sv in enumerate(surveys):
        try:
            # Validate accelerometer magnitude
            ax, ay, az = sv["accelerometer_x"], sv["accelerometer_y"], sv["accelerometer_z"]
            g_mag = math.sqrt(ax*ax + ay*ay + az*az)
            if not (7.0 <= g_mag <= 12.0):
                return {"is_valid": False, "error": f"Accelerometer magnitude {g_mag:.2f} m/s² at station {i} outside 7-12 m/s²"}
            
            # Calculate unit gravity vector
            grav_vectors.append((ax/g_mag, ay/g_mag, az/g_mag))
            
            # Get mag field measurements
            bx, by, bz = sv["mag_x"], sv["mag_y"], sv["mag_z"]
            B_meas = math.sqrt(bx*bx + by*by + bz*bz)
            B_meas_list.append(B_meas)
            
            # Calculate unit mag vector
            unit_vectors.append((bx/B_meas, by/B_meas, bz/B_meas))
            
            # Get expected field
            Bt = sv["expected_geomagnetic_field"]["total_field"]
            Bt_list.append(Bt)
        except Exception as e:
            return {"is_valid": False, "error": f"Error preprocessing station {i}: {str(e)}"}
    
    # Build design matrix according to Appendix 1F
    A = np.zeros((2*n, 6))
    
    for i, sv in enumerate(surveys):
        # Get expected values 
        Bt = Bt_list[i]
        dip_t = sv["expected_geomagnetic_field"]["dip"]
        
        # Get measured values
        B_meas = B_meas_list[i]
        bx, by, bz = sv["mag_x"], sv["mag_y"], sv["mag_z"]
        
        # Unit vectors
        nx, ny, nz = unit_vectors[i]
        kx, ky, kz = grav_vectors[i]
        
        # Calculate measured dip (dot product of unit vectors)
        dot_product = nx*kx + ny*ky + nz*kz
        # Safely clamp to [-1,1] range to avoid domain errors
        dot_product = max(-1.0, min(1.0, dot_product))
        dip_meas = math.degrees(math.asin(dot_product))
        
        # Errors to solve for
        field_err = B_meas - Bt
        dip_err = dip_meas - dip_t
        
        # Store in combined error vector
        ΔBΘ[2*i] = field_err
        ΔBΘ[2*i+1] = Bt * dip_err  # Scale to match field magnitude
        
        # Calculate design matrix coefficients as per Appendix 1E/1F
        # Field row - exactly as per Appendix 1E
        A[2*i, 0] = bx/B_meas  # nx = bx/B
        A[2*i, 1] = by/B_meas  # ny = by/B
        A[2*i, 2] = bz/B_meas  # nz = bz/B
        A[2*i, 3] = bx*bx/B_meas  # 2*MSX term simplified
        A[2*i, 4] = by*by/B_meas  # 2*MSY term simplified
        A[2*i, 5] = bz*bz/B_meas  # 2*MSZ term simplified
        
        # Dip row - calculate wx, wy, wz as per Appendix 1E
        dip_rad = math.radians(dip_t)
        cosd = max(math.cos(dip_rad), 1e-4)  # Safety factor for vertical fields
        sind = math.sin(dip_rad)
        
        # Calculate terms as per paper
        wx = (kx * cosd - nx * sind) / cosd
        wy = (ky * cosd - ny * sind) / cosd
        wz = (kz * cosd - nz * sind) / cosd
        
        A[2*i+1, 0] = wx
        A[2*i+1, 1] = wy
        A[2*i+1, 2] = wz
        A[2*i+1, 3] = wx * Bt  # Bt factor to normalize scale with field row
        A[2*i+1, 4] = wy * Bt
        A[2*i+1, 5] = wz * Bt
    
    # Check condition number
    try:
        cond_num = np.linalg.cond(A)
        if cond_num > 1e15:
            # Apply regularization to improve condition number
            alpha = 1e-8 * np.trace(A.T @ A) / A.shape[1]
            ATA_reg = A.T @ A + alpha * np.eye(A.shape[1])
            X = np.linalg.solve(ATA_reg, A.T @ ΔBΘ)
        else:
            # Solve system normally
            X = np.linalg.lstsq(A, ΔBΘ, rcond=None)[0]
    except np.linalg.LinAlgError:
        return {"is_valid": False, "error": "Linear algebra error in least squares solution"}
    
    # Calculate residuals
    residuals = ΔBΘ - A @ X
    
    # Calculate correlation matrix
    try:
        ATA_inv = np.linalg.inv(A.T @ A + 1e-10 * np.eye(A.shape[1]))  # Add tiny regularization
        std = np.sqrt(np.diag(ATA_inv))
        
        # Calculate correlation matrix safely
        with np.errstate(divide="ignore", invalid="ignore"):
            corr = ATA_inv / np.outer(std, std)
        
        # Fix any NaN values in correlation matrix
        corr = np.nan_to_num(corr, nan=0.0)
        np.fill_diagonal(corr, 1.0)
        max_corr = np.max(np.abs(corr - np.eye(6)))
    except np.linalg.LinAlgError:
        return {"is_valid": False, "error": "Error calculating correlation matrix"}
    
    # Tolerance check for parameters
    params_valid = np.all(np.abs(X) <= param_tol)
    
    # Calculate residual tolerances (per Appendix 1F)
    res_tol = []
    for i, (Bt, sv) in enumerate(zip(Bt_list, surveys)):
        bx, by, bz = sv["mag_x"], sv["mag_y"], sv["mag_z"]
        B = math.sqrt(bx*bx + by*by + bz*bz)
        nx, ny, nz = bx/B, by/B, bz/B
        
        # Total field tolerance - from paper
        tf_tol = sigma * math.sqrt(
            (σ_mbx * nx) ** 2 +
            (σ_mby * ny) ** 2 +
            (σ_mbz * nz) ** 2 +
            (σ_msx * nx * Bt) ** 2 +
            (σ_msy * ny * Bt) ** 2 +
            (σ_msz * nz * Bt) ** 2 +
            σ_mfi ** 2
        )
        res_tol.append(tf_tol)
        
        # Dip tolerance
        dip_rad = math.radians(sv["expected_geomagnetic_field"]["dip"])
        cosd = max(math.cos(dip_rad), 1e-4)
        sind = math.sin(dip_rad)
        
        # Calculate gravity unit vector
        g = math.sqrt(sv["accelerometer_x"]**2 + sv["accelerometer_y"]**2 + sv["accelerometer_z"]**2)
        kx = sv["accelerometer_x"] / g
        ky = sv["accelerometer_y"] / g
        kz = sv["accelerometer_z"] / g
        
        # Calculate weighting terms
        wx = (kx * cosd - nx * sind) / cosd
        wy = (ky * cosd - ny * sind) / cosd
        wz = (kz * cosd - nz * sind) / cosd
        
        # Dip tolerance (scaled by Bt)
        dp_tol = sigma * math.sqrt(
            (σ_mbx * wx) ** 2 +
            (σ_mby * wy) ** 2 +
            (σ_mbz * wz) ** 2 +
            (σ_msx * wx * Bt) ** 2 +
            (σ_msy * wy * Bt) ** 2 +
            (σ_msz * wz * Bt) ** 2 +
            σ_mdi ** 2
        )
        res_tol.append(Bt * dp_tol)
    
    # Check residual validity
    residuals_valid = np.all(np.abs(residuals) <= res_tol)
    
    # Final validity check
    overall_valid = params_valid and residuals_valid and max_corr <= 0.4
    
    # Prepare result
    qc = QCResult("MSMT")
    qc.set_validity(overall_valid)
    
    # Add measurements and tolerances
    for name, val, tol in zip(
        ["MBX", "MBY", "MBZ", "MSX", "MSY", "MSZ"], X, param_tol
    ):
        qc.add_measurement(name, float(val))
        qc.add_tolerance(name, float(tol))
    
    # Add details
    qc.add_detail("field_residuals", residuals[0::2].tolist())
    qc.add_detail("dip_residuals", residuals[1::2].tolist())
    qc.add_detail("field_tolerances", res_tol[0::2])
    qc.add_detail("dip_tolerances", [rt / Bt for rt, Bt in zip(res_tol[1::2], Bt_list)])
    qc.add_detail("correlation_matrix", corr.tolist())
    qc.add_detail("max_nondiagonal_correlation", float(max_corr))
    qc.add_detail("sigma", sigma)
    
    # Provide failure reason if applicable
    if not overall_valid:
        if max_corr > 0.4:
            qc.add_detail("failure_reason", "High parameter correlations > 0.4")
        elif not params_valid:
            qc.add_detail("failure_reason", "Parameter estimate exceeds tolerance")
        else:
            qc.add_detail("failure_reason", "Residual error exceeds tolerance")
    
    return qc.to_dict()
