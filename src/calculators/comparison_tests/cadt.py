# src/calculators/external_qc_tests/cadt.py
import math
import numpy as np
from src.models.qc_result import QCResult
from src.utils.ipm_parser import parse_ipm_file
from src.utils.tolerance import get_error_term_value

# Sidereal Earth rotation rate in degrees/hour
EARTH_RATE_DPH = 15.041067

def perform_cadt(in_run, out_run, average_running_speed, ipm_data):
    """
    Continuous Azimuth Drift Test (CADT) - SPE 105558 Appendix 1B
    
    Tests for gyro drift and random walk by analyzing in-run/out-run azimuth differences.
    
    Parameters
    ----------
    in_run : list of dict
        Each dict must contain 'depth' and 'azimuth'
    out_run : list of dict
        Each dict must contain 'depth' and 'azimuth'
    average_running_speed : float
        Average survey running speed in meters/hour
    ipm_data : str or IPMFile
        Raw IPM content or a parsed IPMFile instance
        
    Returns
    -------
    dict
        QCResult serialized as dict
    """
    # ---------- Validate input data ----------------------------------------------
    if len(in_run) < 10 or len(out_run) < 10:
        return _fail("At least 10 survey stations are required for CADT")
    
    if average_running_speed <= 0:
        return _fail("Average running speed must be positive")
    
    # ---------- Reduce data to evenly spaced apparent surveys ------------------
    # Continuous gyro measurements are affected by short-term oscillations
    # We reduce the data points to smooth these out
    in_run_sorted = sorted(in_run, key=lambda x: x['depth'])
    out_run_sorted = sorted(out_run, key=lambda x: x['depth'])
    
    # Reduce to approximately 100m intervals for smoothing short-term oscillations
    target_interval = 100.0  # meters
    
    reduced_in_run = _reduce_data(in_run_sorted, target_interval)
    reduced_out_run = _reduce_data(out_run_sorted, target_interval)
    
    # ---------- Find matching depths between in-run and out-run ----------------
    # Use interpolation to match depths
    min_depth = max(reduced_in_run[0]['depth'], reduced_out_run[0]['depth'])
    max_depth = min(reduced_in_run[-1]['depth'], reduced_out_run[-1]['depth'])
    
    if max_depth <= min_depth:
        return _fail("No overlapping depth section between in-run and out-run")
    
    # Create evenly spaced depth points in the overlapping section
    target_depths = np.linspace(min_depth, max_depth, min(len(reduced_in_run), len(reduced_out_run)))
    
    # Interpolate azimuth values at target depths
    in_azimuths = _interpolate_azimuths(reduced_in_run, target_depths)
    out_azimuths = _interpolate_azimuths(reduced_out_run, target_depths)
    
    if len(in_azimuths) < 5 or len(out_azimuths) < 5:
        return _fail("Insufficient matching depth points after interpolation")
    
    # ---------- Calculate weighted azimuth differences -------------------------
    # Determine gyro system type from ipm data (default to XY for now)
    gyro_system_type = "XY"  # Future enhancement: detect from IPM
    
    # For all points except the first, calculate geometry-weighted azimuth change difference
    psi_values = []
    for i in range(1, len(target_depths)):
        # Azimuth difference between in-run and out-run at current and previous depth
        delta_A_prev = out_azimuths[i-1] - in_azimuths[i-1]
        delta_A_curr = out_azimuths[i] - in_azimuths[i]
        
        # Difference in azimuth changes
        delta_delta_A = delta_A_curr - delta_A_prev
        
        # Apply geometry weighting based on gyro system type
        # For simplicity, we're assuming XY gyro system which is the most common
        # For XYZ or Z systems, additional inclination information would be needed
        psi = delta_delta_A
        psi_values.append(psi)
    
    # ---------- Calculate linear drift and random walk --------------------------
    if len(psi_values) < 2:
        return _fail("Insufficient data points for drift calculation")
    
    # Average of weighted azimuth differences
    avg_psi = sum(psi_values) / len(psi_values)
    
    # Time difference between first and last depth point in hours
    time_diff_hours = (target_depths[-1] - target_depths[0]) / average_running_speed
    
    # Linear drift in degrees/hour
    gyro_drift = avg_psi / time_diff_hours
    
    # Random walk calculation
    squared_differences = sum((psi - avg_psi)**2 for psi in psi_values)
    gyro_random_walk = math.sqrt(squared_differences) / (time_diff_hours * math.sqrt(len(psi_values) - 1))
    
    # ---------- Check against error model tolerances ---------------------------
    # Parse IPM data
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data
    
    # Get 1σ tolerances from IPM
    sigma_drift = get_error_term_value(ipm, "VD", "e", "s", default=0.2)  # Gyro drift
    sigma_random_walk = get_error_term_value(ipm, "VRW", "e", "s", default=0.2)  # Gyro random walk
    
    # 3σ tolerance for drift
    drift_tolerance = 3.0 * sigma_drift
    
    # Special tolerance formula for random walk from Appendix 1B
    n = len(psi_values)
    Z_0_003_n_minus_2 = _chi_square_limit(n - 2)
    random_walk_tolerance = sigma_random_walk * math.sqrt(Z_0_003_n_minus_2 / (n - 2))
    
    # Validity checks
    valid_drift = abs(gyro_drift) <= drift_tolerance
    valid_random_walk = gyro_random_walk <= random_walk_tolerance
    overall_valid = valid_drift and valid_random_walk
    
    # ---------- Create QCResult ------------------------------------------------
    result = QCResult("CADT")
    result.set_validity(overall_valid)
    
    result.add_measurement("gyro_drift", gyro_drift)
    result.add_measurement("gyro_random_walk", gyro_random_walk)
    result.add_tolerance("drift_tolerance", drift_tolerance)
    result.add_tolerance("random_walk_tolerance", random_walk_tolerance)
    
    result.add_detail("survey_duration_hours", time_diff_hours)
    result.add_detail("reduced_point_count", len(target_depths))
    result.add_detail("avg_weighted_azimuth_diff", avg_psi)
    result.add_detail("gyro_system_type", gyro_system_type)
    
    if not overall_valid:
        if not valid_drift:
            result.add_detail("failure_reason", "Gyro drift exceeds tolerance")
        else:
            result.add_detail("failure_reason", "Gyro random walk exceeds tolerance")
    
    return result.to_dict()

