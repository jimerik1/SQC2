# src/calculators/sag_correction/calculator.py
from math import degrees, radians, pi
import numpy as np
from typing import List, Dict, Any, Optional

from src.calculators.sag_correction.models import (
    BHA, BHAElement, Stabilizer, Trajectory, Material, SagResult
)
from src.calculators.sag_correction.bha_converter import bha_to_calculation_inputs
from src.calculators.sag_correction.coordinate_descent import coordinate_descent
from src.calculators.sag_correction.beam_sections import calculate_beam_sections

def calculate_sag_correction(
    trajectory: List[Dict[str, float]],
    bha: Dict[str, Any],
    sensor_position: float,
    mud_weight: float,
    dni_uphole_length: float = 25.0,
    physical_constants: Optional[Dict[str, float]] = None,
    toolface: float = 0.0
) -> Dict[str, Any]:
    """
    Perform BHA sag correction calculation.
    
    Args:
        trajectory: List of survey points containing md, inc, and optional azi
        bha: Dictionary with BHA structure and stabilizers
        sensor_position: Distance from D&I sensor to bit (meters)
        mud_weight: Mud weight (g/ml)
        dni_uphole_length: Uphole length to model from D&I sensor (meters)
        physical_constants: Dictionary with physical constants
        toolface: Toolface angle (degrees)
        
    Returns:
        Dictionary with survey results and grid data
    """
    # Use default physical constants if not provided
    if physical_constants is None:
        physical_constants = {
            'ro_steel': 7850.0,  # kg/m³
            'e_steel': 2.05e11,  # Pa
            'e_nmag': 1.90e11    # Pa
        }
    
    # Convert input data to model objects
    bha_obj = parse_bha(bha, sensor_position)
    traj_obj = parse_trajectory(trajectory)
    
    # Calculate sag correction for each survey point
    survey_results = []
    all_sag_results = []
    grid_data = []
    current_result = None
    
    for station in traj_obj:
        # Calculate sag for this station
        segment = get_windowed_trajectory(traj_obj, station.md, 200.0)  # Using a 200m lookback window
        
        result = calculate_sag_for_station(
            bha=bha_obj,
            md_bit=station.md,
            trajectory=segment,
            steer_toolface=toolface,
            mud_weight=mud_weight,
            dni_uphole_length=dni_uphole_length,
            physical_constants=physical_constants
        )
        
        all_sag_results.append(result)
        
        # Store results for each survey point
        survey_results.append({
            'md': station.md,
            'original_inc': station.inc,
            'sag': degrees(result.sag),
            'corrected_inc': station.inc + degrees(result.sag),
            'valid': result.valid
        })
        
        # Save the most recent result for grid data
        current_result = result
    
    # Generate grid data from the last calculation
    if current_result:
        for i in range(len(current_result.grid)):
            grid_data.append({
                'z_from_bit_m': float(current_result.grid[i]),
                'deflection_m': float(current_result.opt[i] - current_result.mid[i]),
                'slope_deg': float(degrees(current_result.slope[i])),
                'moment_Nm': float(current_result.moment[i]),
                'shear_N': float(current_result.shear[i])
            })
    
    # Compile the final response
    response = {
        'survey_results': survey_results,
        'grid_data': grid_data,
        'sensor_position': sensor_position,
        'dni_uphole_length': dni_uphole_length
    }
    
    return response

def parse_bha(bha_data: Dict[str, Any], sensor_position: float) -> BHA:
    """
    Parse BHA data from the request into a BHA object.
    
    Args:
        bha_data: Dictionary with BHA structure and stabilizers
        sensor_position: Distance from D&I sensor to bit
        
    Returns:
        BHA object
    """
    # Parse BHA elements
    structure = []
    for elem in bha_data['structure']:
        material = Material.NON_MAGNETIC if elem.get('material', '').upper() == 'NON_MAGNETIC' else Material.STEEL
        structure.append(BHAElement(
            description=elem['description'],
            od=elem['od'],
            id=elem['id'],
            max_od=elem['max_od'],
            length=elem['length'],
            weight=elem['weight'],
            material=material
        ))
    
    # Parse stabilizers
    stabilizers = []
    for stab in bha_data.get('stabilizers', []):
        stabilizers.append(Stabilizer(
            blade_od=stab['blade_od'],
            distance_to_bit=stab['distance_to_bit'],
            length=stab['length']
        ))
    
    # Create and return the BHA object
    return BHA(
        structure=structure,
        stabilizers=stabilizers,
        dni_to_bit=sensor_position,
        # Default values for bend attributes
        bend_angle=0.0,
        bend_to_bit=0.0
    )

