# src/calculators/sag_correction/beam_sections.py
import numpy as np

def calculate_beam_sections(
    z: np.ndarray,
    x: np.ndarray,
    ei: np.ndarray,
    dz: float
) -> dict:
    """
    Calculate beam section properties (slope, moment, shear) from deflection curve.
    
    Args:
        z: Z-coordinates
        x: Lateral positions
        ei: Bending stiffness
        dz: Grid spacing
        
    Returns:
        Dictionary with theta, moment, and shear arrays
    """
    # Calculate first derivative (slope)
    theta = np.empty_like(x)
    theta[1:-1] = (x[2:] - x[:-2]) / (2 * dz)
    theta[0] = (x[1] - x[0]) / dz
    theta[-1] = (x[-1] - x[-2]) / dz
    
    # Calculate second derivative (curvature)
    kappa = np.empty_like(x)
    kappa[1:-1] = (x[2:] - 2 * x[1:-1] + x[:-2]) / dz**2
    kappa[0] = (x[2] - 2 * x[1] + x[0]) / dz**2
    kappa[-1] = (x[-1] - 2 * x[-2] + x[-3]) / dz**2
    
    # Calculate moment and shear
    moment = ei * kappa
    shear = np.empty_like(moment)
    shear[1:-1] = (moment[2:] - moment[:-2]) / (2 * dz)
    shear[0] = (moment[1] - moment[0]) / dz
    shear[-1] = (moment[-1] - moment[-2]) / dz
    
    return {"theta": theta, "moment": moment, "shear": shear}