# services/qc/rsmt.py
import math
import numpy as np
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

def perform_rsmt(surveys, ipm_data):
    """
    Performs Rotation-Shot Misalignment Test (RSMT) on a set of survey measurements
    
    Args:
        surveys (list): List of survey station data dictionaries, each containing:
            - inclination: Survey inclination (degrees)
            - toolface: Survey toolface (degrees)
            Each survey should be taken at the same depth but with different toolfaces
            
        ipm_data (dict): Instrument Performance Model data containing error terms
        
    Returns:
        dict: QC test results with:
            - is_valid: Boolean indicating if survey passed the test
            - misalignment_mx: X component of toolface-dependent misalignment (degrees)
            - misalignment_my: Y component of toolface-dependent misalignment (degrees)
            - mx_tolerance: Tolerance for X misalignment (degrees)
            - my_tolerance: Tolerance for Y misalignment (degrees)
            - correlation: Correlation coefficient between MX and MY estimations
            - details: Additional test details
    """
    # Check if we have enough measurements with enough toolface variation
    if len(surveys) < 5:
        return {
            'is_valid': False,
            'error': "At least 5 rotation-shot measurements are required for RSMT"
        }
    
    # Extract inclinations and toolfaces from surveys
    inclinations = [survey['inclination'] for survey in surveys]
    toolfaces = [survey['toolface'] for survey in surveys]
    
    # Check if the inclination is sufficient (RSMT doesn't work well near vertical)
    first_inc = inclinations[0]
    if first_inc < 5.0:
        return {
            'is_valid': False,
            'error': "RSMT is not reliable for inclinations less than 5 degrees"
        }
    
    # Check toolface distribution (should cover at least 3 quadrants)
    # Count measurements in each quadrant
    quadrants = [0, 0, 0, 0]  # Q1: 0-90, Q2: 90-180, Q3: 180-270, Q4: 270-360
    for tf in toolfaces:
        quadrant = int(tf / 90)
        if quadrant == 4:  # Handle 360 degrees case
            quadrant = 0
        quadrants[quadrant] += 1
    
    # Count how many quadrants have measurements
    quadrant_count = sum(1 for q in quadrants if q > 0)
    if quadrant_count < 3:
        return {
            'is_valid': False,
            'error': "RSMT requires toolfaces distributed across at least 3 quadrants"
        }
    
    # Construct the design matrix and observations vector for least squares
    A = []  # Design matrix
    b = []  # Observations vector (inclination differences)
    
    # Use first survey as reference
    ref_inc = inclinations[0]
    ref_tf = toolfaces[0]
    
    for i in range(1, len(surveys)):
        inc = inclinations[i]
        tf = toolfaces[i]
        
        # Calculate inclination difference
        inc_diff = inc - ref_inc
        
        # Get coefficients for the design matrix
        tf_rad = math.radians(tf)
        ref_tf_rad = math.radians(ref_tf)
        
        # Equation: ΔΔI = MX * (cos(αi) - cos(α0)) + MY * (sin(αi) - sin(α0))
        # Where αi is the toolface of measurement i, α0 is the reference toolface
        coef_mx = math.cos(tf_rad) - math.cos(ref_tf_rad)
        coef_my = math.sin(tf_rad) - math.sin(ref_tf_rad)
        
        A.append([coef_mx, coef_my])
        b.append(inc_diff)
    
    # Convert to numpy arrays for matrix operations
    A = np.array(A)
    b = np.array(b)
    
    # Calculate misalignment parameters using least squares: (A^T * A)^(-1) * A^T * b
    try:
        AT_A = np.dot(A.T, A)
        AT_A_inv = np.linalg.inv(AT_A)
        AT_b = np.dot(A.T, b)
        misalignment = np.dot(AT_A_inv, AT_b)
        
        # Extract misalignment components
        mx = misalignment[0]
        my = misalignment[1]
        
        # Calculate correlation coefficient
        Q = AT_A_inv  # Cofactor matrix
        corr_coef = Q[0, 1] / (math.sqrt(Q[0, 0]) * math.sqrt(Q[1, 1]))
        
        # Check if correlation coefficient is within acceptable range
        if abs(corr_coef) > 0.4:
            return {
                'is_valid': False,
                'error': f"High correlation between MX and MY ({corr_coef:.2f}). Need better toolface distribution."
            }
        
        # Calculate residuals
        v = np.dot(A, misalignment) - b
        
        # Calculate tolerances
        mx_tolerance, my_tolerance = calculate_rsmt_tolerances(ipm_data)
        
        # Determine if misalignments are within tolerance
        is_mx_valid = abs(mx) <= mx_tolerance
        is_my_valid = abs(my) <= my_tolerance
        is_valid = is_mx_valid and is_my_valid
        
        # Create result
        result = QCResult("RSMT")
        result.set_validity(is_valid)
        result.add_measurement("misalignment_mx", mx)
        result.add_measurement("misalignment_my", my)
        result.add_tolerance("mx", mx_tolerance)
        result.add_tolerance("my", my_tolerance)
        result.add_detail("correlation", corr_coef)
        result.add_detail("is_mx_valid", is_mx_valid)
        result.add_detail("is_my_valid", is_my_valid)
        result.add_detail("residuals", v.tolist())
        result.add_detail("inclination", first_inc)
        result.add_detail("quadrant_distribution", quadrants)
        
        return result.to_dict()
        
    except np.linalg.LinAlgError:
        # Matrix inversion failed
        return {
            'is_valid': False,
            'error': "Matrix inversion failed. Measurement geometry is likely poor."
        }

def calculate_rsmt_tolerances(ipm_data):
    """
    Calculate tolerances for the RSMT test
    
    Args:
        ipm_data (dict): IPM data containing misalignment error terms
        
    Returns:
        tuple: (mx_tolerance, my_tolerance) in degrees
    """
    # Parse IPM if it's string content
    if isinstance(ipm_data, str):
        ipm = parse_ipm_file(ipm_data)
    else:
        ipm = ipm_data
    
    # Get misalignment error terms from IPM
    mx_sigma = get_error_term_value(ipm, 'MX', 'e', 's')
    my_sigma = get_error_term_value(ipm, 'MY', 'e', 's')
    
    # Calculate 3-sigma tolerances
    mx_tolerance = 3 * mx_sigma
    my_tolerance = 3 * my_sigma
    
    return mx_tolerance, my_tolerance
