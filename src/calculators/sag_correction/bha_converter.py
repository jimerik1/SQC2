# src/calculators/sag_correction/bha_converter.py
from math import sqrt, pi
import numpy as np
from typing import Dict, Tuple

from src.calculators.sag_correction.models import BHA, Material

def bha_to_calculation_inputs(
    bha: BHA, 
    dz: float, 
    physical_constants: Dict[str, float],
    dni_uphole_length: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    """
    Convert a BHA object into arrays of physical properties needed for calculations.
    
    Args:
        bha: The Bottom Hole Assembly object
        dz: The discretization step size in meters
        physical_constants: Dictionary with physical constants
        dni_uphole_length: Maximum uphole length to model from D&I sensor (m)
    
    Returns:
        Tuple containing:
            - ei: Array of bending stiffness (EI) values
            - outer_diameter: Array of outer diameters
            - inner_diameter: Array of inner diameters
            - linear_weight: Array of weights per meter (buoyancy-adjusted)
            - bend_ind: Index of the bend location in the arrays
    """
    # Extract physical constants
    RO_STEEL = physical_constants['ro_steel']
    E_STEEL = physical_constants['e_steel']
    E_NMAG = physical_constants['e_nmag']
    
    # Calculate cumulative length for each element
    cum_length = []
    length = 0.0
    for element in bha.structure:
        length += element.length
        cum_length.append(length)
    
    # Process stabilizer information
    blade_pos = []  # Position index of each stabilizer
    blade_length = []  # Length of each stabilizer in grid units
    blade_od = []  # Outer diameter of each stabilizer
    
    for stab in bha.stabilizers:
        # Convert length to grid units (at least 1)
        grid_length = max(1, round(stab.length / dz))
        blade_length.append(grid_length)
        
        # Calculate position in grid units
        pos_index = round(stab.distance_to_bit / dz)
        blade_pos.append(pos_index)
        
        # Store diameter
        blade_od.append(stab.blade_od)
    
    # Initialize arrays for physical properties
    young_modulus = []
    apparent_inner_diameter = []
    linear_weight = []
    outer_diameter = []
    inner_diameter = []
    
    # Convert BHA elements to discretized arrays
    model_length = dz / 2
    num_elements = len(bha.structure)
    element_index = 0
    
    while element_index < num_elements:
        # Get current element
        element = bha.structure[element_index]
        
        # Set Young's modulus based on material
        is_non_magnetic = element.material == Material.NON_MAGNETIC
        young_modulus.append(E_NMAG if is_non_magnetic else E_STEEL)
        
        # Get outer diameter
        OD = element.od
        
        # Calculate weight per meter
        if element.weight <= 0:
            raise ValueError(f"BHA element '{element.description}' has zero or negative weight. Check your input data.")
        Q = element.weight / element.length
        
        # Calculate effective inner diameter from weight and density
        # This accounts for connection weights, etc.
        ID_squared = OD**2 - 4 * Q / (pi * RO_STEEL)
        ID = sqrt(ID_squared) if ID_squared > 0 else 0
        
        # Store values in arrays
        outer_diameter.append(OD)
        linear_weight.append(Q)
        apparent_inner_diameter.append(ID)
        inner_diameter.append(element.id)
        
        # Move to next grid point
        model_length += dz
        
        # Move to next element if we've covered its length
        if model_length >= cum_length[element_index]:
            element_index += 1
        
        # Stop after modeling enough length past the D&I sensor
        if model_length > bha.dni_to_bit + dni_uphole_length + dz:
            break
    
    # Convert lists to numpy arrays
    young_modulus = np.array(young_modulus)
    outer_diameter = np.array(outer_diameter)
    linear_weight = np.array(linear_weight)
    apparent_inner_diameter = np.array(apparent_inner_diameter)
    inner_diameter = np.array(inner_diameter)
    
    # Calculate moment of inertia (I) for each element
    # I = π/64 * (OD⁴ - ID⁴)
    inertia_momentum = pi * (outer_diameter**4 - apparent_inner_diameter**4) / 64
    
    # Add stabilizers' effect on moment of inertia
    num_stab = len(bha.stabilizers)
    for i in range(num_stab):
        # Calculate start and end indices for this stabilizer
        start = blade_pos[i]
        stop = blade_pos[i] + int(blade_length[i])
        
        # Skip if stabilizer is outside modeled range
        if start >= len(outer_diameter):
            continue
        
        stop = min(stop, len(outer_diameter))
        
        # Add stabilizer effect to moment of inertia
        # This approximates the additional stiffness provided by the stabilizer blades
        if start < len(outer_diameter):
            blade_contribution = (
                blade_od[i]**3 * outer_diameter[start] / 36 +
                blade_od[i] * outer_diameter[start]**3 / 324
            )
            inertia_momentum[start:stop] += blade_contribution
            
            # Update outer diameter for visualization
            outer_diameter[start:stop] = blade_od[i]
    
    # Calculate bending stiffness (EI)
    ei = young_modulus * inertia_momentum
    
    # Calculate bend position index
    if round(bha.bend_to_bit / dz) <= 0:
        bend_ind = -10  # Default value if bend is at or below bit
    else:
        bend_ind = round(bha.bend_to_bit / dz)
    
    return ei, outer_diameter, inner_diameter, linear_weight, bend_ind