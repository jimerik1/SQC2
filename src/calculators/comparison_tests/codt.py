# src/calculators/external_qc_tests/codt.py
import math
import numpy as np
from src.models.qc_result import QCResult

def perform_codt(survey1, survey2, max_stations=15):
    """
    Coordinate Difference Test (CODT) - SPE 105558 Appendix 1E
    
    Checks coordinate differences (lateral, highside, along-hole) between
    two independent surveys using Chi-square statistics.
    
    Parameters
    ----------
    survey1 : list of dict
        Each dict must contain 'depth', 'north', 'east', 'tvd', 'inclination', 'azimuth',
        and 'error_model' with 'lateral_std', 'highside_std', 'alonghole_std'
    survey2 : list of dict
        Each dict must contain the same fields as survey1
    max_stations : int
        Maximum number of stations to use in test (default: 15)
        
    Returns
    -------
    dict
        QCResult serialized as dict
    """
    # ---------- Validate input data ----------------------------------------------
    if len(survey1) < 3 or len(survey2) < 3:
        return _fail("At least 3 survey stations are required for CODT")
    
    # ---------- Find matching depths between surveys ----------------------------
    survey2_by_depth = {s['depth']: s for s in survey2}
    matching_points = []
    
    required_fields = ['north', 'east', 'tvd', 'inclination', 'azimuth', 'error_model']
    error_fields = ['lateral_std', 'highside_std', 'alonghole_std']
    
    for s1 in survey1:
        if s1['depth'] in survey2_by_depth:
            s2 = survey2_by_depth[s1['depth']]
            
            # Check for required fields
            if any(field not in s1 for field in required_fields) or \
               any(field not in s2 for field in required_fields):
                continue
                
            # Check for required error model fields
            if any(field not in s1['error_model'] for field in error_fields) or \
               any(field not in s2['error_model'] for field in error_fields):
                continue
                
            matching_points.append({
                'depth': s1['depth'],
                'north1': s1['north'],
                'east1': s1['east'],
                'tvd1': s1['tvd'],
                'inc1': s1['inclination'],
                'az1': s1['azimuth'],
                'north2': s2['north'],
                'east2': s2['east'],
                'tvd2': s2['tvd'],
                'inc2': s2['inclination'],
                'az2': s2['azimuth'],
                'lateral_std1': s1['error_model']['lateral_std'],
                'highside_std1': s1['error_model']['highside_std'],
                'alonghole_std1': s1['error_model']['alonghole_std'],
                'lateral_std2': s2['error_model']['lateral_std'],
                'highside_std2': s2['error_model']['highside_std'],
                'alonghole_std2': s2['error_model']['alonghole_std']
            })
    
    if len(matching_points) < 3:
        return _fail("At least 3 matching depths with proper error models required for CODT")
    
    # ---------- Select representative stations (max specified number) -----------
    if len(matching_points) > max_stations:
        # Pick evenly spaced stations across the survey
        indices = np.linspace(0, len(matching_points) - 1, max_stations).astype(int)
        matching_points = [matching_points[i] for i in indices]
    
    # ---------- Calculate coordinate differences and Chi-square components ------
    # Filter points with very small standard deviations (< 0.2m)
    min_std = 0.2  # meters
    
    valid_points_lateral = []
    valid_points_highside = []
    valid_points_alonghole = []
    
    # Calculate lateral, highside, and along-hole differences for each point
    for point in matching_points:
        # Calculate NEV coordinate differences
        north_diff = point['north2'] - point['north1']
        east_diff = point['east2'] - point['east1']
        tvd_diff = point['tvd2'] - point['tvd1']
        
        # Calculate average azimuth and inclination (in radians)
        inc_avg = math.radians((point['inc1'] + point['inc2']) / 2)
        az_avg = math.radians((point['az1'] + point['az2']) / 2)
        
        # Transform to lateral, highside, along-hole coordinates
        # Lateral (perpendicular to well direction in horizontal plane)
        lateral_diff = -north_diff * math.sin(az_avg) + east_diff * math.cos(az_avg)
        
        # Highside (perpendicular to well in vertical plane of well azimuth)
        highside_diff = -tvd_diff * math.sin(inc_avg) + \
                       north_diff * math.cos(az_avg) * math.cos(inc_avg) + \
                       east_diff * math.sin(az_avg) * math.cos(inc_avg)
        
        # Along-hole (along well direction)
        alonghole_diff = tvd_diff * math.cos(inc_avg) + \
                        north_diff * math.cos(az_avg) * math.sin(inc_avg) + \
                        east_diff * math.sin(az_avg) * math.sin(inc_avg)
        
        # Combined standard deviations
        lateral_std = math.sqrt(point['lateral_std1']**2 + point['lateral_std2']**2)
        highside_std = math.sqrt(point['highside_std1']**2 + point['highside_std2']**2)
        alonghole_std = math.sqrt(point['alonghole_std1']**2 + point['alonghole_std2']**2)
        
        # Add to valid points lists if standard deviation is sufficient
        if lateral_std >= min_std:
            valid_points_lateral.append({
                'depth': point['depth'],
                'diff': lateral_diff,
                'std': lateral_std
            })
            
        if highside_std >= min_std:
            valid_points_highside.append({
                'depth': point['depth'],
                'diff': highside_diff,
                'std': highside_std
            })
            
        if alonghole_std >= min_std:
            valid_points_alonghole.append({
                'depth': point['depth'],
                'diff': alonghole_diff,
                'std': alonghole_std
            })
    
    # ---------- Calculate Chi-square test statistics ----------------------------
    # Calculate chi-square statistic for each direction
    X_L = sum((p['diff']**2 / p['std']**2) for p in valid_points_lateral) if valid_points_lateral else 0
    X_H = sum((p['diff']**2 / p['std']**2) for p in valid_points_highside) if valid_points_highside else 0
    X_W = sum((p['diff']**2 / p['std']**2) for p in valid_points_alonghole) if valid_points_alonghole else 0
    
    # Degrees of freedom for each test
    n_L = len(valid_points_lateral)
    n_H = len(valid_points_highside)
    n_W = len(valid_points_alonghole)
    
    # Test limits based on Chi-square distribution (0.3% significance)
    Z_limit_L = _chi_square_limit(n_L) if n_L > 0 else 0
    Z_limit_H = _chi_square_limit(n_H) if n_H > 0 else 0
    Z_limit_W = _chi_square_limit(n_W) if n_W > 0 else 0
    
    # Determine validity of each test
    valid_L = n_L == 0 or X_L <= Z_limit_L
    valid_H = n_H == 0 or X_H <= Z_limit_H
    valid_W = n_W == 0 or X_W <= Z_limit_W
    
    # Overall validity
    overall_valid = valid_L and valid_H and valid_W
    
    # ---------- Create QCResult ------------------------------------------------
    result = QCResult("CODT")
    result.set_validity(overall_valid)
    
    # Add measurements and tolerances
    if n_L > 0:
        result.add_measurement("lateral_chi_square", X_L)
        result.add_tolerance("lateral_limit", Z_limit_L)
    
    if n_H > 0:
        result.add_measurement("highside_chi_square", X_H)
        result.add_tolerance("highside_limit", Z_limit_H)
    
    if n_W > 0:
        result.add_measurement("alonghole_chi_square", X_W)
        result.add_tolerance("alonghole_limit", Z_limit_W)
    
    # Add details
    result.add_detail("lateral_points", n_L)
    result.add_detail("highside_points", n_H)
    result.add_detail("alonghole_points", n_W)
    result.add_detail("significance_level", "0.3%")
    
    if n_L > 0:
        result.add_detail("lateral_diffs", [p['diff'] for p in valid_points_lateral])
    
    if n_H > 0:
        result.add_detail("highside_diffs", [p['diff'] for p in valid_points_highside])
    
    if n_W > 0:
        result.add_detail("alonghole_diffs", [p['diff'] for p in valid_points_alonghole])
    
    # Add failure reason if test failed
    if not overall_valid:
        failure_reasons = []
        if not valid_L and n_L > 0:
            failure_reasons.append("Lateral differences exceed tolerance")
        if not valid_H and n_H > 0:
            failure_reasons.append("Highside differences exceed tolerance")
        if not valid_W and n_W > 0:
            failure_reasons.append("Along-hole differences exceed tolerance")
            
        result.add_detail("failure_reason", "; ".join(failure_reasons))
    
    return result.to_dict()

