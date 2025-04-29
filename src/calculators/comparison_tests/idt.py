# src/calculators/external_qc_tests/idt.py
import math
import numpy as np
from src.models.qc_result import QCResult

def perform_idt(survey1, survey2, max_stations=15):
    """
    Inclination Difference Test (IDT) - SPE 105558 Appendix 1C
    
    Compares inclinations from two independent surveys using Chi-square statistics
    to verify if they are performing according to their error models.
    
    Parameters
    ----------
    survey1 : list of dict
        Each dict must contain 'depth', 'inclination', and 'error_model' with 'inclination_std'
    survey2 : list of dict
        Each dict must contain 'depth', 'inclination', and 'error_model' with 'inclination_std'
    max_stations : int
        Maximum number of stations to use in test (default: 15)
        
    Returns
    -------
    dict
        QCResult serialized as dict
    """
    # ---------- Validate input data ----------------------------------------------
    if len(survey1) < 3 or len(survey2) < 3:
        return _fail("At least 3 survey stations are required for IDT")
    
    # ---------- Find matching depths between surveys ----------------------------
    survey2_by_depth = {s['depth']: s for s in survey2}
    matching_points = []
    
    for s1 in survey1:
        if s1['depth'] in survey2_by_depth:
            s2 = survey2_by_depth[s1['depth']]
            # Check for required error model data
            if ('error_model' not in s1 or 'inclination_std' not in s1['error_model'] or
                'error_model' not in s2 or 'inclination_std' not in s2['error_model']):
                continue
                
            matching_points.append({
                'depth': s1['depth'],
                'inclination1': s1['inclination'],
                'inclination2': s2['inclination'],
                'std1': s1['error_model']['inclination_std'],
                'std2': s2['error_model']['inclination_std']
            })
    
    if len(matching_points) < 3:
        return _fail("At least 3 matching depths with proper error models required for IDT")
    
    # ---------- Select representative stations (max specified number) -----------
    if len(matching_points) > max_stations:
        # Pick evenly spaced stations across the survey
        indices = np.linspace(0, len(matching_points) - 1, max_stations).astype(int)
        matching_points = [matching_points[i] for i in indices]
    
    # ---------- Calculate Chi-square test statistic ----------------------------
    # Filter points with very small standard deviations
    valid_points = [p for p in matching_points 
                  if math.sqrt(p['std1']**2 + p['std2']**2) >= 0.1]
    
    if len(valid_points) < 3:
        return _fail("Not enough points with sufficient inclination uncertainty")
    
    # Calculate normalized inclination differences
    inclination_diffs = []
    scaled_diffs = []
    
    for point in valid_points:
        diff = point['inclination2'] - point['inclination1']
        inclination_diffs.append(diff)
        
        # Calculate chi-square component for this station
        combined_variance = point['std1']**2 + point['std2']**2
        x_i = diff**2 / combined_variance
        scaled_diffs.append(x_i)
    
    # Sum of Chi-square components
    X_I = sum(scaled_diffs)
    
    # Chi-square test limit for n degrees of freedom at 0.3% significance
    n = len(valid_points)
    Z_limit = _chi_square_limit(n)
    
    # Test result
    is_valid = X_I <= Z_limit
    
    # ---------- Create QCResult ------------------------------------------------
    result = QCResult("IDT")
    result.set_validity(is_valid)
    
    result.add_measurement("chi_square_statistic", X_I)
    result.add_tolerance("chi_square_limit", Z_limit)
    
    result.add_detail("degrees_of_freedom", n)
    result.add_detail("inclination_differences", inclination_diffs)
    result.add_detail("scaled_differences", scaled_diffs)
    result.add_detail("significance_level", "0.3%")
    
    if not is_valid:
        result.add_detail("failure_reason", 
                         "Inclination differences exceed expected model uncertainty")
    
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
    return {"is_valid": False, "error": msg, "test_name": "IDT"}