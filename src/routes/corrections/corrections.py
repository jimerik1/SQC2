# src/routes/corrections/corrections.py
from flask import Blueprint, request, jsonify
from src.calculators.sag_correction.calculator import calculate_sag_correction

corrections_bp = Blueprint('corrections', __name__)

@corrections_bp.route('/sag', methods=['POST'])
def sag_correction():
    """
    Perform BHA sag correction calculation
    
    Expected input format:
    {
        "trajectory": [
            {
                "md": float,     # measured depth (meters)
                "inc": float,    # inclination (degrees)
                "azi": float     # azimuth (degrees, optional)
            },
            ...
        ],
        "bha": {
            "structure": [
                {
                    "description": string,
                    "od": float,            # outer diameter (meters)
                    "id": float,            # inner diameter (meters)
                    "max_od": float,        # maximum outer diameter (meters)
                    "length": float,        # length (meters)
                    "weight": float,        # weight (metric tons)
                    "material": string      # "STEEL" or "NON_MAGNETIC"
                },
                ...
            ],
            "stabilizers": [
                {
                    "blade_od": float,         # blade outer diameter (meters)
                    "distance_to_bit": float,  # distance from midpoint to bit (meters)
                    "length": float            # length (meters)
                },
                ...
            ]
        },
        "sensor_position": float,     # distance from D&I sensor to bit (meters)
        "mud_weight": float,          # mud weight (g/ml)
        "dni_uphole_length": float,   # uphole length to model from D&I sensor (meters)
        "physical_constants": {       # optional, defaults will be used if not provided
            "ro_steel": float,        # density of steel (kg/m³)
            "e_steel": float,         # Young's modulus for construction steel (Pa)
            "e_nmag": float           # Young's modulus for non-magnetic steel (Pa)
        },
        "toolface": float             # toolface angle (degrees, optional, defaults to 0)
    }
    
    Returns:
    {
        "survey_results": [
            {
                "md": float,             # measured depth (meters)
                "original_inc": float,   # original inclination (degrees)
                "sag": float,            # sag correction (degrees)
                "corrected_inc": float,  # corrected inclination (degrees)
                "valid": boolean         # validity flag
            },
            ...
        ],
        "grid_data": [
            {
                "z_from_bit_m": float,   # distance from bit (meters)
                "deflection_m": float,   # lateral deflection (meters)
                "slope_deg": float,      # slope (degrees)
                "moment_Nm": float,      # moment (Newton-meters)
                "shear_N": float         # shear force (Newtons)
            },
            ...
        ],
        "sensor_position": float,        # distance from D&I sensor to bit (meters)
        "dni_uphole_length": float       # uphole length modeled from D&I sensor (meters)
    }
    """
    data = request.get_json()
    
    # Validate required inputs
    required_fields = ['trajectory', 'bha', 'sensor_position', 'mud_weight']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Extract inputs with defaults
    trajectory = data['trajectory']
    bha = data['bha']
    sensor_position = data['sensor_position']
    mud_weight = data['mud_weight']
    dni_uphole_length = data.get('dni_uphole_length', 25.0)  # Default value
    toolface = data.get('toolface', 0.0)  # Default value
    
    # Extract physical constants with defaults
    constants = data.get('physical_constants', {})
    ro_steel = constants.get('ro_steel', 7850.0)
    e_steel = constants.get('e_steel', 2.05e11)
    e_nmag = constants.get('e_nmag', 1.90e11)

    # Perform the calculation
    result = calculate_sag_correction(
        trajectory=trajectory,
        bha=bha,
        sensor_position=sensor_position,
        mud_weight=mud_weight,
        dni_uphole_length=dni_uphole_length,
        physical_constants={
            'ro_steel': ro_steel,
            'e_steel': e_steel,
            'e_nmag': e_nmag
        },
        toolface=toolface
    )
    
    return jsonify(result)