def _chi_square_limit(n):
    """Return the Chi-square test limit for n degrees of freedom at 0.3% significance."""
    # Approximate values for chi-square distribution at 0.3% significance
    chi_square_table = {
        1: 8.8,
        2: 11.6,
        3: 13.9,
        4: 16.0, 
        5: 18.0,
        10: 27.9,
        15: 34.4,
        20: 40.3,
        30: 51.0,
        50: 76.1,
        100: 143.0
    }
    
    # Direct lookup if we have the exact value
    if n in chi_square_table:
        return chi_square_table[n]
    
    # Linear interpolation for values in between
    keys = sorted(chi_square_table.keys())
    if n < keys[0]:
        return chi_square_table[keys[0]]
    if n > keys[-1]:
        return chi_square_table[keys[-1]]
    
    # Find bounding values
    lower_key = max(k for k in keys if k <= n)
    upper_key = min(k for k in keys if k >= n)
    
    # Exact match
    if lower_key == upper_key:
        return chi_square_table[lower_key]
    
    # Interpolate
    lower_val = chi_square_table[lower_key]
    upper_val = chi_square_table[upper_key]
    proportion = (n - lower_key) / (upper_key - lower_key)
    
    return lower_val + proportion * (upper_val - lower_val)

def _fail(msg):
    """Return a standardized error response."""
    return {"is_valid": False, "error": msg, "test_name": "CODT"}