import math
import numpy as np
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

def perform_tfdt(survey, ipm_data):
    """
    Performs Total Field + Dip Test (TFDT) on a single survey station
    
    Args:
        survey (dict): Survey station data containing:
            - mag_x, mag_y, mag_z: Magnetometer measurements (nT)
            - accelerometer_x, accelerometer_y, accelerometer_z: Accelerometer measurements (g)
            - inclination: Survey inclination (degrees)
            - toolface: Survey toolface (degrees)
            - longitude: Survey location longitude (degrees)
            - latitude: Survey location latitude (degrees)
            - depth: Measured depth (m)
            - geomagnetic_field: Geomagnetic field model data (optional)
            
        ipm_data (dict): Instrument Performance Model data containing error terms
        
    Returns:
        dict: QC test results with:
            - is_valid: Boolean indicating if survey passed the test
            - measured_total_field: Calculated total magnetic field from magnetometer readings
            - theoretical_total_field: Expected total magnetic field
            - total_field_error: Difference between measured and theoretical total field
            - measured_dip: Calculated magnetic dip angle
            - theoretical_dip: Expected magnetic dip angle
            - dip_error: Difference between measured and theoretical dip
            - field_tolerance: Calculated total field tolerance based on IPM
            - dip_tolerance: Calculated dip tolerance based on IPM
            - details: Additional test details
    """
    # Extract survey data
    mag_x = survey['mag_x']
    mag_y = survey['mag_y']
    mag_z = survey['mag_z']
    acc_x = survey['accelerometer_x']
    acc_y = survey['accelerometer_y']
    acc_z = survey['accelerometer_z']
    inclination = survey['inclination']
    toolface = survey['toolface']
    longitude = survey['longitude']
    latitude = survey['latitude']
    depth = survey['depth']
    
    # Get geomagnetic model data if not provided
    geo_data = (survey.get('expected_geomagnetic_field') or 
                survey.get('geomagnetic_field') or 
                get_geomagnetic_field(longitude, latitude, depth))
    
    # Calculate measured total magnetic field
    measured_total_field = math.sqrt(mag_x**2 + mag_y**2 + mag_z**2)
    
    # Calculate measured dip angle
    measured_dip = calculate_magnetic_dip(mag_x, mag_y, mag_z, acc_x, acc_y, acc_z)
    
    # Get theoretical magnetic field values
    theoretical_total_field = geo_data['total_field']
    theoretical_dip = geo_data['dip']
    
    # Calculate errors
    total_field_error = measured_total_field - theoretical_total_field
    dip_error = measured_dip - theoretical_dip
    
    # Calculate tolerances
    field_tolerance, dip_tolerance = calculate_tfdt_tolerances(
        ipm_data, inclination, toolface, theoretical_total_field, theoretical_dip
    )
    
    # Determine if the survey is valid
    is_valid_field = abs(total_field_error) <= field_tolerance
    is_valid_dip = abs(dip_error) <= dip_tolerance
    is_valid = is_valid_field and is_valid_dip
    
    # Create result object
    result = QCResult("TFDT")
    result.set_validity(is_valid)
    result.add_measurement("total_field", measured_total_field)
    result.add_theoretical("total_field", theoretical_total_field)
    result.add_error("total_field", total_field_error)
    result.add_tolerance("total_field", field_tolerance)
    result.add_measurement("dip", measured_dip)
    result.add_theoretical("dip", theoretical_dip)
    result.add_error("dip", dip_error)
    result.add_tolerance("dip", dip_tolerance)
    result.add_detail("is_valid_field", is_valid_field)
    result.add_detail("is_valid_dip", is_valid_dip)
    result.add_detail("inclination", inclination)
    result.add_detail("toolface", toolface)
    result.add_detail("weighting_functions", calculate_tfdt_weighting_functions(
        inclination, toolface, theoretical_dip
    ))
    
    return result.to_dict()

def calculate_magnetic_dip(mag_x, mag_y, mag_z, acc_x, acc_y, acc_z):
    """
    Calculate magnetic dip angle from magnetometer and accelerometer readings
    
    Args:
        mag_x, mag_y, mag_z (float): Magnetometer readings (nT)
        acc_x, acc_y, acc_z (float): Accelerometer readings (g)
        
    Returns:
        float: Magnetic dip angle in degrees
    """
    # Calculate gravity vector
    g = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
    
    # Calculate dot product of magnetic and gravity vectors
    dot_product = mag_x * acc_x + mag_y * acc_y + mag_z * acc_z
    
    # Calculate magnetic dip angle
    dip_rad = math.asin(dot_product / (g * math.sqrt(mag_x**2 + mag_y**2 + mag_z**2)))
    
    return math.degrees(dip_rad)

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

