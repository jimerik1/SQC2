# services/qc/mse.py
import math
import numpy as np
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

def perform_mse(surveys, ipm_data):
    """
    Performs Multi-Station Estimation (MSE) on a set of survey measurements.
    
    MSE is an advanced technique that simultaneously estimates both the true 
    directional parameters (azimuths, inclinations, toolfaces) and the systematic 
    error parameters affecting the measurements.
    
    This implementation is based on the approach described in "The Reliability 
    Problem Related to Directional Survey Data" (IADC/SPE 103734).
    
    Args:
        surveys (list): List of survey dictionaries containing:
            - mag_x, mag_y, mag_z: Magnetometer measurements (nT)
            - Gx, Gy, Gz: Accelerometer measurements (g)
            - inclination: Survey inclination (degrees)
            - azimuth: Survey azimuth (degrees)
            - toolface: Survey toolface (degrees)
            - longitude: Survey location longitude (degrees)
            - latitude: Survey location latitude (degrees)
            - depth: Measured depth (m)
            - geomagnetic_field: Geomagnetic field model data (optional)
            
        ipm_data (dict): Instrument Performance Model data containing error terms
        
    Returns:
        dict: MSE results with:
            - is_valid: Boolean indicating if the estimation is valid
            - error_parameters: Estimated systematic error parameters
            - corrected_surveys: Surveys with corrected angles
            - correlations: Correlation coefficients between error parameters
            - statistics: Statistics about the estimation quality
            - details: Additional details about the estimation process
    """
    # ----- IMPORTANT LIMITATIONS AND USAGE NOTES -----
    # The following limitations of MSE should be considered when interpreting results:
    #
    # 1. GEOMETRY DEPENDENCY:
    #    - MSE performance is highly dependent on well geometry and directional variation.
    #    - Axial error terms (especially z-axis) are difficult to estimate in wells with
    #      limited inclination variation.
    #    - Cross-axial error terms are more reliably estimated, especially for tools that
    #      rotate between survey stations.
    #
    # 2. CORRELATION ISSUES:
    #    - High correlations between estimated parameters indicate unreliable estimates.
    #    - It's difficult to distinguish between scale factor errors and reference field errors.
    #    - Magnetic declination errors cannot be detected or estimated using MSE.
    #
    # 3. STATISTICAL INTERPRETATION:
    #    - Small sensor errors within acceptable ranges may not be statistically significant
    #      in the estimation, even if present.
    #    - Uncritical use of MSE can lead to misinterpretation of results.
    #    - Statistical testing must be applied to determine which parameters are reliable.
    #
    # 4. REFERENCE FIELD QUALITY:
    #    - The quality of MSE results depends heavily on the accuracy of Earth's field 
    #      reference data (magnetic field strength, dip angle).
    #
    # 5. MODEL COMPLEXITY:
    #    - Estimating too many error parameters simultaneously can lead to high uncertainty
    #      in both the azimuth and error estimates.
    # ---------------------------------------------------

    # Verify if we have enough surveys
    if len(surveys) < 10:
        return {
            'is_valid': False,
            'error': "At least 10 survey stations are required for MSE"
        }
    
    # Check if survey data has sufficient variation
    inclinations = [survey['inclination'] for survey in surveys]
    azimuths = [survey['azimuth'] for survey in surveys]
    toolfaces = [survey['toolface'] for survey in surveys]
    
    inc_variation = max(inclinations) - min(inclinations)
    azi_variation = max([abs((a1 - a2 + 180) % 360 - 180) for a1 in azimuths for a2 in azimuths])
    
    # Check toolface distribution
    tf_quadrants = [0, 0, 0, 0]  # Q1: 0-90, Q2: 90-180, Q3: 180-270, Q4: 270-360
    for tf in toolfaces:
        quadrant = int(tf / 90)
        if quadrant == 4:  # Handle 360 degrees case
            quadrant = 0
        tf_quadrants[quadrant] += 1
    
    quadrant_count = sum(1 for q in tf_quadrants if q > 0)
    
    # Evaluate the survey geometry
    geometry_quality = "excellent" if (inc_variation > 45 and azi_variation > 45 and quadrant_count >= 4) else \
                       "good" if (inc_variation > 30 and azi_variation > 30 and quadrant_count >= 3) else \
                       "fair" if (inc_variation > 15 and azi_variation > 15 and quadrant_count >= 2) else \
                       "poor"
    
    # For poor geometry, we should limit the number of parameters to estimate
    # to avoid unreliable results
    if geometry_quality == "poor":
        return {
            'is_valid': False,
            'error': "Survey geometry is insufficient for reliable MSE. Need more variation in inclination, azimuth, and toolface.",
            'details': {
                'inclination_variation': inc_variation,
                'azimuth_variation': azi_variation,
                'quadrant_distribution': tf_quadrants,
                'geometry_quality': geometry_quality
            }
        }

    # Parse IPM if it's string content
    if isinstance(ipm_data, str):
        ipm = parse_ipm_file(ipm_data)
    else:
        ipm = ipm_data
    
    # Setup the parameter model based on geometry quality
    # We'll use different parameter sets depending on the geometry quality
    # to avoid overparameterization that leads to high correlations
    if geometry_quality == "excellent":
        # Full model with both magnetometer and accelerometer parameters
        param_names = ['MBX', 'MBY', 'MBZ', 'MSX', 'MSY', 'MSZ', 'ABX', 'ABY', 'ABZ', 'ASX', 'ASY']
    elif geometry_quality == "good":
        # Reduced model focusing on primary magnetometer parameters
        param_names = ['MBX', 'MBY', 'MBZ', 'MSX', 'MSY', 'ABX', 'ABY']
    else:  # "fair"
        # Minimal model with only the most reliable parameters
        param_names = ['MBX', 'MBY', 'ABX', 'ABY']
    
    # Build vectors of measurements
    # We'll formulate the problem as y = f(x) + ε
    # where y is the measurement vector, x is the parameter vector, 
    # f is the non-linear function relating parameters to measurements,
    # and ε is the measurement noise

    # Number of surveys and parameters
    n_surveys = len(surveys)
    n_params = len(param_names)
    
    # Each survey provides 6 measurements (3 mag + 3 accel components)
    n_measurements = n_surveys * 6
    
    # Initialize measurement vector y
    y = np.zeros(n_measurements)
    
    # Fill measurement vector with actual sensor readings
    for i, survey in enumerate(surveys):
        # Magnetometer readings
        y[i*6 + 0] = survey['mag_x']
        y[i*6 + 1] = survey['mag_y']
        y[i*6 + 2] = survey['mag_z']
        
        # Accelerometer readings
        y[i*6 + 3] = survey['Gx']
        y[i*6 + 4] = survey['Gy']
        y[i*6 + 5] = survey['Gz']
    
    # Initialize parameter vector with initial guess
    # First n_surveys*3 elements are the true angles (inc, azi, tf) for each station
    # Last n_params elements are the systematic error parameters
    x = np.zeros(n_surveys*3 + n_params)
    
    # Initialize with reported angles
    for i, survey in enumerate(surveys):
        x[i*3 + 0] = math.radians(survey['inclination'])
        x[i*3 + 1] = math.radians(survey['azimuth'])
        x[i*3 + 2] = math.radians(survey['toolface'])
    
    # Set up geomagnetic reference data
    geo_data = []
    for survey in surveys:
        if 'expected_geomagnetic_field' in survey and survey['expected_geomagnetic_field']:
            geo_data.append(survey['expected_geomagnetic_field'])
        else:
            # If not provided, use a simple approximation based on location
            geo_data.append(get_geomagnetic_field(survey['longitude'], survey['latitude'], survey['depth']))
    
    # Gauss-Newton iteration to solve the non-linear least squares problem
    max_iterations = 20
    convergence_threshold = 1e-6
    converged = False
    
    # Keep track of iteration history
    iteration_history = []
    
    for iteration in range(max_iterations):
        # Compute predicted measurements based on current parameter estimates
        y_pred = predict_measurements(x, geo_data, n_surveys, param_names)
        
        # Compute residuals
        residuals = y - y_pred
        
        # Compute Jacobian matrix (partial derivatives of measurements w.r.t. parameters)
        J = compute_jacobian(x, geo_data, n_surveys, param_names)
        
        # Compute normal equations: (J^T * J) * dx = J^T * residuals
        JTJ = np.dot(J.T, J)
        JTr = np.dot(J.T, residuals)
        
        # Add small regularization to avoid singularity
        # This helps stabilize the solution
        reg = 1e-6 * np.eye(JTJ.shape[0])
        JTJ_reg = JTJ + reg
        
        try:
            # Solve for parameter update
            dx = np.linalg.solve(JTJ_reg, JTr)
            
            # Update parameters
            x = x + dx
            
            # Check for convergence
            if np.linalg.norm(dx) < convergence_threshold:
                converged = True
                break
                
            # Save iteration stats
            iteration_history.append({
                'iteration': iteration,
                'residual_norm': float(np.linalg.norm(residuals)),
                'parameter_update_norm': float(np.linalg.norm(dx))
            })
            
        except np.linalg.LinAlgError:
            # If matrix is singular, the problem is likely ill-conditioned
            return {
                'is_valid': False,
                'error': "Matrix inversion failed. The estimation problem is likely ill-conditioned due to poor survey geometry or high parameter correlations.",
                'details': {
                    'inclination_variation': inc_variation,
                    'azimuth_variation': azi_variation,
                    'quadrant_distribution': tf_quadrants,
                    'geometry_quality': geometry_quality,
                    'iterations_completed': iteration
                }
            }
    
    # Get error parameter estimates from the solution vector
    # Last n_params elements of x are the error parameters
    error_params = x[-n_params:]
    
    # Get corrected angles from the solution vector
    # First n_surveys*3 elements of x are the corrected angles for each station
    corrected_angles = []
    for i in range(n_surveys):
        corrected_angles.append({
            'inclination': math.degrees(x[i*3 + 0]),
            'azimuth': math.degrees(x[i*3 + 1]) % 360,
            'toolface': math.degrees(x[i*3 + 2]) % 360
        })
    
    # Compute covariance matrix and correlation coefficients
    # The covariance matrix is proportional to (J^T * J)^(-1)
    try:
        # Add regularization to avoid singularity
        cov = np.linalg.inv(JTJ + 1e-6 * np.eye(JTJ.shape[0]))
        
        # Extract only the covariance of error parameters 
        # (last n_params x n_params block of full covariance matrix)
        error_cov = cov[-n_params:, -n_params:]
        
        # Compute standard deviations of error parameters
        error_stds = np.sqrt(np.diag(error_cov))
        
        # Compute correlation matrix
        corr_matrix = np.zeros_like(error_cov)
        for i in range(n_params):
            for j in range(n_params):
                corr_matrix[i, j] = error_cov[i, j] / (error_stds[i] * error_stds[j])
    except np.linalg.LinAlgError:
        # If matrix inversion fails, set all correlations to NaN
        error_stds = np.array([float('nan')] * n_params)
        corr_matrix = np.array([[float('nan')] * n_params] * n_params)
    
    # Check for high correlations that indicate poor estimation
    max_off_diag_corr = 0
    for i in range(n_params):
        for j in range(n_params):
            if i != j and not math.isnan(corr_matrix[i, j]) and abs(corr_matrix[i, j]) > max_off_diag_corr:
                max_off_diag_corr = abs(corr_matrix[i, j])
    
    # Get IPM tolerances for error parameters
    tolerances = {}
    for i, name in enumerate(param_names):
        tol = get_error_term_value(ipm, name, 'e', 's')
        tolerances[name] = 3 * tol if tol is not None else None
    
    # Format error parameter results with standard deviations and significance
    error_param_results = {}
    for i, name in enumerate(param_names):
        if math.isnan(error_stds[i]):
            t_stat = float('nan')
            significant = False
        else:
            t_stat = abs(error_params[i] / error_stds[i])
            significant = t_stat > 2.0  # t-statistic > 2 indicates statistical significance at ~95% level
        
        error_param_results[name] = {
            'value': float(error_params[i]),
            'std_dev': float(error_stds[i]),
            't_statistic': float(t_stat),
            'significant': significant,
            'within_tolerance': True if tolerances[name] is None else abs(error_params[i]) <= tolerances[name]
        }
    
    # Check if estimation is valid overall
    is_params_valid = all(result['within_tolerance'] for result in error_param_results.values() 
                          if not math.isnan(result['std_dev']))
    
    is_valid = converged and is_params_valid and max_off_diag_corr <= 0.4
    
    # Create the final result
    result = {
        'is_valid': is_valid,
        'error_parameters': error_param_results,
        'corrected_surveys': [{**surveys[i], **corrected_angles[i]} for i in range(n_surveys)],
        'correlations': corr_matrix.tolist(),
        'statistics': {
            'max_correlation': float(max_off_diag_corr),
            'converged': converged,
            'iterations': len(iteration_history) + 1,
            'final_residual_norm': float(np.linalg.norm(residuals)) if 'residuals' in locals() else None,
            'geometry_quality': geometry_quality
        },
        'details': {
            'inclination_variation': inc_variation,
            'azimuth_variation': azi_variation,
            'quadrant_distribution': tf_quadrants,
            'iteration_history': iteration_history
        }
    }
    
    if not is_valid:
        if max_off_diag_corr > 0.4:
            result['details']['failure_reason'] = "High parameter correlations detected"
        elif not is_params_valid:
            result['details']['failure_reason'] = "One or more error parameters outside tolerance"
        elif not converged:
            result['details']['failure_reason'] = "Estimation did not converge"
    
    return result