def parse_trajectory(traj_data: List[Dict[str, float]]) -> List[Trajectory]:
    """
    Parse trajectory data from the request into a list of Trajectory objects.
    
    Args:
        traj_data: List of survey points
        
    Returns:
        List of Trajectory objects
    """
    return [Trajectory(md=point['md'], inc=point['inc']) for point in traj_data]

def get_windowed_trajectory(
    all_surveys: List[Trajectory],
    md_bit: float,
    lookback: float = 60.0
) -> List[Trajectory]:
    """
    Return all surveys within `lookback` metres above the current bit MD.
    
    Args:
        all_surveys: List of all survey points
        md_bit: Measured depth at bit
        lookback: Lookback distance
        
    Returns:
        List of survey points within the lookback window
    """
    # Sort surveys by measured depth
    sorted_surveys = sorted(all_surveys, key=lambda s: s.md)
    
    # Find surveys within the lookback window
    result = [s for s in sorted_surveys if md_bit - lookback <= s.md <= md_bit]
    
    # If no surveys found, include at least the closest survey
    if not result and sorted_surveys:
        closest = min(sorted_surveys, key=lambda s: abs(s.md - md_bit))
        result = [closest]
    
    return result

def calculate_sag_for_station(
    bha: BHA,
    md_bit: float,
    trajectory: List[Trajectory],
    steer_toolface: float,
    mud_weight: float,
    dni_uphole_length: float,
    physical_constants: Dict[str, float]
) -> SagResult:
    """
    Calculate sag correction for a single survey station.
    
    Args:
        bha: BHA object
        md_bit: Measured depth at bit
        trajectory: List of trajectory points
        steer_toolface: Toolface angle in degrees
        mud_weight: Mud weight in g/ml
        dni_uphole_length: Uphole length to model from D&I sensor
        physical_constants: Dictionary with physical constants
        
    Returns:
        SagResult object
    """
    # Convert toolface to radians
    steer_toolface_rad = radians(steer_toolface)
    
    # Convert trajectory to numpy array
    traj_array = np.array([[st.md, radians(st.inc)] for st in trajectory])
    
    # Choose grid spacing based on inclination
    avg_inc = (trajectory[0].inc + trajectory[-1].inc) / 2
    dz = 1.5 if avg_inc < 10 else 0.75  # finer resolution for low inclination
    eps = 1e-7  # convergence threshold
    
    # Run the optimization to find BHA position
    z_cur, x_opt, x_low, x_top, bha_od, bha_id, ei, valid = optimize_bha_position(
        bha, steer_toolface_rad, mud_weight, md_bit, traj_array, dz, eps,
        dni_uphole_length, physical_constants
    )
    
    # Calculate midline position
    x_mid = (x_low + x_top) / 2
    
    # Calculate sag correction
    sag = calculate_sag_from_position(dz, x_opt - x_mid, bha.dni_to_bit)
    
    # Calculate beam sections (slope, moment, shear)
    sections = calculate_beam_sections(z_cur, x_opt, ei, dz)
    
    # Return comprehensive results
    return SagResult(
        sag=sag,
        grid=z_cur,
        opt=x_opt,
        low=x_low,
        top=x_top,
        mid=x_mid,
        od=bha_od,
        id=bha_id,
        valid=valid,
        slope=sections["theta"],
        moment=sections["moment"],
        shear=sections["shear"]
    )

