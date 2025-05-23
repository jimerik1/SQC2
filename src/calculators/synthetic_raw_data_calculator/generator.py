# src/calculators/synthetic_raw_data_calculator/generator.py
import numpy as np
import pandas as pd
from scipy.optimize import least_squares, minimize, differential_evolution

def generate_synthetic_raw_data(trajectory_data, magnetic_dip=73.484, magnetic_field_strength=51541.551, 
                              gravity=9.81, declination=1.429, add_noise=False, noise_level=0.001,
                              optimization_params=None):
    """
    Generate raw survey data using numerical optimization to match all parameters simultaneously.
    Enhanced with improved stability for low-inclination wells and rotating priority system.
    
    Parameters:
    -----------
    trajectory_data : dict or pandas.DataFrame
        Dictionary or DataFrame containing trajectory data (Inc, Azi, Depth)
    magnetic_dip : float
        Magnetic dip angle in degrees
    magnetic_field_strength : float
        Total magnetic field strength in nT
    gravity : float
        Gravity value in m/s²
    declination : float
        Magnetic declination in degrees
    add_noise : bool
        Whether to add random noise to the data
    noise_level : float
        Relative magnitude of noise to add
    optimization_params : dict
        Dictionary of parameters for controlling the optimization:
        - primary_method: str - Method for first optimization ('trf', 'lm', 'dogbox')
        - fallback_methods: list - List of fallback methods to try
        - max_iter_primary: int - Max iterations for primary method
        - max_iter_fallback: int - Max iterations for fallback methods
        - ftol: float - Function tolerance for convergence
        - xtol: float - Parameter tolerance for convergence
        - priority_rotation: bool - Whether to rotate through different parameter priorities
        - priority_weights: list - List of weight dictionaries for different priority combinations
        - low_inc_threshold: float - Threshold for low inclination special handling (degrees)
        - azi_success_threshold: float - Maximum acceptable azimuth error in degrees
        - mag_success_threshold: float - Maximum acceptable field magnitude error in nT
        - smoothing_enabled: bool - Whether to apply smoothing between solutions
        - extrapolation_enabled: bool - Whether to extrapolate from previous solutions
        
    Returns:
    --------
    dict: Dictionary with raw sensor data, original trajectory data, and stats
    """
    # Convert dictionary to DataFrame if necessary
    if isinstance(trajectory_data, dict):
        trajectory_df = pd.DataFrame(trajectory_data)
    else:
        trajectory_df = trajectory_data.copy()
    
    # Default optimization parameters with enhanced configuration
    default_params = {
        'primary_method': 'trf',
        'fallback_methods': ['lm', 'Nelder-Mead', 'COBYLA', 'differential_evolution'],
        'max_iter_primary': 500,
        'max_iter_fallback': 300,
        'ftol': 1e-11,
        'xtol': 1e-11,
        'priority_rotation': True,  # Enable rotation of priorities
        'priority_weights': [  # Different weight combinations to try
            {'dip_weight': 10.0, 'azi_weight': 5.0, 'mag_weight': 1.0},
            {'dip_weight': 1.0, 'azi_weight': 10.0, 'mag_weight': 1.0},
            {'dip_weight': 1.0, 'azi_weight': 1.0, 'mag_weight': 10.0},
        ],
        'low_inc_threshold': 3.0,  # Degrees below which special handling is used
        'azi_success_threshold': 1.0,  # degrees
        'mag_success_threshold': 1000.0,   # nT
        'smoothing_enabled': True,  # Enable solution smoothing
        'extrapolation_enabled': True,  # Enable extrapolation from previous points
        'smoothing_factor': 0.3,  # Factor for solution smoothing (0-1)
    }
    
    # Update with user-provided parameters if any
    if optimization_params is not None:
        default_params.update(optimization_params)
    
    # Use updated parameters
    opt_params = default_params
    
    n_points = len(trajectory_df)
    Gx = np.zeros(n_points)
    Gy = np.zeros(n_points)
    Gz = np.zeros(n_points)
    Bx = np.zeros(n_points)
    By = np.zeros(n_points)
    Bz = np.zeros(n_points)
    
    # Convert angles to radians
    dip_rad = np.radians(magnetic_dip)
    dec_rad = np.radians(declination)
    
    # Earth's magnetic field components in NED
    Bh = magnetic_field_strength * np.cos(dip_rad)
    Bz_geo = magnetic_field_strength * np.sin(dip_rad)
    Bx_geo = Bh * np.cos(dec_rad)
    By_geo = Bh * np.sin(dec_rad)
    
    success_count = 0
    primary_success = 0
    fallback_success = 0
    failure_count = 0
    special_case_count = 0
    
    # Dictionary to track success per priority configuration
    priority_success = {str(weights): 0 for weights in opt_params['priority_weights']}
    
    # Keep track of previous solution for continuity
    previous_solution = None
    
    for i in range(n_points):
        inc = np.radians(trajectory_df['Inc'].values[i])
        azi = np.radians(trajectory_df['Azi'].values[i])
        depth = trajectory_df['Depth'].values[i] if 'Depth' in trajectory_df.columns else i
        
        # Calculate accelerometer values
        sin_inc = np.sin(inc)
        cos_inc = np.cos(inc)
        sin_azi = np.sin(azi)
        cos_azi = np.cos(azi)
        
        Gx[i] = gravity * sin_inc * cos_azi
        Gy[i] = gravity * sin_inc * sin_azi
        Gz[i] = gravity * cos_inc
        
        # Enhanced low-inclination handling
        if inc < np.radians(opt_params['low_inc_threshold']):
            # Use more robust low-inclination handling
            # Use a more gradual transition between vertical and non-vertical solutions
            transition_factor = inc / np.radians(opt_params['low_inc_threshold'])
            
            # Base solution for vertical case
            vertical_solution = [
                magnetic_field_strength * np.cos(dip_rad) * np.cos(azi),
                magnetic_field_strength * np.cos(dip_rad) * np.sin(azi),
                magnetic_field_strength * np.sin(dip_rad)
            ]
            
            # If we have a previous solution and extrapolation is enabled, use it for stability
            if previous_solution is not None and opt_params['extrapolation_enabled']:
                # Calculate a blended solution
                blended_solution = [
                    vertical_solution[0] * (1-transition_factor) + previous_solution[0] * transition_factor,
                    vertical_solution[1] * (1-transition_factor) + previous_solution[1] * transition_factor,
                    vertical_solution[2] * (1-transition_factor) + previous_solution[2] * transition_factor
                ]
                Bx[i], By[i], Bz[i] = blended_solution
                
                # Verify and adjust if needed
                current_mag = np.sqrt(Bx[i]**2 + By[i]**2 + Bz[i]**2)
                if abs(current_mag - magnetic_field_strength) > opt_params['mag_success_threshold']:
                    # Scale to maintain correct field magnitude
                    scale = magnetic_field_strength / current_mag
                    Bx[i] *= scale
                    By[i] *= scale
                    Bz[i] *= scale
                
                previous_solution = [Bx[i], By[i], Bz[i]]
                special_case_count += 1
                continue
            else:
                # Use the vertical solution directly
                Bx[i], By[i], Bz[i] = vertical_solution
                previous_solution = vertical_solution
                special_case_count += 1
                continue
        
        # Define function to create residual function with specific weights
        def create_residual_function(weights):
            def residuals(B_vec):
                Bx_val, By_val, Bz_val = B_vec
                
                # Calculate azimuth from current B-field
                num = Gx[i] * By_val - Gy[i] * Bx_val
                den = Bz_val * (Gx[i]**2 + Gy[i]**2) - Gz[i] * (Gx[i] * Bx_val + Gy[i] * By_val)
                calc_azi = np.arctan2(num, den)
                
                # Calculate field magnitude
                calc_mag = np.sqrt(Bx_val**2 + By_val**2 + Bz_val**2)
                
                # Calculate dip angle (using standard method matching validation code)
                G_norm = np.array([Gx[i], Gy[i], Gz[i]]) / np.sqrt(Gx[i]**2 + Gy[i]**2 + Gz[i]**2)
                B_norm = np.array([Bx_val, By_val, Bz_val]) / calc_mag
                dot_product = np.dot(B_norm, G_norm)
                calc_dip = np.arcsin(np.clip(dot_product, -1.0, 1.0))
                
                # Calculate errors with weights
                azi_error = np.sin(calc_azi - azi) * weights['azi_weight']
                mag_error = (calc_mag - magnetic_field_strength) / magnetic_field_strength * weights['mag_weight']
                dip_error = (calc_dip - dip_rad) * weights['dip_weight']
                
                return [azi_error, mag_error, dip_error]
            return residuals
        
        # Define function to create objective function from residual function
        def create_objective_function(residual_func):
            def objective(B_vec):
                errors = residual_func(B_vec)
                return np.sum(np.array(errors) ** 2)
            return objective
        
        # Get initial guess
        if previous_solution is not None and opt_params['extrapolation_enabled']:
            # Use previous solution as initial guess
            B_tool_initial = previous_solution
        else:
            # Generate initial guess based on rotation from NED to tool frame
            rotation_matrix = np.array([
                [sin_inc * cos_azi, sin_inc * sin_azi, cos_inc],
                [sin_azi, -cos_azi, 0],
                [cos_inc * cos_azi, cos_inc * sin_azi, -sin_inc]
            ])
            
            B_ned = np.array([Bx_geo, By_geo, Bz_geo])
            B_tool_initial = np.dot(rotation_matrix, B_ned)
        
        # Try optimization with different priority weights
        solved = False
        current_solution = B_tool_initial.copy()  # Default in case all optimizations fail
        
        # Determine weight combinations to try
        if opt_params['priority_rotation']:
            weight_combinations = opt_params['priority_weights']
        else:
            # Just use the first weight combination
            weight_combinations = [opt_params['priority_weights'][0]]
        
        # Try each weight combination
        for weights in weight_combinations:
            if solved:
                break
                
            residual_func = create_residual_function(weights)
            objective_func = create_objective_function(residual_func)
            
            # Try optimization with primary method
            try:
                result = least_squares(
                    residual_func, 
                    B_tool_initial, 
                    method=opt_params['primary_method'],
                    ftol=opt_params['ftol'], 
                    xtol=opt_params['xtol'],
                    max_nfev=opt_params['max_iter_primary']
                )
                
                # Check if converged with good enough results
                current_solution = result.x
                
                # Calculate metrics for evaluation
                num = Gx[i] * current_solution[1] - Gy[i] * current_solution[0]
                den = current_solution[2] * (Gx[i]**2 + Gy[i]**2) - Gz[i] * (Gx[i] * current_solution[0] + Gy[i] * current_solution[1])
                final_azi = np.degrees(np.arctan2(num, den))
                final_mag = np.sqrt(current_solution[0]**2 + current_solution[1]**2 + current_solution[2]**2)
                target_azi = np.degrees(azi)
                azi_diff = abs(final_azi - target_azi) % 360
                azi_diff = min(azi_diff, 360 - azi_diff)
                mag_diff = final_mag - magnetic_field_strength
                
                # Check if solution is acceptable
                if azi_diff < opt_params['azi_success_threshold'] and abs(mag_diff) < opt_params['mag_success_threshold']:
                    success_count += 1
                    primary_success += 1
                    priority_success[str(weights)] = priority_success.get(str(weights), 0) + 1
                    solved = True
                    break
                else:
                    # Try fallback methods if primary method didn't work well enough
                    for method in opt_params['fallback_methods']:
                        try:
                            if method == 'differential_evolution':
                                # Global optimization
                                bounds = [(current_solution[0] - magnetic_field_strength/2, current_solution[0] + magnetic_field_strength/2),
                                          (current_solution[1] - magnetic_field_strength/2, current_solution[1] + magnetic_field_strength/2),
                                          (current_solution[2] - magnetic_field_strength/2, current_solution[2] + magnetic_field_strength/2)]
                                
                                result = differential_evolution(
                                    objective_func,
                                    bounds,
                                    maxiter=opt_params['max_iter_fallback'],
                                    tol=opt_params['ftol'],
                                    polish=True
                                )
                                current_solution = result.x
                            elif method == 'lm':
                                # LM method for least_squares
                                result = least_squares(
                                    residual_func,
                                    current_solution,
                                    method='lm',
                                    ftol=opt_params['ftol'],
                                    xtol=opt_params['xtol'],
                                    max_nfev=opt_params['max_iter_fallback']
                                )
                                current_solution = result.x
                            else:
                                # General minimize methods
                                result = minimize(
                                    objective_func,
                                    current_solution,
                                    method=method,
                                    tol=opt_params['ftol'],
                                    options={'maxiter': opt_params['max_iter_fallback']}
                                )
                                current_solution = result.x
                                
                            # Check results
                            num = Gx[i] * current_solution[1] - Gy[i] * current_solution[0]
                            den = current_solution[2] * (Gx[i]**2 + Gy[i]**2) - Gz[i] * (Gx[i] * current_solution[0] + Gy[i] * current_solution[1])
                            final_azi = np.degrees(np.arctan2(num, den))
                            final_mag = np.sqrt(current_solution[0]**2 + current_solution[1]**2 + current_solution[2]**2)
                            target_azi = np.degrees(azi)
                            azi_diff = abs(final_azi - target_azi) % 360
                            azi_diff = min(azi_diff, 360 - azi_diff)
                            mag_diff = final_mag - magnetic_field_strength
                            
                            if azi_diff < opt_params['azi_success_threshold'] and abs(mag_diff) < opt_params['mag_success_threshold']:
                                success_count += 1
                                fallback_success += 1
                                priority_success[str(weights)] = priority_success.get(str(weights), 0) + 1
                                solved = True
                                break
                            
                        except Exception:
                            continue
                    
                    # Break the outer loop if a method succeeded
                    if solved:
                        break
            
            except Exception:
                pass  # Continue to next weight combination
        
        # If all optimization approaches failed, use direct calculation
        if not solved:
            failure_count += 1
            
            # Direct calculation of By
            try:
                # Handle special cases for cardinal azimuths
                if np.abs(np.tan(azi)) < 1e-10 or np.abs(np.tan(azi)) > 1e10:
                    if np.abs(np.cos(azi)) > 0.7:  # Close to 0 or 180 degrees
                        By_value = (Gy[i] * current_solution[0]) / Gx[i]
                    else:  # Close to 90 or 270 degrees
                        By_value = ((current_solution[2] * (Gx[i]**2 + Gy[i]**2) - 
                                     Gz[i] * Gx[i] * current_solution[0]) / (Gz[i] * Gy[i]))
                else:
                    # Standard calculation
                    By_value = (np.tan(azi) * current_solution[2] * (Gx[i]**2 + Gy[i]**2) -
                                np.tan(azi) * Gz[i] * Gx[i] * current_solution[0] +
                                Gy[i] * current_solution[0]) / (Gx[i] + np.tan(azi) * Gz[i] * Gy[i])
                
                # Update solution
                current_solution[1] = By_value
                
                # Scale to maintain correct field magnitude
                current_mag = np.sqrt(np.sum(current_solution**2))
                scale = magnetic_field_strength / current_mag
                current_solution *= scale
                
            except Exception:
                # Try a more aggressive approach if direct calculation fails
                try:
                    # Use a robust optimizer as emergency fallback
                    result = differential_evolution(
                        lambda B_vec: (np.sqrt(B_vec[0]**2 + B_vec[1]**2 + B_vec[2]**2) - magnetic_field_strength)**2 + 
                                      100 * np.sin(np.arctan2(Gx[i] * B_vec[1] - Gy[i] * B_vec[0], 
                                                             B_vec[2] * (Gx[i]**2 + Gy[i]**2) - Gz[i] * (Gx[i] * B_vec[0] + Gy[i] * B_vec[1])) - azi)**2,
                        [(-magnetic_field_strength, magnetic_field_strength),
                         (-magnetic_field_strength, magnetic_field_strength),
                         (-magnetic_field_strength, magnetic_field_strength)],
                        maxiter=100,
                        tol=1e-8
                    )
                    current_solution = result.x
                except Exception:
                    # If all else fails, use initial guess and scale it
                    current_mag = np.sqrt(np.sum(B_tool_initial**2))
                    if current_mag > 0:
                        scale = magnetic_field_strength / current_mag
                        current_solution = B_tool_initial * scale
        
        # Store final values
        Bx[i], By[i], Bz[i] = current_solution
        
        # If smoothing is enabled and not the first point, consider smoothing
        if i > 0 and opt_params['smoothing_enabled'] and (not solved):
            smoothing_factor = opt_params['smoothing_factor']
            orig_solution = [Bx[i], By[i], Bz[i]]
            
            # Blend with previous solution
            Bx[i] = Bx[i] * (1 - smoothing_factor) + Bx[i-1] * smoothing_factor
            By[i] = By[i] * (1 - smoothing_factor) + By[i-1] * smoothing_factor
            Bz[i] = Bz[i] * (1 - smoothing_factor) + Bz[i-1] * smoothing_factor
            
            # Rescale to maintain field strength
            current_mag = np.sqrt(Bx[i]**2 + By[i]**2 + Bz[i]**2)
            scale = magnetic_field_strength / current_mag
            Bx[i] *= scale
            By[i] *= scale
            Bz[i] *= scale
            
            # Verify the smoothed solution
            num = Gx[i] * By[i] - Gy[i] * Bx[i]
            den = Bz[i] * (Gx[i]**2 + Gy[i]**2) - Gz[i] * (Gx[i] * Bx[i] + Gy[i] * By[i])
            smoothed_azi = np.degrees(np.arctan2(num, den))
            target_azi = np.degrees(azi)
            azi_diff_smoothed = abs(smoothed_azi - target_azi) % 360
            azi_diff_smoothed = min(azi_diff_smoothed, 360 - azi_diff_smoothed)
            
            # If smoothing made things worse, revert
            if i > 1 and azi_diff_smoothed > azi_diff:
                Bx[i], By[i], Bz[i] = orig_solution
        
        # Store this solution for use in the next iteration
        previous_solution = [Bx[i], By[i], Bz[i]]
    
    # Add noise if requested
    if add_noise:
        Gx += np.random.normal(0, noise_level * gravity, n_points)
        Gy += np.random.normal(0, noise_level * gravity, n_points)
        Gz += np.random.normal(0, noise_level * gravity, n_points)
        Bx += np.random.normal(0, noise_level * magnetic_field_strength, n_points)
        By += np.random.normal(0, noise_level * magnetic_field_strength, n_points)
        Bz += np.random.normal(0, noise_level * magnetic_field_strength, n_points)
    
    # Create output data
    result_data = {
        'Depth': trajectory_df['Depth'].tolist(),
        'Inc': trajectory_df['Inc'].tolist(),
        'Azi': trajectory_df['Azi'].tolist(),
        'Gx': Gx.tolist(),
        'Gy': Gy.tolist(),
        'Gz': Gz.tolist(),
        'Bx': Bx.tolist(),
        'By': By.tolist(),
        'Bz': Bz.tolist()
    }
    
    # Add toolface if it exists in input
    if 'tfo' in trajectory_df.columns:
        result_data['tfo'] = trajectory_df['tfo'].tolist()
    
    # Add stats for diagnostics
    stats = {
        'total_points': n_points,
        'success_count': success_count,
        'primary_success': primary_success,
        'fallback_success': fallback_success,
        'failure_count': failure_count,
        'special_case_count': special_case_count,
        'priority_success': {k: v for k, v in priority_success.items() if v > 0}
    }
    
    return {
        'sensor_data': result_data,
        'stats': stats,
        'parameters': {
            'magnetic_dip': magnetic_dip,
            'magnetic_field_strength': magnetic_field_strength,
            'gravity': gravity,
            'declination': declination,
            'noise_added': add_noise,
            'noise_level': noise_level if add_noise else 0
        }
    }

