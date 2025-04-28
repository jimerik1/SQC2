# services/qc/msmt.py
import math
import numpy as np
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

def perform_msmt(surveys, ipm_data):
    """
    Performs Multi-Station Magnetometer Test (MSMT) on a set of survey measurements
    
    Args:
        surveys (list): List of survey dictionaries containing:
            - mag_x, mag_y, mag_z: Magnetometer measurements (nT)
            - accelerometer_x, accelerometer_y, accelerometer_z: Accelerometer measurements (g)
            - inclination: Survey inclination (degrees)
            - azimuth: Survey azimuth (degrees)
            - toolface: Survey toolface (degrees)
            - longitude: Survey location longitude (degrees)
            - latitude: Survey location latitude (degrees)
            - depth: Measured depth (m)
            - geomagnetic_field: Geomagnetic field model data (optional)
            
        ipm_data (dict): Instrument Performance Model data containing error terms
        
    Returns:
        dict: QC test results with:
            - is_valid: Boolean indicating if surveys passed the test
            - magnetometer_errors: Estimated magnetometer error parameters
            - residuals: Residual magnetic field and dip errors per station
            - correlations: Correlation coefficients between error parameters
            - details: Additional test details
    """
    # Verify if we have enough surveys
    if len(surveys) < 10:
        return {
            'is_valid': False,
            'error': "At least 10 survey stations are required for MSMT"
        }
    
    # Initialize list to store magnetic field and dip errors
    magnetic_field_errors = []
    dip_errors = []
    
    # Calculate field and dip errors for each station
    for survey in surveys:
        # Extract magnetometer measurements
        mag_x = survey['mag_x']
        mag_y = survey['mag_y']
        mag_z = survey['mag_z']
        
        # Extract accelerometer measurements
        acc_x = survey['accelerometer_x']
        acc_y = survey['accelerometer_y']
        acc_z = survey['accelerometer_z']
        
        # Calculate measured magnetic field magnitude
        measured_total_field = math.sqrt(mag_x**2 + mag_y**2 + mag_z**2)
        
        # Calculate measured dip angle
        g = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
        dot_product = mag_x * acc_x + mag_y * acc_y + mag_z * acc_z
        measured_dip = math.degrees(math.asin(dot_product / (g * measured_total_field)))
        
        # Get theoretical magnetic field values (from provided field model or calculate)
        if 'geomagnetic_field' in survey:
            geo_data = survey['geomagnetic_field']
        else:
            geo_data = get_geomagnetic_field(survey['longitude'], survey['latitude'], survey['depth'])
        
        theoretical_total_field = geo_data['total_field']
        theoretical_dip = geo_data['dip']
        
        # Calculate errors
        field_error = measured_total_field - theoretical_total_field
        dip_error = measured_dip - theoretical_dip
        
        # Store errors
        magnetic_field_errors.append(field_error)
        dip_errors.append(dip_error)
    
    # Combine magnetic field errors and scaled dip errors
    combined_errors = []
    for i, survey in enumerate(surveys):
        if 'geomagnetic_field' in survey:
            geo_data = survey['geomagnetic_field']
        else:
            geo_data = get_geomagnetic_field(survey['longitude'], survey['latitude'], survey['depth'])
        
        theoretical_total_field = geo_data['total_field']
        
        # Add magnetic field error
        combined_errors.append(magnetic_field_errors[i])
        
        # Add scaled dip error
        combined_errors.append(theoretical_total_field * dip_errors[i])
    
    # Create design matrix for combined field and dip errors
    # We'll estimate MBX, MBY, MBZ, MSX, MSY, MSZ
    A = np.zeros((len(combined_errors), 6))
    
    row = 0
    for i, survey in enumerate(surveys):
        inc = math.radians(survey['inclination'])
        az = math.radians(survey['azimuth'])
        tf = math.radians(survey['toolface'])
        
        # Extract measurements
        mag_x = survey['mag_x']
        mag_y = survey['mag_y']
        mag_z = survey['mag_z']
        
        acc_x = survey['accelerometer_x']
        acc_y = survey['accelerometer_y']
        acc_z = survey['accelerometer_z']
        
        # Get theoretical field values
        if 'geomagnetic_field' in survey:
            geo_data = survey['geomagnetic_field']
        else:
            geo_data = get_geomagnetic_field(survey['longitude'], survey['latitude'], survey['depth'])
        
        theoretical_total_field = geo_data['total_field']
        theoretical_dip = math.radians(geo_data['dip'])
        
        # Calculate weighting functions for total field
        # Normalized magnetometer components
        B = math.sqrt(mag_x**2 + mag_y**2 + mag_z**2)
        bx = mag_x / B
        by = mag_y / B
        bz = mag_z / B
        
        # Total field error weighting functions
        A[row, 0] = bx  # MBX effect on total field
        A[row, 1] = by  # MBY effect on total field
        A[row, 2] = bz  # MBZ effect on total field
        A[row, 3] = bx * theoretical_total_field  # MSX effect on total field
        A[row, 4] = by * theoretical_total_field  # MSY effect on total field
        A[row, 5] = bz * theoretical_total_field  # MSZ effect on total field
        
        row += 1
        
        # Calculate weighting functions for dip
        # Normalized gravity components
        g = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
        gx = acc_x / g
        gy = acc_y / g
        gz = acc_z / g
        
        # Calculate weighting functions (simplified)
        cos_dip = math.cos(theoretical_dip)
        sin_dip = math.sin(theoretical_dip)
        
        # Dip error weighting functions
        A[row, 0] = (gx * cos_dip - bx * sin_dip) / cos_dip  # MBX effect on dip
        A[row, 1] = (gy * cos_dip - by * sin_dip) / cos_dip  # MBY effect on dip
        A[row, 2] = (gz * cos_dip - bz * sin_dip) / cos_dip  # MBZ effect on dip
        A[row, 3] = (gx * cos_dip - bx * sin_dip) / cos_dip * theoretical_total_field  # MSX effect on dip
        A[row, 4] = (gy * cos_dip - by * sin_dip) / cos_dip * theoretical_total_field  # MSY effect on dip
        A[row, 5] = (gz * cos_dip - bz * sin_dip) / cos_dip * theoretical_total_field  # MSZ effect on dip
        
        row += 1
    
    # Solve the least squares problem
    combined_errors_array = np.array(combined_errors)
    
    try:
        # Calculate (A^T * A)^-1
        AT_A = np.dot(A.T, A)
        AT_A_inv = np.linalg.inv(AT_A)
        
        # Calculate A^T * errors
        AT_e = np.dot(A.T, combined_errors_array)
        
        # Calculate parameter vector X
        X = np.dot(AT_A_inv, AT_e)
        
        # Calculate residuals
        residuals = combined_errors_array - np.dot(A, X)
        
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
        
        # Get magnetometer error terms from IPM
        mbx_sigma = get_error_term_value(ipm, 'MBX', 'e', 's')
        mby_sigma = get_error_term_value(ipm, 'MBY', 'e', 's')
        mbz_sigma = get_error_term_value(ipm, 'MBZ', 'e', 's')
        msx_sigma = get_error_term_value(ipm, 'MSX', 'e', 's')
        msy_sigma = get_error_term_value(ipm, 'MSY', 'e', 's')
        msz_sigma = get_error_term_value(ipm, 'MSZ', 'e', 's')
        mfi_sigma = get_error_term_value(ipm, 'MFI', 'e', 's')
        mdi_sigma = get_error_term_value(ipm, 'MDI', 'e', 's')
        
        # Parameter names and tolerances
        param_names = ['MBX', 'MBY', 'MBZ', 'MSX', 'MSY', 'MSZ']
        param_tolerances = [3 * mbx_sigma, 3 * mby_sigma, 3 * mbz_sigma, 
                          3 * msx_sigma, 3 * msy_sigma, 3 * msz_sigma]
        
        # Check if parameters are within tolerances
        params_valid = all(abs(X[i]) <= param_tolerances[i] for i in range(len(X)))
        
        # Calculate tolerance for residuals at each station
        residual_tolerances = []
        row = 0
        for i, survey in enumerate(surveys):
            # Extract measurements and survey data
            inc = math.radians(survey['inclination'])
            az = math.radians(survey['azimuth'])
            tf = math.radians(survey['toolface'])
            
            # Get theoretical field values
            if 'geomagnetic_field' in survey:
                geo_data = survey['geomagnetic_field']
            else:
                geo_data = get_geomagnetic_field(survey['longitude'], survey['latitude'], survey['depth'])
            
            theoretical_total_field = geo_data['total_field']
            theoretical_dip = math.radians(geo_data['dip'])
            
            # Calculate weighting functions for the tolerance
            mag_x = survey['mag_x']
            mag_y = survey['mag_y']
            mag_z = survey['mag_z']
            
            B = math.sqrt(mag_x**2 + mag_y**2 + mag_z**2)
            bx = mag_x / B
            by = mag_y / B
            bz = mag_z / B
            
            # Calculate total field tolerance
            field_tolerance = 3 * math.sqrt(
                (mbx_sigma * bx)**2 + 
                (mby_sigma * by)**2 + 
                (mbz_sigma * bz)**2 + 
                (msx_sigma * bx * theoretical_total_field)**2 + 
                (msy_sigma * by * theoretical_total_field)**2 + 
                (msz_sigma * bz * theoretical_total_field)**2 +
                (mfi_sigma * theoretical_total_field)**2
            )
            
            # Calculate dip tolerance
            dip_tolerance = 3 * math.sqrt(
                (mbx_sigma * A[row+1, 0])**2 + 
                (mby_sigma * A[row+1, 1])**2 + 
                (mbz_sigma * A[row+1, 2])**2 + 
                (msx_sigma * A[row+1, 3])**2 + 
                (msy_sigma * A[row+1, 4])**2 + 
                (msz_sigma * A[row+1, 5])**2 +
                (mdi_sigma)**2
            )
            
            # Add tolerances
            residual_tolerances.append(field_tolerance)
            residual_tolerances.append(theoretical_total_field * dip_tolerance)
            
            row += 2
        
        # Check if residuals are within tolerances
        residuals_valid = all(abs(residuals[i]) <= residual_tolerances[i] for i in range(len(residuals)))
        
        # Overall test validity
        is_valid = params_valid and residuals_valid and max_nondiag_corr <= 0.4
        
        # Create result
        result = QCResult("MSMT")
        result.set_validity(is_valid)
        
        # Add parameter estimates
        for i, name in enumerate(param_names):
            result.add_measurement(name, float(X[i]))
            result.add_tolerance(name, param_tolerances[i])
        
        # Add residuals (separated for field and dip)
        field_residuals = [residuals[i] for i in range(0, len(residuals), 2)]
        dip_residuals = [residuals[i+1]/surveys[i//2]['geomagnetic_field']['total_field'] 
                        if 'geomagnetic_field' in surveys[i//2] 
                        else residuals[i+1]/get_geomagnetic_field(
                            surveys[i//2]['longitude'], 
                            surveys[i//2]['latitude'], 
                            surveys[i//2]['depth'])['total_field'] 
                        for i in range(0, len(residuals)-1, 2)]
        
        field_tolerances = [residual_tolerances[i] for i in range(0, len(residual_tolerances), 2)]
        dip_tolerances = [residual_tolerances[i+1]/surveys[i//2]['geomagnetic_field']['total_field'] 
                         if 'geomagnetic_field' in surveys[i//2] 
                         else residual_tolerances[i+1]/get_geomagnetic_field(
                             surveys[i//2]['longitude'], 
                             surveys[i//2]['latitude'], 
                             surveys[i//2]['depth'])['total_field'] 
                         for i in range(0, len(residual_tolerances)-1, 2)]
        
        result.add_detail("field_residuals", field_residuals)
        result.add_detail("dip_residuals", dip_residuals)
        result.add_detail("field_tolerances", field_tolerances)
        result.add_detail("dip_tolerances", dip_tolerances)
        
        # Add correlation info
        result.add_detail("correlation_matrix", corr_matrix.tolist())
        result.add_detail("max_nondiagonal_correlation", float(max_nondiag_corr))
        
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