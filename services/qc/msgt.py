# services/qc/msgt.py
import math
import numpy as np
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

def perform_msgt(surveys, ipm_data):
    """
    Performs Multi-Station Gyro Test (MSGT) on a set of survey measurements
    
    Args:
        surveys (list): List of survey dictionaries containing:
            - gyro_x, gyro_y: Gyroscope measurements (deg/hr)
            - inclination: Survey inclination (degrees)
            - azimuth: Survey azimuth (degrees)
            - toolface: Survey toolface (degrees)
            - latitude: Survey location latitude (degrees)
            
        ipm_data (dict): Instrument Performance Model data containing error terms
        
    Returns:
        dict: QC test results with:
            - is_valid: Boolean indicating if surveys passed the test
            - gyro_errors: Estimated gyroscope error parameters
            - residuals: Residual horizontal Earth rate errors per station
            - correlations: Correlation coefficients between error parameters
            - details: Additional test details
    """
    # Verify if we have enough surveys
    if len(surveys) < 10:
        return {
            'is_valid': False,
            'error': "At least 10 survey stations are required for MSGT"
        }
    
    # Extract survey data
    inclinations = [math.radians(survey['inclination']) for survey in surveys]
    azimuths = [math.radians(survey['azimuth']) for survey in surveys]
    toolfaces = [math.radians(survey['toolface']) for survey in surveys]
    
    # Check inclination variation
    inc_variation = max(inclinations) - min(inclinations)
    
    # Check toolface quadrant distribution
    tf_quadrants = [0, 0, 0, 0]  # Q1: 0-90, Q2: 90-180, Q3: 180-270, Q4: 270-360
    for tf in [math.degrees(tf) % 360 for tf in toolfaces]:
        quadrant = int(tf / 90)
        tf_quadrants[quadrant] += 1
    
    quadrant_count = sum(1 for q in tf_quadrants if q > 0)
    
    # Check azimuth distribution relative to east/west
    east_west_count = 0
    for az in [math.degrees(az) % 360 for az in azimuths]:
        if (az >= 60 and az <= 120) or (az >= 240 and az <= 300):
            east_west_count += 1
    
    east_west_ratio = east_west_count / len(surveys)
    
    # Check if geometry is suitable for MSGT
    if inc_variation < math.radians(30) or quadrant_count < 3 or east_west_ratio > 0.5:
        return {
            'is_valid': False,
            'error': "Survey geometry is not suitable for MSGT. Need more variation in inclination, toolface, and/or azimuth."
        }
    
    # Calculate horizontal Earth rate errors for each station
    h_rate_errors = []
    earth_rate = 15.041067  # deg/hr
    
    for survey in surveys:
        gyro_x = survey['gyro_x']
        gyro_y = survey['gyro_y']
        inc = math.radians(survey['inclination'])
        az = math.radians(survey['azimuth'])
        tf = math.radians(survey['toolface'])
        latitude = survey['latitude']
        
        # Calculate measured horizontal Earth rate
        measured_h_rate = calculate_measured_horizontal_rate(gyro_x, gyro_y, inc, az, tf)
        
        # Calculate theoretical horizontal Earth rate
        theoretical_h_rate = earth_rate * math.cos(math.radians(latitude))
        
        # Calculate horizontal rate error
        h_rate_error = measured_h_rate - theoretical_h_rate
        h_rate_errors.append(h_rate_error)
    
    # Create design matrix
    # For xy gyro systems, we estimate GBX*, GBY*, M, and Q
    A = np.zeros((len(surveys), 4))
    
    for i, (survey, inc, az, tf) in enumerate(zip(surveys, inclinations, azimuths, toolfaces)):
        # Calculate weighting functions
        A[i, 0] = math.sin(inc) * math.cos(az) + math.sin(az) / math.cos(tf)  # GBX*
        A[i, 1] = math.sin(inc) * math.sin(az) - math.cos(az) / math.cos(tf)  # GBY*
        A[i, 2] = -math.sin(inc) * math.cos(az)  # M
        A[i, 3] = math.sin(inc) * math.sin(az) * math.tan(inc)  # Q
    
    # Solve the least squares problem
    h_rate_errors_array = np.array(h_rate_errors)
    
    try:
        # Calculate (A^T * A)^-1
        AT_A = np.dot(A.T, A)
        AT_A_inv = np.linalg.inv(AT_A)
        
        # Calculate A^T * ΔΩh
        AT_h = np.dot(A.T, h_rate_errors_array)
        
        # Calculate parameter vector X
        X = np.dot(AT_A_inv, AT_h)
        
        # Calculate residuals
        residuals = h_rate_errors_array - np.dot(A, X)
        
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
        
        # Get gyro error terms from IPM
        gbx_sigma = get_error_term_value(ipm, 'GBX', 'e', 's')
        gby_sigma = get_error_term_value(ipm, 'GBY', 'e', 's')
        m_sigma = get_error_term_value(ipm, 'M', 'e', 's')
        q_sigma = get_error_term_value(ipm, 'Q', 'e', 's')
        
        # Parameter names and tolerances
        param_names = ['GBX*', 'GBY*', 'M', 'Q']
        param_tolerances = [3 * gbx_sigma, 3 * gby_sigma, 3 * m_sigma, 3 * q_sigma]
        
        # Check if parameters are within tolerances
        params_valid = all(abs(X[i]) <= param_tolerances[i] for i in range(len(X)))
        
        # Calculate tolerance for residuals at each station
        residual_tolerances = []
        for i, survey in enumerate(surveys):
            inc = math.radians(survey['inclination'])
            az = math.radians(survey['azimuth'])
            tf = math.radians(survey['toolface'])
            
            # Get weighting functions
            w_gbx = math.sin(inc) * math.cos(az) + math.sin(az) / math.cos(tf)
            w_gby = math.sin(inc) * math.sin(az) - math.cos(az) / math.cos(tf)
            w_m = -math.sin(inc) * math.cos(az)
            w_q = math.sin(inc) * math.sin(az) * math.tan(inc)
            
            # Get additional error terms from IPM
            gsx = get_error_term_value(ipm, 'GSX', 'e', 's')
            gsy = get_error_term_value(ipm, 'GSY', 'e', 's')
            gr = get_error_term_value(ipm, 'GR', 'e', 's')
            
            # Calculate tolerance for this station
            tolerance = 3 * math.sqrt(
                (gbx_sigma * w_gbx)**2 + 
                (gby_sigma * w_gby)**2 + 
                (m_sigma * w_m)**2 + 
                (q_sigma * w_q)**2 +
                (gr**2)  # Random gyro error
            )
            
            residual_tolerances.append(tolerance)
        
        # Check if residuals are within tolerances
        residuals_valid = all(abs(residuals[i]) <= residual_tolerances[i] for i in range(len(residuals)))
        
        # Overall test validity
        is_valid = params_valid and residuals_valid and max_nondiag_corr <= 0.4
        
        # Create result
        result = QCResult("MSGT")
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
        
        # Add geometry info
        result.add_detail("inclination_variation_degrees", math.degrees(inc_variation))
        result.add_detail("quadrant_distribution", tf_quadrants)
        result.add_detail("east_west_ratio", east_west_ratio)
        
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

def calculate_measured_horizontal_rate(gyro_x, gyro_y, inclination, azimuth, toolface):
    """
    Calculate the horizontal Earth rate from gyro measurements
    
    Args:
        gyro_x (float): X-axis gyro measurement (deg/hr)
        gyro_y (float): Y-axis gyro measurement (deg/hr)
        inclination (float): Inclination in radians
        azimuth (float): Azimuth in radians
        toolface (float): Toolface in radians
        
    Returns:
        float: Measured horizontal Earth rate (deg/hr)
    """
    # Transform gyro readings based on toolface
    sin_tf = math.sin(toolface)
    cos_tf = math.cos(toolface)
    sin_inc = math.sin(inclination)
    
    # Transform gyro readings to earth-fixed coordinate system
    wx_enu = gyro_x * cos_tf - gyro_y * sin_tf
    wy_enu = gyro_x * sin_tf + gyro_y * cos_tf
    
    # Calculate horizontal rate component
    # Note: This is a simplified calculation and may need adjustment
    # based on the specific gyro-compassing method used
    horizontal_rate = abs(math.sqrt(wx_enu**2 + wy_enu**2) / sin_inc)
    
    return horizontal_rate