def optimize_bha_position(
    bha: BHA,
    toolface: float,
    mud_weight: float,
    md_bit: float,
    traj: np.ndarray,
    dz: float,
    eps: float,
    dni_uphole_length: float,
    physical_constants: Dict[str, float]
) -> tuple:
    """
    Optimize the BHA position within the wellbore constraints.
    
    Args:
        bha: The BHA object
        toolface: Toolface angle in radians
        mud_weight: Mud weight in g/ml
        md_bit: Measured depth at bit
        traj: Array of trajectory points (MD and inclination)
        dz: Grid spacing in meters
        eps: Convergence threshold
        dni_uphole_length: Uphole length to model from D&I sensor
        physical_constants: Dictionary with physical constants
        
    Returns:
        Tuple containing grid, optimized position, boundaries, etc.
    """
    # Extract physical constants
    ro_steel = physical_constants['ro_steel']
    
    # Calculate apparent bend angle (projected onto the plane of deflection)
    apparent_bend_angle = bha.bend_angle * np.cos(toolface)
    
    # Convert BHA to calculation inputs
    ei, bha_od, bha_id, linear_weight, bend_ind = bha_to_calculation_inputs(
        bha, dz, physical_constants, dni_uphole_length
    )
    
    # Create grid coordinates
    z_cur = np.cumsum(dz * np.ones_like(ei)) - dz
    
    # Convert trajectory to BHA coordinates
    x_mid, inc_grid, inc_avg = trajectory_to_coordinates(z_cur, md_bit, traj)
    
    # Calculate lateral force due to gravity (q = weight × sin(inclination))
    q = linear_weight * (1 - mud_weight / ro_steel) * np.sin(inc_grid)
    
    # Calculate borehole enlargement
    borehole_enlargement = 0.025 * bha.structure[0].od  # Default safety factor
    
    # Calculate wellbore radius at each point
    radius = 0.5 * (np.max(bha_od) * np.ones_like(ei) + borehole_enlargement)
    
    # Calculate wellbore boundaries
    x_low = x_mid - radius  # Lower bound
    x_top = x_mid + radius  # Upper bound
    
    # Set initial position
    if inc_avg > 2.5 * pi / 180:
        # For significant inclination, start from low side
        x_opt = x_low + bha_od / 2.0
    else:
        # For near-vertical, start from middle
        x_opt = (x_low + x_top) / 2.0
    
    # Run coordinate descent to optimize position
    x_opt, valid_flag = coordinate_descent(
        x_opt, ei, q, bha_od, x_low, x_top,
        dz, bend_ind, apparent_bend_angle, eps
    )
    
    return z_cur, x_opt, x_low, x_top, bha_od, bha_id, ei, bool(valid_flag)

def trajectory_to_coordinates(z: np.ndarray, md_bit: float, traj: np.ndarray) -> tuple:
    """
    Convert a wellbore trajectory to coordinates along the BHA.
    
    Args:
        z: Z-coordinates of the grid points
        md_bit: Measured depth at bit
        traj: Array of trajectory points (MD and inclination)
        
    Returns:
        Tuple containing midline position, inclination at each point, and average inclination
    """
    # Extract trajectory data
    md = np.flip(traj[:, 0])
    inc = np.flip(traj[:, 1])
    
    # Convert MD to z-coordinate (z is negative uphole from bit)
    md = -(md - md_bit)
    
    # Interpolate inclination at each grid point
    inc_grid = np.interp(z, md, inc)
    
    # Calculate average inclination
    inc_avg = np.mean(inc_grid)
    
    # Calculate borehole center position based on trajectory
    # This accounts for the curvature of the wellbore
    step = z[1] - z[0]
    x_mid = step * (np.cumsum(np.cos(inc_grid)) - np.cumsum(np.cos(inc_avg)))
    
    return x_mid, inc_grid, inc_avg

def calculate_sag_from_position(dz: float, x: np.ndarray, dni_to_bit: float) -> float:
    """
    Calculate the sag correction value from the BHA position.
    
    Args:
        dz: Grid spacing in meters
        x: BHA position relative to midline
        dni_to_bit: Distance from D&I sensor to bit in meters
        
    Returns:
        Sag correction value in radians
    """
    import numpy as np
    from math import atan
    
    # Calculate the index of the D&I sensor position
    dni_ind = int(round(dni_to_bit / dz))
    
    # Handle boundary cases
    if dni_ind <= 0:
        dni_ind = 1
    elif dni_ind >= len(x) - 1:
        dni_ind = len(x) - 2
    
    # Calculate sag as the average of the angles at the D&I sensor
    fwd_angle = atan((x[dni_ind + 1] - x[dni_ind]) / dz)
    back_angle = atan((x[dni_ind] - x[dni_ind - 1]) / dz)
    sag = -(fwd_angle + back_angle) / 2
    
    return sag