def validate_synthetic_data(sensor_data, magnetic_dip=73.484, magnetic_field_strength=51541.551, 
                          gravity=9.81, declination=1.429):
    """
    Validate synthetic data using standard industry formulas.
    
    Parameters:
    -----------
    sensor_data : dict
        Dictionary with raw sensor and trajectory data
    magnetic_dip : float
        Magnetic dip angle in degrees
    magnetic_field_strength : float
        Total magnetic field strength in nT
    gravity : float
        Gravity value in m/s²
    declination : float
        Magnetic declination in degrees
        
    Returns:
    --------
    dict: Dictionary with validation results
    """
    # Extract raw data
    data = sensor_data['sensor_data'] if 'sensor_data' in sensor_data else sensor_data
    
    # Convert to numpy arrays
    Depth = np.array(data['Depth'])
    Inc = np.array(data['Inc'])
    Azi = np.array(data['Azi'])
    Gx = np.array(data['Gx'])
    Gy = np.array(data['Gy'])
    Gz = np.array(data['Gz'])
    Bx = np.array(data['Bx'])
    By = np.array(data['By'])
    Bz = np.array(data['Bz'])
    
    # Calculate total magnitudes
    G = np.sqrt(Gx**2 + Gy**2 + Gz**2)
    B = np.sqrt(Bx**2 + By**2 + Bz**2)
    
    # Calculate inclination
    inc_calc = np.degrees(np.arccos(np.clip(Gz / G, -1.0, 1.0)))
    
    # Calculate azimuth
    azimuth = np.zeros(len(Gx))
    
    for i in range(len(Gx)):
        # Standard azimuth calculation
        numerator = Gx[i] * By[i] - Gy[i] * Bx[i]
        denominator = Bz[i] * (Gx[i]**2 + Gy[i]**2) - Gz[i] * (Gx[i] * Bx[i] + Gy[i] * By[i])
        
        # Directly compute the azimuth using arctan2
        azimuth[i] = np.degrees(np.arctan2(numerator, denominator))
        
        # Ensure 0-360 range
        if azimuth[i] < 0:
            azimuth[i] += 360
    
    # Calculate magnetic dip angle
    dip_calc = np.zeros(len(Gx))
    for i in range(len(Gx)):
        # Dot product of normalized G and B vectors gives cos(angle between them)
        g_norm = np.array([Gx[i], Gy[i], Gz[i]]) / G[i]
        b_norm = np.array([Bx[i], By[i], Bz[i]]) / B[i]
        dot_product = np.dot(g_norm, b_norm)
        # Magnetic dip is 90° minus this angle (in the northern hemisphere)
        dip_calc[i] = np.degrees(np.arcsin(np.clip(dot_product, -1.0, 1.0)))
    
    # Calculate differences
    inc_diff = Inc - inc_calc
    azi_diff = np.minimum(abs(Azi - azimuth), abs(360 - abs(Azi - azimuth)))
    dip_diff = magnetic_dip - dip_calc
    b_diff = magnetic_field_strength - B
    
    # Create validation result
    validation_result = {
        'Depth': Depth.tolist(),
        'Inc_Original': Inc.tolist(),
        'Inc_Calculated': inc_calc.tolist(),
        'Inc_Diff': inc_diff.tolist(),
        'Azi_Original': Azi.tolist(),
        'Azi_Calculated': azimuth.tolist(),
        'Azi_Diff': azi_diff.tolist(),
        'Dip_Original': [magnetic_dip] * len(Gx),
        'Dip_Calculated': dip_calc.tolist(),
        'Dip_Diff': dip_diff.tolist(),
        'B_Original': [magnetic_field_strength] * len(Gx),
        'B_Calculated': B.tolist(),
        'B_Diff': b_diff.tolist(),
        'G_Magnitude': G.tolist()
    }
    
    # Add summary statistics
    validation_stats = {
        'inc_mean_diff': float(np.mean(np.abs(inc_diff))),
        'inc_max_diff': float(np.max(np.abs(inc_diff))),
        'azi_mean_diff': float(np.mean(azi_diff)),
        'azi_max_diff': float(np.max(azi_diff)),
        'dip_mean_diff': float(np.mean(np.abs(dip_diff))),
        'dip_max_diff': float(np.max(np.abs(dip_diff))),
        'b_mean_diff': float(np.mean(np.abs(b_diff))),
        'b_max_diff': float(np.max(np.abs(b_diff)))
    }
    
    return {
        'validation_data': validation_result,
        'validation_stats': validation_stats
    }