def _reduce_data(data, target_interval):
    """Reduce data to approximately evenly spaced points."""
    if len(data) <= 2:
        return data
    
    # Total depth span
    depth_range = data[-1]['depth'] - data[0]['depth']
    
    # Number of intervals based on target spacing
    n_intervals = max(1, int(depth_range / target_interval))
    
    # Compute new points using averaging over intervals
    reduced_data = []
    indices = np.linspace(0, len(data) - 1, n_intervals + 1).astype(int)
    
    for i in range(len(indices) - 1):
        start_idx = indices[i]
        end_idx = indices[i+1]
        
        segment = data[start_idx:end_idx+1]
        if not segment:
            continue
            
        avg_depth = sum(p['depth'] for p in segment) / len(segment)
        
        # For azimuth, we need to handle the circular nature
        sin_sum = sum(math.sin(math.radians(p['azimuth'])) for p in segment)
        cos_sum = sum(math.cos(math.radians(p['azimuth'])) for p in segment)
        avg_azimuth = math.degrees(math.atan2(sin_sum, cos_sum)) % 360
        
        reduced_data.append({
            'depth': avg_depth,
            'azimuth': avg_azimuth
        })
    
    return reduced_data

def _interpolate_azimuths(survey_data, target_depths):
    """Interpolate azimuth values at specified depths."""
    interpolated = []
    
    depths = [p['depth'] for p in survey_data]
    azimuths = [p['azimuth'] for p in survey_data]
    
    for depth in target_depths:
        if depth < depths[0] or depth > depths[-1]:
            continue
        
        # Find bounding indices
        idx = 0
        while idx < len(depths) - 1 and depths[idx + 1] < depth:
            idx += 1
        
        if depths[idx] == depth:
            # Exact match
            interpolated.append(azimuths[idx])
        elif idx < len(depths) - 1:
            # Linear interpolation with special handling for azimuth wrap
            d1, d2 = depths[idx], depths[idx + 1]
            a1, a2 = azimuths[idx], azimuths[idx + 1]
            
            # Ensure shortest path interpolation for azimuth
            if abs(a2 - a1) > 180:
                if a1 < a2:
                    a1 += 360
                else:
                    a2 += 360
            
            t = (depth - d1) / (d2 - d1)
            interpolated_azimuth = a1 + t * (a2 - a1)
            interpolated.append(interpolated_azimuth % 360)
    
    return interpolated

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
    return {"is_valid": False, "error": msg, "test_name": "CADT"}