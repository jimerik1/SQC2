import math
import numpy as np
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

def perform_hert(survey, ipm_data):
    """
    Performs Horizontal Earth Rate Test (HERT) on a single survey station
    
    Args:
        survey (dict): Survey station data containing:
            - gyro_x, gyro_y: Gyroscope measurements (deg/hr)
            - inclination: Survey inclination (degrees)
            - azimuth: Survey azimuth (degrees)
            - toolface: Survey toolface (degrees)
            - latitude: Survey location latitude (degrees)
            
        ipm_data (dict): Instrument Performance Model data containing error terms
        
    Returns:
        dict: QC test results with:
            - is_valid: Boolean indicating if survey passed the test
            - measured_horizontal_rate: Calculated horizontal Earth rate from gyro readings
            - theoretical_horizontal_rate: Expected horizontal Earth rate
            - horizontal_rate_error: Difference between measured and theoretical rates
            - tolerance: Calculated tolerance based on IPM
            - details: Additional test details
    """
    # Extract survey data
    gyro_x = survey['gyro_x']
    gyro_y = survey['gyro_y']
    inclination = survey['inclination']
    azimuth = survey['azimuth']
    toolface = survey['toolface']
    latitude = survey['latitude']
    
    # Calculate measured horizontal Earth rate
    measured_h_rate = calculate_measured_horizontal_rate(gyro_x, gyro_y, inclination, azimuth, toolface)
    
    # Calculate theoretical horizontal Earth rate
    earth_rate = 15.041067  # deg/hr
    theoretical_h_rate = earth_rate * math.cos(math.radians(latitude))
    
    # Calculate horizontal rate error
    h_rate_error = measured_h_rate - theoretical_h_rate
    
    # Calculate tolerance
    tolerance = calculate_hert_tolerance(ipm_data, inclination, azimuth, toolface)
    
    # Determine if the survey is valid
    is_valid = abs(h_rate_error) <= tolerance
    
    # Create result object
    result = QCResult("HERT")
    result.set_validity(is_valid)
    result.add_measurement("horizontal_rate", measured_h_rate)
    result.add_theoretical("horizontal_rate", theoretical_h_rate)
    result.add_error("horizontal_rate", h_rate_error)
    result.add_tolerance("horizontal_rate", tolerance)
    result.add_detail("inclination", inclination)
    result.add_detail("azimuth", azimuth)
    result.add_detail("toolface", toolface)
    result.add_detail("weighting_functions", calculate_hert_weighting_functions(inclination, azimuth, toolface))
    
    return result.to_dict()

def calculate_measured_horizontal_rate(gyro_x, gyro_y, inclination, azimuth, toolface):
    """
    Calculate the horizontal Earth rate from gyro measurements
    
    Args:
        gyro_x (float): X-axis gyro measurement (deg/hr)
        gyro_y (float): Y-axis gyro measurement (deg/hr)
        inclination (float): Inclination in degrees
        azimuth (float): Azimuth in degrees
        toolface (float): Toolface in degrees
        
    Returns:
        float: Measured horizontal Earth rate (deg/hr)
    """
    # Convert to radians
    inc_rad = math.radians(inclination)
    az_rad = math.radians(azimuth)
    tf_rad = math.radians(toolface)
    
    # Calculate horizontal Earth rate based on gyro measurements
    # This implementation depends on the specific gyro-compassing method
    # Simplified example:
    sin_tf = math.sin(tf_rad)
    cos_tf = math.cos(tf_rad)
    sin_inc = math.sin(inc_rad)
    
    # Transform gyro readings to find Earth rotation rate
    wx_enu = gyro_x * cos_tf - gyro_y * sin_tf
    wy_enu = gyro_x * sin_tf + gyro_y * cos_tf
    
    # Calculate horizontal rate
    horizontal_rate = abs(math.sqrt(wx_enu**2 + wy_enu**2) / sin_inc)
    
    return horizontal_rate

def calculate_hert_weighting_functions(inclination, azimuth, toolface):
    """
    Calculate the weighting functions for the HERT
    
    Args:
        inclination (float): Inclination in degrees
        azimuth (float): Azimuth in degrees
        toolface (float): Toolface in degrees
        
    Returns:
        dict: Weighting functions for each error term
    """
    # Convert to radians
    inc_rad = math.radians(inclination)
    az_rad = math.radians(azimuth)
    tf_rad = math.radians(toolface)
    
    # Calculate weighting functions
    # These are the partial derivatives of the horizontal rate error with respect to each error term
    w_gbx = math.sin(inc_rad) * math.cos(az_rad) + math.sin(az_rad) / math.cos(tf_rad)
    w_gby = math.sin(inc_rad) * math.sin(az_rad) - math.cos(az_rad) / math.cos(tf_rad)
    w_m = -math.sin(inc_rad) * math.cos(az_rad)
    w_q = math.sin(inc_rad) * math.sin(az_rad) * math.tan(inc_rad)
    
    return {
        'w_gbx': w_gbx,
        'w_gby': w_gby,
        'w_m': w_m,
        'w_q': w_q
    }

def calculate_hert_tolerance(ipm_data, inclination, azimuth, toolface):
    """
    Calculate tolerance for Horizontal Earth Rate Test
    
    Args:
        ipm_data (dict): IPM data containing gyro error terms
        inclination (float): Inclination in degrees
        azimuth (float): Azimuth in degrees
        toolface (float): Toolface in degrees
        
    Returns:
        float: Tolerance value for HERT
    """
    # Parse IPM if it's string content
    if isinstance(ipm_data, str):
        ipm = parse_ipm_file(ipm_data)
    else:
        ipm = ipm_data
    
    # Get weighting functions
    weights = calculate_hert_weighting_functions(inclination, azimuth, toolface)
    w_gbx = weights['w_gbx']
    w_gby = weights['w_gby']
    w_m = weights['w_m']
    w_q = weights['w_q']
    
    # Get error terms from IPM
    gbx = get_error_term_value(ipm, 'GBX', 'e', 's')
    gby = get_error_term_value(ipm, 'GBY', 'e', 's')
    m = get_error_term_value(ipm, 'M', 'e', 's')
    q = get_error_term_value(ipm, 'Q', 'e', 's')
    gsx = get_error_term_value(ipm, 'GSX', 'e', 's')
    gsy = get_error_term_value(ipm, 'GSY', 'e', 's')
    gr = get_error_term_value(ipm, 'GR', 'e', 's')
    
    # Earth's rotation rate in deg/hr
    earth_rate = 15.041067
    
    # Calculate tolerance (3-sigma)
    tolerance = 3 * math.sqrt(
        (gbx * w_gbx)**2 + 
        (gby * w_gby)**2 + 
        (m * w_m)**2 + 
        (q * w_q)**2 +
        (gr**2)  # Random gyro error
    )
    
    return tolerance