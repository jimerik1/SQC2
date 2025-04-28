import math
import numpy as np
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

def perform_get(survey, ipm_data):
    """
    Performs Gravity Error Test (GET) on a single survey station
    
    Args:
        survey (dict): Survey station data containing:
            - accelerometer_x, accelerometer_y, accelerometer_z: Accelerometer measurements (g)
            - inclination: Survey inclination (degrees)
            - toolface: Survey toolface (degrees)
            - expected_gravity: Expected theoretical gravity (g) from external gravity model
        
        ipm_data (dict): Instrument Performance Model data containing error terms
        
    Returns:
        dict: QC test results with:
            - is_valid: Boolean indicating if survey passed the test
            - measured_gravity: Calculated gravity from accelerometer readings
            - theoretical_gravity: Expected gravity provided in the input
            - gravity_error: Difference between measured and theoretical gravity
            - tolerance: Calculated tolerance based on IPM
            - details: Additional test details
    """
    # Extract survey data
    acc_x = survey['accelerometer_x']
    acc_y = survey['accelerometer_y']
    acc_z = survey['accelerometer_z']
    inclination = survey['inclination']
    toolface = survey['toolface']
    
    # Calculate measured gravity
    measured_gravity = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
    
    # Use provided theoretical gravity from input
    theoretical_gravity = survey['expected_gravity']
    
    # Calculate gravity error
    gravity_error = measured_gravity - theoretical_gravity
    
    # Calculate tolerance
    tolerance = calculate_get_tolerance(ipm_data, inclination, toolface)
    
    # Determine if the survey is valid
    is_valid = abs(gravity_error) <= tolerance
    
    # Create result object
    result = QCResult("GET")
    result.set_validity(is_valid)
    result.add_measurement("gravity", measured_gravity)
    result.add_theoretical("gravity", theoretical_gravity)
    result.add_error("gravity", gravity_error)
    result.add_tolerance("gravity", tolerance)
    result.add_detail("inclination", inclination)
    result.add_detail("toolface", toolface)
    result.add_detail("weighting_functions", calculate_get_weighting_functions(inclination, toolface))
    
    return result.to_dict()

def calculate_get_weighting_functions(inclination, toolface):
    """
    Calculate the weighting functions for the GET
    
    Args:
        inclination (float): Inclination in degrees
        toolface (float): Toolface in degrees
        
    Returns:
        dict: Weighting functions for each error term
    """
    inc_rad = math.radians(inclination)
    tf_rad = math.radians(toolface)
    
    # Calculate weighting functions
    wx = math.sin(inc_rad) * math.sin(tf_rad)
    wy = math.sin(inc_rad) * math.cos(tf_rad)
    wz = math.cos(inc_rad)
    
    return {
        'wx': wx,
        'wy': wy,
        'wz': wz
    }

def calculate_get_tolerance(ipm_data, inclination, toolface):
    """
    Calculate tolerance for Gravity Error Test
    
    Args:
        ipm_data (dict): IPM data containing accelerometer error terms
        inclination (float): Inclination in degrees
        toolface (float): Toolface in degrees
        
    Returns:
        float: Tolerance value for GET
    """
    # Parse IPM if it's string content
    if isinstance(ipm_data, str):
        ipm = parse_ipm_file(ipm_data)
    else:
        ipm = ipm_data
    
    # Get weighting functions
    weights = calculate_get_weighting_functions(inclination, toolface)
    wx = weights['wx']
    wy = weights['wy']
    wz = weights['wz']
    
    # Get error terms from IPM
    abx = get_error_term_value(ipm, 'ABXY-TI1S', 'e', 's')
    aby = get_error_term_value(ipm, 'ABXY-TI1S', 'e', 's')
    abz = get_error_term_value(ipm, 'ABZ', 'e', 's')
    asx = get_error_term_value(ipm, 'ASXY-TI1S', 'e', 's')
    asy = get_error_term_value(ipm, 'ASXY-TI1S', 'e', 's')
    asz = get_error_term_value(ipm, 'ASZ', 'e', 's')
    
    # Calculate tolerance (3-sigma)
    g = 9.80665  # Standard gravity in m/s²
    tolerance = 3 * math.sqrt(
        (abx * wx)**2 + 
        (aby * wy)**2 + 
        (abz * wz)**2 + 
        (asx * wx * g)**2 + 
        (asy * wy * g)**2 + 
        (asz * wz * g)**2
    )
    
    return tolerance