def calculate_tfdt_weighting_functions(inclination, toolface, theoretical_dip):
    """
    Calculate the weighting functions for the TFDT
    
    Args:
        inclination (float): Inclination in degrees
        toolface (float): Toolface in degrees
        theoretical_dip (float): Theoretical magnetic dip in degrees
        
    Returns:
        dict: Weighting functions for each error term
    """
    # Convert to radians
    inc_rad = math.radians(inclination)
    tf_rad = math.radians(toolface)
    dip_rad = math.radians(theoretical_dip)
    
    # Calculate weighting functions for total field
    wbx_b = math.sin(inc_rad) * math.cos(tf_rad) * math.cos(dip_rad) - \
           math.sin(tf_rad) * math.sin(dip_rad)
    wby_b = math.sin(inc_rad) * math.sin(tf_rad) * math.cos(dip_rad) + \
           math.cos(tf_rad) * math.sin(dip_rad)
    wbz_b = math.cos(inc_rad) * math.cos(dip_rad)
    
    # Calculate weighting functions for dip
    wbx_d = (math.sin(inc_rad) * math.cos(tf_rad) * math.sin(dip_rad) + \
            math.sin(tf_rad) * math.cos(dip_rad)) / math.cos(dip_rad)
    wby_d = (math.sin(inc_rad) * math.sin(tf_rad) * math.sin(dip_rad) - \
            math.cos(tf_rad) * math.cos(dip_rad)) / math.cos(dip_rad)
    wbz_d = math.cos(inc_rad) * math.sin(dip_rad) / math.cos(dip_rad)
    
    return {
        'wbx_b': wbx_b,
        'wby_b': wby_b,
        'wbz_b': wbz_b,
        'wbx_d': wbx_d,
        'wby_d': wby_d,
        'wbz_d': wbz_d
    }

def calculate_tfdt_tolerances(ipm_data, inclination, toolface, total_field, dip):
    """
    Calculate tolerances for Total Field + Dip Test
    
    Args:
        ipm_data (dict): IPM data containing magnetometer error terms
        inclination (float): Inclination in degrees
        toolface (float): Toolface in degrees
        total_field (float): Theoretical total magnetic field (nT)
        dip (float): Theoretical magnetic dip angle (degrees)
        
    Returns:
        tuple: (field_tolerance, dip_tolerance) values for TFDT
    """
    # Parse IPM if it's string content
    if isinstance(ipm_data, str):
        ipm = parse_ipm_file(ipm_data)
    else:
        ipm = ipm_data
    
    # Get weighting functions
    weights = calculate_tfdt_weighting_functions(inclination, toolface, dip)
    
    # Get error terms from IPM
    mbx = get_error_term_value(ipm, 'MBX', 'e', 's')
    mby = get_error_term_value(ipm, 'MBY', 'e', 's')
    mbz = get_error_term_value(ipm, 'MBZ', 'e', 's')
    msx = get_error_term_value(ipm, 'MSX', 'e', 's')
    msy = get_error_term_value(ipm, 'MSY', 'e', 's')
    msz = get_error_term_value(ipm, 'MSZ', 'e', 's')
    mfi = get_error_term_value(ipm, 'MFI', 'e', 's')
    mdi = get_error_term_value(ipm, 'MDI', 'e', 's')
    
    # Calculate field tolerance (3-sigma)
    field_tolerance = 3 * math.sqrt(
        (mbx * weights['wbx_b'])**2 + 
        (mby * weights['wby_b'])**2 + 
        (mbz * weights['wbz_b'])**2 + 
        (msx * weights['wbx_b'] * total_field)**2 + 
        (msy * weights['wby_b'] * total_field)**2 + 
        (msz * weights['wbz_b'] * total_field)**2 +
        (mfi * total_field)**2
    )
    
    # Calculate dip tolerance (3-sigma)
    dip_tolerance = 3 * math.sqrt(
        (mbx * weights['wbx_d'])**2 + 
        (mby * weights['wby_d'])**2 + 
        (mbz * weights['wbz_d'])**2 + 
        (msx * weights['wbx_d'] * total_field)**2 + 
        (msy * weights['wby_d'] * total_field)**2 + 
        (msz * weights['wbz_d'] * total_field)**2 +
        (mdi)**2
    )
    
    return field_tolerance, dip_tolerance