def predict_measurements(x, geo_data, n_surveys, param_names):
    """
    Predict sensor measurements given parameters
    
    Args:
        x (ndarray): Parameter vector (angles + error parameters)
        geo_data (list): List of geomagnetic field data for each survey
        n_surveys (int): Number of survey stations
        param_names (list): Names of error parameters
        
    Returns:
        ndarray: Predicted measurements
    """
    # Initialize predictions array (6 measurements per survey)
    y_pred = np.zeros(n_surveys * 6)
    
    # Extract error parameters from x
    error_params = {}
    for i, name in enumerate(param_names):
        error_params[name] = x[n_surveys*3 + i]
    
    # Helper function to get error parameter value or 0 if not present
    def get_param(name):
        return error_params.get(name, 0.0)
    
    # Calculate predicted measurements for each survey
    for i in range(n_surveys):
        # Get corrected angles for this survey
        inc = x[i*3 + 0]  # radians
        azi = x[i*3 + 1]  # radians
        tf = x[i*3 + 2]   # radians
        
        # Get geomagnetic reference field
        bt = geo_data[i]['total_field']
        dip = math.radians(geo_data[i]['dip'])
        
        # Compute ideal sensor readings
        # Theoretical magnetometer readings
        bx_ideal = bt * (math.sin(inc) * math.cos(azi) * math.cos(dip) - 
                         math.sin(dip) * math.sin(azi))
        by_ideal = bt * (math.sin(inc) * math.sin(azi) * math.cos(dip) + 
                         math.sin(dip) * math.cos(azi))
        bz_ideal = bt * (math.cos(inc) * math.cos(dip) + 
                         math.sin(inc) * math.sin(dip))
        
        # Theoretical accelerometer readings (g)
        gx_ideal = math.sin(inc) * math.sin(tf)
        gy_ideal = math.sin(inc) * math.cos(tf)
        gz_ideal = math.cos(inc)
        
        # Apply error models to get predicted measurements
        # Magnetometer with errors
        mbx = get_param('MBX')
        mby = get_param('MBY')
        mbz = get_param('MBZ')
        msx = get_param('MSX')
        msy = get_param('MSY')
        msz = get_param('MSZ')
        
        bx_pred = bx_ideal * (1 + msx * bt) + mbx
        by_pred = by_ideal * (1 + msy * bt) + mby
        bz_pred = bz_ideal * (1 + msz * bt) + mbz
        
        # Accelerometer with errors
        abx = get_param('ABX')
        aby = get_param('ABY')
        abz = get_param('ABZ')
        asx = get_param('ASX')
        asy = get_param('ASY')
        asz = get_param('ASZ')
        
        g = 9.80665  # standard gravity in m/s²
        gx_pred = gx_ideal * (1 + asx * g) + abx
        gy_pred = gy_ideal * (1 + asy * g) + aby
        gz_pred = gz_ideal * (1 + asz * g) + abz
        
        # Store predicted measurements
        y_pred[i*6 + 0] = bx_pred
        y_pred[i*6 + 1] = by_pred
        y_pred[i*6 + 2] = bz_pred
        y_pred[i*6 + 3] = gx_pred
        y_pred[i*6 + 4] = gy_pred
        y_pred[i*6 + 5] = gz_pred
    
    return y_pred

