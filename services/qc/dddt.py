import math
import numpy as np
from models.qc_result import QCResult
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value

def perform_dddt(pipe_depth, wireline_depth, survey, ipm_data):
    """
    Performs Dual Depth Difference Test (DDDT) on pipe and wireline depth measurements
    
    Args:
        pipe_depth (float): Measured depth from pipe tally (m)
        wireline_depth (float): Measured depth from wireline (m)
        survey (dict): Survey data containing:
            - inclination: Survey inclination (degrees)
            - azimuth: Survey azimuth (degrees)
            - true_vertical_depth: True vertical depth (m) (optional)
        ipm_data (dict): Instrument Performance Model data containing error terms
        
    Returns:
        dict: QC test results with:
            - is_valid: Boolean indicating if measurements passed the test
            - pipe_depth: Pipe depth measurement
            - wireline_depth: Wireline depth measurement
            - depth_difference: Difference between pipe and wireline depths
            - tolerance: Calculated tolerance based on IPM
            - details: Additional test details
    """
    # Extract data
    inclination = survey.get('inclination', 0)
    
    # Calculate true vertical depth if not provided
    true_vertical_depth = survey.get('true_vertical_depth')
    if true_vertical_depth is None:
        # Simple approximation assuming straight borehole at current inclination
        true_vertical_depth = pipe_depth * math.cos(math.radians(inclination))
    
    # Calculate depth difference
    depth_difference = pipe_depth - wireline_depth
    
    # Calculate tolerance
    tolerance = calculate_dddt_tolerance(ipm_data, pipe_depth, true_vertical_depth)
    
    # Determine if the depth measurements are valid
    is_valid = abs(depth_difference) <= tolerance
    
    # Create result
    result = QCResult("DDDT")
    result.set_validity(is_valid)
    result.add_measurement("pipe_depth", pipe_depth)
    result.add_measurement("wireline_depth", wireline_depth)
    result.add_error("depth_difference", depth_difference)
    result.add_tolerance("depth_difference", tolerance)  # key now matches
    result.add_detail("true_vertical_depth", true_vertical_depth)
    
    return result.to_dict()

def calculate_dddt_tolerance(ipm_data, depth, true_vertical_depth):
    """
    Calculate tolerance for Dual Depth Difference Test
    
    Args:
        ipm_data (dict): IPM data containing depth error terms
        depth (float): Measured depth (m)
        true_vertical_depth (float): True vertical depth (m)
        
    Returns:
        float: Tolerance value for DDDT
    """
    # Parse IPM if it's string content
    if isinstance(ipm_data, str):
        ipm = parse_ipm_file(ipm_data)
    else:
        ipm = ipm_data
    
    # Get depth error terms from IPM
    # Depth reference errors
    dref_p = get_error_term_value(ipm, 'DREF-PIPE', 'e', 's')
    dref_w = get_error_term_value(ipm, 'DREF-WIRE', 'e', 's')
    
    # Depth scale factor errors
    dsf_p = get_error_term_value(ipm, 'DSF-PIPE', 'e', 's')
    dsf_w = get_error_term_value(ipm, 'DSF-WIRE', 'e', 's')
    
    # Depth stretch errors
    dst_p = get_error_term_value(ipm, 'DST-PIPE', 'e', 's')
    dst_w = get_error_term_value(ipm, 'DST-WIRE', 'e', 's')
    
    # Calculate tolerance (3-sigma) based on equation from the paper
    # ΔΔD = ΔDREF + Dt * ΔDSF + Dt * Dv * ΔDST
    # where ΔDREF = DREF_p - DREF_w, etc.
    
    dref_diff = math.sqrt(dref_p**2 + dref_w**2)
    dsf_diff = math.sqrt(dsf_p**2 + dsf_w**2)
    dst_diff = math.sqrt(dst_p**2 + dst_w**2)
    
    tolerance = 3 * math.sqrt(
        dref_diff**2 +
        (depth * dsf_diff)**2 +
        (true_vertical_depth * dst_diff)**2      # <-- removed extra depth factor
    )
    
    return tolerance