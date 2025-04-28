import numpy as np
import math
from utils.ipm_parser import parse_ipm_file

def calculate_get_tolerance(ipm_data, inclination, toolface):
    """
    Calculate the tolerance for Gravity Error Test based on IPM file
    
    Args:
        ipm_data: IPM file content or parsed IPMFile object
        inclination: Survey inclination in degrees
        toolface: Survey toolface in degrees
    
    Returns:
        The calculated tolerance value
    """
    # Parse IPM if it's a string
    if isinstance(ipm_data, str):
        ipm = parse_ipm_file(ipm_data)
    else:
        ipm = ipm_data
    
    # Convert to radians
    inc_rad = math.radians(inclination)
    tf_rad = math.radians(toolface)
    
    # Get relevant error terms from IPM
    abx = get_error_term_value(ipm, 'ABXY-TI1S', 'e', 's')
    aby = get_error_term_value(ipm, 'ABXY-TI1S', 'e', 's')
    abz = get_error_term_value(ipm, 'ABZ', 'e', 's')
    asx = get_error_term_value(ipm, 'ASXY-TI1S', 'e', 's')
    asy = get_error_term_value(ipm, 'ASXY-TI1S', 'e', 's')
    asz = get_error_term_value(ipm, 'ASZ', 'e', 's')
    
    # Weighting functions for GET (simplified for example)
    wx = math.sin(inc_rad) * math.sin(tf_rad)
    wy = math.sin(inc_rad) * math.cos(tf_rad)
    wz = math.cos(inc_rad)
    
    # Calculate tolerance (3-sigma)
    tolerance = 3 * math.sqrt(
        (abx * wx)**2 + 
        (aby * wy)**2 + 
        (abz * wz)**2 + 
        (asx * wx * 9.8)**2 + 
        (asy * wy * 9.8)**2 + 
        (asz * wz * 9.8)**2
    )
    
    return tolerance

def get_error_term_value(ipm, name, vector='', tie_on=''):
    """Helper function to get error term value or default to zero"""
    term = ipm.get_error_term(name, vector, tie_on)
    return term['value'] if term else 0.0