def compute_jacobian(x, geo_data, n_surveys, param_names):
    """
    Compute the Jacobian matrix of partial derivatives
    
    Args:
        x (ndarray): Parameter vector (angles + error parameters)
        geo_data (list): List of geomagnetic field data for each survey
        n_surveys (int): Number of survey stations
        param_names (list): Names of error parameters
        
    Returns:
        ndarray: Jacobian matrix
    """
    # Total number of parameters
    n_total_params = len(x)
    
    # Total number of measurements (6 per survey)
    n_measurements = n_surveys * 6
    
    # Initialize Jacobian matrix
    J = np.zeros((n_measurements, n_total_params))
    
    # Small value for finite difference approximation
    h = 1e-6
    
    # Compute Jacobian using finite differences
    for j in range(n_total_params):
        # Make a copy of x and perturb the j-th parameter
        x_plus = x.copy()
        x_plus[j] += h
        
        # Compute predictions with perturbed parameter
        y_plus = predict_measurements(x_plus, geo_data, n_surveys, param_names)
        
        # Compute predictions with original parameters
        y = predict_measurements(x, geo_data, n_surveys, param_names)
        
        # Compute partial derivatives using finite differences
        J[:, j] = (y_plus - y) / h
    
    return J

def get_geomagnetic_field(longitude, latitude, depth):
    """
    Get geomagnetic field data for a given location
    
    Args:
        longitude (float): Longitude in degrees
        latitude (float): Latitude in degrees
        depth (float): Depth in meters
        
    Returns:
        dict: Geomagnetic field data containing total_field, dip, declination
    """
    # In a real implementation, this would interface with a geomagnetic model
    # like IGRF or WMM, or could accept pre-calculated field data
    # This is a placeholder implementation
    
    # Example values - in reality would be based on models and location
    return {
        'total_field': 48000,  # nT
        'dip': 65,  # degrees
        'declination': 4,  # degrees
    }