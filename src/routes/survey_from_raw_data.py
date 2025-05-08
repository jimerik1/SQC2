from flask import Blueprint, request, jsonify
import numpy as np
import math
import traceback

survey_from_raw_data_bp = Blueprint('survey_from_raw_data', __name__)

@survey_from_raw_data_bp.route('/calculate', methods=['POST'])
def calculate_directional_parameters():
    """
    Calculate directional parameters from raw sensor data
    
    Expected input format:
    {
        "Bx": float,  # nT
        "By": float,  # nT
        "Bz": float,  # nT
        "Gx": float,  # m/s²
        "Gy": float,  # m/s²
        "Gz": float   # m/s²
    }
    
    Returns:
        Dictionary with calculated values:
        - inclination (degrees)
        - azimuth (degrees)
        - total_magnetic_field (nT)
        - dip (degrees)
    """
    try:
        data = request.get_json()
        
        # Check required fields
        required_fields = ['Bx', 'By', 'Bz', 'Gx', 'Gy', 'Gz']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Calculate directional parameters
        result = calculate_directional_params(
            data['Gx'], data['Gy'], data['Gz'],
            data['Bx'], data['By'], data['Bz']
        )
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@survey_from_raw_data_bp.route('/calculate-with-toolface', methods=['POST'])
def calculate_with_toolface():
    """
    Calculate all directional parameters including toolface from two consecutive survey points
    
    Expected input format:
    {
        "current": {
            "Bx": float,  # nT
            "By": float,  # nT
            "Bz": float,  # nT
            "Gx": float,  # m/s²
            "Gy": float,  # m/s²
            "Gz": float   # m/s²
        },
        "previous": {
            "Bx": float,  # nT
            "By": float,  # nT
            "Bz": float,  # nT
            "Gx": float,  # m/s²
            "Gy": float,  # m/s²
            "Gz": float   # m/s²
        }
    }
    
    Returns:
        Dictionary with calculated values including toolface
    """
    try:
        data = request.get_json()
        
        # Check required structures
        if 'current' not in data or 'previous' not in data:
            return jsonify({"error": "Both 'current' and 'previous' survey data required"}), 400
        
        # Check required fields for both current and previous
        required_fields = ['Bx', 'By', 'Bz', 'Gx', 'Gy', 'Gz']
        for point in ['current', 'previous']:
            for field in required_fields:
                if field not in data[point]:
                    return jsonify({"error": f"Missing required field: {field} in {point} survey"}), 400
        
        # Calculate directional parameters for both points
        current_params = calculate_directional_params(
            data['current']['Gx'], data['current']['Gy'], data['current']['Gz'],
            data['current']['Bx'], data['current']['By'], data['current']['Bz']
        )
        
        prev_params = calculate_directional_params(
            data['previous']['Gx'], data['previous']['Gy'], data['previous']['Gz'],
            data['previous']['Bx'], data['previous']['By'], data['previous']['Bz']
        )
        
        # Calculate toolface using the provided formula
        toolface = calculate_toolface(
            current_params['inclination'], 
            prev_params['inclination'],
            current_params['azimuth'], 
            prev_params['azimuth']
        )
        
        # Add toolface to results
        result = current_params.copy()
        result['toolface'] = toolface
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@survey_from_raw_data_bp.route('/calculate-batch', methods=['POST'])
def calculate_batch():
    """
    Calculate directional parameters for multiple survey points
    
    Expected input format:
    {
        "surveys": [
            {
                "depth": float,
                "Bx": float,
                "By": float,
                "Bz": float,
                "Gx": float,
                "Gy": float,
                "Gz": float
            },
            ...
        ]
    }
    
    Returns:
        Structured response with results containing index and grouped parameters
    """
    try:
        data = request.get_json()
        
        # Check required structure
        if 'surveys' not in data or not isinstance(data['surveys'], list) or len(data['surveys']) == 0:
            return jsonify({"error": "Expected non-empty 'surveys' array in request"}), 400
        
        # Required fields for each survey
        required_fields = ['depth', 'Bx', 'By', 'Bz', 'Gx', 'Gy', 'Gz']
        
        results = []
        
        # Process each survey
        for i, survey in enumerate(data['surveys']):
            # Check all required fields
            for field in required_fields:
                if field not in survey:
                    return jsonify({"error": f"Missing required field: {field} in survey at index {i}"}), 400
            
            # Calculate directional parameters
            params = calculate_directional_params(
                survey['Gx'], survey['Gy'], survey['Gz'],
                survey['Bx'], survey['By'], survey['Bz']
            )
            
            # Structure the result in a nested format
            result = {
                "index": i,
                "location": {
                    "depth": survey['depth']
                },
                "directional_parameters": {
                    "inclination": params['inclination'],
                    "azimuth": params['azimuth'],
                    "magnetic_field": {
                        "total": params['total_magnetic_field'],
                        "dip": params['dip']
                    },
                    "gravity": {
                        "magnitude": params['gravity_total']
                    }
                }
            }
            
            results.append(result)
        
        # Return the structured response
        return jsonify({"results": results})
    
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc() if app.debug else None
        }), 500
        
