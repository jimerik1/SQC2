# services/qc/msat.py
import math
import numpy as np
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

def perform_msat(surveys, ipm_data):
    """
    Performs Multi-Station Accelerometer Test (MSAT) on a set of survey measurements
    
    Args:
        surveys (list): List of survey dictionaries containing:
            - accelerometer_x, accelerometer_y, accelerometer_z: Accelerometer measurements (g)
            - inclination: Survey inclination (degrees)
            - toolface: Survey toolface (degrees)
            - depth: Measured depth (m)
            - latitude: Survey location latitude (degrees)
        
        ipm_data (dict): Instrument Performance Model data containing error terms
        
    Returns:
        dict: QC test results with:
            - is_valid: Boolean indicating if surveys passed the test
            - accelerometer_errors: Estimated accelerometer error parameters
            - residuals: Residual gravity errors per station
            - correlations: Correlation coefficients between error parameters
            - details: Additional test details
    """
    # Verify if we have enough surveys with sufficient variation
    if len(surveys) < 10:
        return {
            'is_valid': False,
            'error': "At least 10 survey stations are required for MSAT"
        }
    
    # Extract inclinations and toolfaces
    inclinations = [math.radians(survey['inclination']) for survey in surveys]
    toolfaces = [math.radians(survey['toolface']) for survey in surveys]
    
    # Check inclination and toolface variation
    inc_variation = max(inclinations) - min(inclinations)
    tf_quadrants = [0, 0, 0, 0]  # Q1: 0-90, Q2: 90-180, Q3: 180-270, Q4: 270-360
    
    for tf in [math.degrees(tf) % 360 for tf in toolfaces]:
        quadrant = int(tf / 90)
        tf_quadrants[quadrant] += 1
    
    quadrant_count = sum(1 for q in tf_quadrants if q > 0)
    
    # Decide which model to use based on variation
    use_reduced_model = inc_variation < math.radians(45) or quadrant_count < 3
    
    # Calculate gravity errors for each station
    gravity_errors = []
    for survey in surveys:
        acc_x = survey['accelerometer_x']
        acc_y = survey['accelerometer_y']
        acc_z = survey['accelerometer_z']
        
        # Calculate measured gravity
        measured_gravity = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
        
        # Calculate theoretical gravity
        depth = survey['depth']
        latitude = survey['latitude']
        theoretical_gravity = calculate_theoretical_gravity(latitude, depth)
        
        # Calculate gravity error
        gravity_error = measured_gravity - theoretical_gravity
        gravity_errors.append(gravity_error)
    
    # Create design matrix
    if use_reduced_model:
        # Reduced model with 3 parameters (lumped x, lumped y, lumped z)
        A = np.zeros((len(surveys), 3))
        for i, (survey, inc, tf) in enumerate(zip(surveys, inclinations, toolfaces)):
            # Weighting functions for reduced model
            wx = math.sin(inc) * math.sin(tf)
            wy = math.sin(inc) * math.cos(tf)
            wz = math.cos(inc)
            
            A[i, 0] = wx  # Lumped x effect
            A[i, 1] = wy  # Lumped y effect
            A[i, 2] = wz  # Lumped z effect
    else:
        # Full model with 5 parameters
        A = np.zeros((len(surveys), 5))
        for i, (survey, inc, tf) in enumerate(zip(surveys, inclinations, toolfaces)):
            # Weighting functions for full model
            wx = math.sin(inc) * math.sin(tf)
            wy = math.sin(inc) * math.cos(tf)
            wz = math.cos(inc)
            
            Gt = calculate_theoretical_gravity(survey['latitude'], survey['depth'])
            
            A[i, 0] = wx  # ABX
            A[i, 1] = wy  # ABY
            A[i, 2] = wz  # ABZ*
            A[i, 3] = wx * Gt  # ASX
            A[i, 4] = wy * Gt  # ASY
    
    # Solve the least squares problem
    gravity_errors_array = np.array(gravity_errors)
    
    try:
        # Calculate (A^T * A)^-1
        AT_A = np.dot(A.T, A)
        AT_A_inv = np.linalg.inv(AT_A)
        
        # Calculate A^T * ΔG
        AT_g = np.dot(A.T, gravity_errors_array)
        
        # Calculate parameter vector X
        X = np.dot(AT_A_inv, AT_g)
        
        # Calculate residuals
        residuals = gravity_errors_array - np.dot(A, X)
        
        # Calculate correlation coefficients
        corr_matrix = np.zeros_like(AT_A_inv)
        for i in range(AT_A_inv.shape[0]):
            for j in range(AT_A_inv.shape[1]):
                corr_matrix[i, j] = AT_A_inv[i, j] / math.sqrt(AT_A_inv[i, i] * AT_A_inv[j, j])
        
        # Check correlations
        max_nondiag_corr = 0
        for i in range(corr_matrix.shape[0]):
            for j in range(corr_matrix.shape[1]):
                if i != j:
                    max_nondiag_corr = max(max_nondiag_corr, abs(corr_matrix[i, j]))
        
        # Parse IPM if it's string content
        if isinstance(ipm_data, str):
            ipm = parse_ipm_file(ipm_data)
        else:
            ipm = ipm_data
        
        # Get accelerometer error terms from IPM
        abx_sigma = get_error_term_value(ipm, 'ABXY-TI1S', 'e', 's')
        aby_sigma = get_error_term_value(ipm, 'ABXY-TI1S', 'e', 's')
        abz_sigma = get_error_term_value(ipm, 'ABZ', 'e', 's')
        asx_sigma = get_error_term_value(ipm, 'ASXY-TI1S', 'e', 's')
        asy_sigma = get_error_term_value(ipm, 'ASXY-TI1S', 'e', 's')
        asz_sigma = get_error_term_value(ipm, 'ASZ', 'e', 's')
        
        # Calculate tolerances for each parameter
        if use_reduced_model:
            param_names = ['ABX*', 'ABY*', 'ABZ*']
            param_tolerances = [3 * abx_sigma, 3 * aby_sigma, 3 * abz_sigma]
        else:
            param_names = ['ABX', 'ABY', 'ABZ*', 'ASX', 'ASY']
            param_tolerances = [3 * abx_sigma, 3 * aby_sigma, 3 * abz_sigma, 
                              3 * asx_sigma, 3 * asy_sigma]
        
        # Check if parameters are within tolerances
        params_valid = all(abs(X[i]) <= param_tolerances[i] for i in range(len(X)))
        
        # Calculate tolerance for residuals at each station
        residual_tolerances = []
        for i, survey in enumerate(surveys):
            inc = math.radians(survey['inclination'])
            tf = math.radians(survey['toolface'])
            
            # Weighting functions
            wx = math.sin(inc) * math.sin(tf)
            wy = math.sin(inc) * math.cos(tf)
            wz = math.cos(inc)
            
            Gt = calculate_theoretical_gravity(survey['latitude'], survey['depth'])
            
            # Calculate tolerance for this station using GET formula
            tolerance = 3 * math.sqrt(
                (abx_sigma * wx)**2 + 
                (aby_sigma * wy)**2 + 
                (abz_sigma * wz)**2 + 
                (asx_sigma * wx * Gt)**2 + 
                (asy_sigma * wy * Gt)**2 + 
                (asz_sigma * wz * Gt)**2
            )
            
            residual_tolerances.append(tolerance)
        
        # Check if residuals are within tolerances
        residuals_valid = all(abs(residuals[i]) <= residual_tolerances[i] for i in range(len(residuals)))
        
        # Overall test validity
        is_valid = params_valid and residuals_valid and max_nondiag_corr <= 0.4
        
        # Create result
        result = QCResult("MSAT")
        result.set_validity(is_valid)
        
        # Add parameter estimates
        for i, name in enumerate(param_names):
            result.add_measurement(name, float(X[i]))
            result.add_tolerance(name, param_tolerances[i])
        
        # Add residuals
        result.add_detail("residuals", residuals.tolist())
        result.add_detail("residual_tolerances", residual_tolerances)
        
        # Add correlation info
        result.add_detail("correlation_matrix", corr_matrix.tolist())
        result.add_detail("max_nondiagonal_correlation", float(max_nondiag_corr))
        
        # Add model info
        result.add_detail("model_type", "reduced" if use_reduced_model else "full")
        result.add_detail("inclination_variation_degrees", math.degrees(inc_variation))
        result.add_detail("quadrant_distribution", tf_quadrants)
        
        if not is_valid:
            if max_nondiag_corr > 0.4:
                result.add_detail("failure_reason", "High parameter correlations detected")
            elif not params_valid:
                result.add_detail("failure_reason", "One or more error parameters outside tolerance")
            elif not residuals_valid:
                result.add_detail("failure_reason", "One or more residual errors outside tolerance")
        
        return result.to_dict()
    
    except np.linalg.LinAlgError:
        # Matrix inversion failed
        return {
            'is_valid': False,
            'error': "Matrix inversion failed. Survey geometry is likely poor."
        }

def calculate_theoretical_gravity(latitude, depth):
    """
    Calculate theoretical gravity at a given latitude and depth
    
    Args:
        latitude (float): Latitude in degrees
        depth (float): Vertical depth in meters
        
    Returns:
        float: Theoretical gravity in g
    """
    # Normal gravity formula (WGS 84 Ellipsoid)
    lat_rad = math.radians(latitude)
    surface_gravity = 9.7803267714 * (1 + 0.00193185138639 * math.sin(lat_rad)**2) / \
                     math.sqrt(1 - 0.00669437999013 * math.sin(lat_rad)**2)
    
    # Convert to g units (divide by standard gravity)
    surface_gravity_g = surface_gravity / 9.80665
    
    # Apply depth correction (free-air correction + Bouguer correction)
    # Approximation: 0.3086 mGal/m free-air gradient
    free_air_correction = 0.3086 * depth / 1000 / 9.80665
    
    # Return corrected gravity
    return surface_gravity_g - free_air_correction