def calculate_directional_params(Gx, Gy, Gz, Bx, By, Bz):
    """
    Calculate directional parameters from raw sensor data
    """
    # Convert input values to float
    Gx, Gy, Gz = float(Gx), float(Gy), float(Gz)
    Bx, By, Bz = float(Bx), float(By), float(Bz)
    
    # Calculate magnitudes
    G_total = np.sqrt(Gx**2 + Gy**2 + Gz**2)
    B_total = np.sqrt(Bx**2 + By**2 + Bz**2)
    
    # Calculate inclination (angle from vertical)
    inclination = np.degrees(np.arccos(np.clip(Gz / G_total, -1.0, 1.0)))
    
    # Calculate azimuth using the standard formula
    numerator = (Gx * By - Gy * Bx)
    denominator = (Bz * (Gx**2 + Gy**2) - Gz * (Gx * Bx + Gy * By))
    
    # Handle special cases to avoid division by zero
    if abs(denominator) < 1e-10:
        # For near-vertical wells or special cases
        if inclination < 3.0:
            azimuth = 0.0  # Default for vertical
        else:
            # Alternative calculation for near-singularity
            Hx = Bx - (Gz * Gx / G_total**2) * B_total
            Hy = By - (Gz * Gy / G_total**2) * B_total
            azimuth = np.degrees(np.arctan2(Hy, Hx)) % 360
    else:
        azimuth = np.degrees(np.arctan2(numerator, denominator)) % 360
    
    # Calculate dip angle
    g_norm = np.array([Gx, Gy, Gz]) / G_total
    b_norm = np.array([Bx, By, Bz]) / B_total
    dot_product = np.dot(g_norm, b_norm)
    dip = np.degrees(np.arcsin(np.clip(dot_product, -1.0, 1.0)))
    
    # Return the calculated parameters
    return {
        "inclination": float(inclination),
        "azimuth": float(azimuth),
        "total_magnetic_field": float(B_total),
        "dip": float(dip),
        "gravity_total": float(G_total)
    }

def calculate_toolface(inc2, inc1, azi2, azi1):
    """
    Calculate toolface angle between two survey points using:
    γ = cos⁻¹((sinθ₂ - sinθ₁cosβ)/(cosθ₁sinβ))
    
    Where:
    - inc1, inc2: inclination angles (degrees)
    - azi1, azi2: azimuth angles (degrees)
    - β: dogleg angle (calculated from inc1, inc2, and azimuth change)
    """
    # Convert to radians
    inc1_rad = np.radians(inc1)
    inc2_rad = np.radians(inc2)
    
    # Calculate azimuth change (handle wrap-around)
    delta_azi = (azi2 - azi1) % 360
    if delta_azi > 180:
        delta_azi = delta_azi - 360
    delta_azi_rad = np.radians(delta_azi)
    
    # Calculate dogleg angle (β)
    # β = cos⁻¹(cos Δφ cosθ₂cosθ₁ + sinθ₂sinθ₁)
    cos_dogleg = (np.cos(delta_azi_rad) * np.cos(inc2_rad) * np.cos(inc1_rad) + 
                  np.sin(inc2_rad) * np.sin(inc1_rad))
    
    # Clamp to valid range for arccos
    cos_dogleg = np.clip(cos_dogleg, -1.0, 1.0)
    dogleg_rad = np.arccos(cos_dogleg)
    
    # Handle zero or very small dogleg angles
    if np.abs(dogleg_rad) < 1e-10:
        return 0.0  # Toolface is undefined for zero dogleg
    
    # Calculate toolface
    # γ = cos⁻¹((sinθ₂ - sinθ₁cosβ)/(cosθ₁sinβ))
    numerator = np.sin(inc2_rad) - np.sin(inc1_rad) * np.cos(dogleg_rad)
    denominator = np.cos(inc1_rad) * np.sin(dogleg_rad)
    
    # Handle division by zero
    if np.abs(denominator) < 1e-10:
        return 0.0  # Toolface is undefined in this case
    
    cos_toolface = np.clip(numerator / denominator, -1.0, 1.0)
    toolface = np.degrees(np.arccos(cos_toolface))
    
    # Determine the sign of the toolface
    # If azimuth is decreasing, toolface is negative
    if delta_azi < 0:
        toolface = 360 - toolface
    
    return float(toolface % 360)