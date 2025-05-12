# src/routes/survey_conversions/survey_from_raw_gyro.py
from flask import Blueprint, request, jsonify
import math
import numpy as np
import traceback

# Create the blueprint with the name expected by your app
survey_from_raw_gyro_bp = Blueprint('survey_from_raw_gyro', __name__)

# Earth's rotation rate in degrees per hour
EARTH_ROTATION_RATE = 15.041067  # deg/hr (sidereal)

@survey_from_raw_gyro_bp.route('/calculate', methods=['POST'])
def calculate_from_gyro():
    """
    Calculate directional parameters from gyro and accelerometer readings
    
    Expected input format:
    {
        "gyro_x": float,           # deg/hr
        "gyro_y": float,           # deg/hr
        "gyro_z": float,           # deg/hr (optional for xyz gyro systems)
        "accelerometer_x": float,  # m/s²
        "accelerometer_y": float,  # m/s²
        "accelerometer_z": float,  # m/s²
        "latitude": float,         # degrees
        "gyro_type": string        # "xy" or "xyz" (default: "xy")
    }
    """
    try:
        data = request.get_json()
        
        # Determine gyro type
        gyro_type = data.get('gyro_type', 'xy').lower()
        
        # Validate required inputs (common fields)
        required_fields = ['gyro_x', 'gyro_y', 'accelerometer_x', 'accelerometer_y', 'accelerometer_z', 'latitude']
        
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
                    
        # Get parameters from request
        gyro_x = float(data['gyro_x'])  # deg/hr
        gyro_y = float(data['gyro_y'])  # deg/hr
        acc_x = float(data['accelerometer_x'])  # m/s²
        acc_y = float(data['accelerometer_y'])  # m/s²
        acc_z = float(data['accelerometer_z'])  # m/s²
        latitude = float(data['latitude'])  # degrees
        
        if not -90 <= latitude <= 90:
            return jsonify({'error': 'Latitude must be between -90 and 90 degrees'}), 400

        # Calculate directional parameters based on gyro type
        # Use xyz calculation only if gyro_type is xyz AND gyro_z is provided
        if gyro_type == 'xyz' and 'gyro_z' in data:
            gyro_z = float(data['gyro_z'])  # deg/hr
            result = calculate_xyz_gyro_params(gyro_x, gyro_y, gyro_z, acc_x, acc_y, acc_z, latitude)
        else:
            # Default to xy calculation if:
            # 1. gyro_type is xy, OR
            # 2. gyro_type is xyz but gyro_z is missing
            if gyro_type == 'xyz' and 'gyro_z' not in data:
                # Add a note in the response
                result = calculate_xy_gyro_params(gyro_x, gyro_y, acc_x, acc_y, acc_z, latitude)
                result['note'] = "Requested xyz gyro calculation but missing gyro_z value. Defaulted to xy calculation."
            else:
                result = calculate_xy_gyro_params(gyro_x, gyro_y, acc_x, acc_y, acc_z, latitude)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

def calculate_xy_gyro_params(gyro_x, gyro_y, acc_x, acc_y, acc_z, latitude):
    """
    Calculate directional parameters from xy gyro and accelerometer readings
    using the standard formulas:
    - Inclination (I) = arctan[√(Ax² + Ay²) / Az]
    - Toolface (TF) = arctan[-Ax / -Ay]
    - Azimuth (A) = arctan[(Gx cos TF - Gy sin TF)cos I / (Gx sin TF + Gy cos TF + Ωv sin I)]
    
    Args:
        gyro_x, gyro_y: Gyro readings in deg/hr
        acc_x, acc_y, acc_z: Accelerometer readings in m/s²
        latitude: Local latitude in degrees
    
    Returns:
        dict: Containing calculated inclination and azimuth
    """
    # Calculate gravity magnitude
    g_total = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
    
    # Calculate inclination from accelerometer readings
    # Using formula: I = arctan[√(Ax² + Ay²) / Az]
    # Mathematically equivalent to: I = arccos(Az / g_total)
    inclination = math.degrees(math.acos(min(max(acc_z / g_total, -1.0), 1.0)))
    
    # Calculate toolface from accelerometer readings (if inclination is sufficient)
    # Using formula: TF = arctan[-Ax / -Ay] = arctan[Ax / Ay]
    if inclination >= 3.0 and inclination <= 177.0:  # Not too close to vertical
        toolface = math.degrees(math.atan2(acc_y, acc_x))
        # Convert to 0-360 range
        toolface = (toolface + 360) % 360
    else:
        # Toolface is undefined in near-vertical wells
        toolface = 0.0  # Default value
    
    # Calculate Earth rotation components
    earth_rotation_horizontal = EARTH_ROTATION_RATE * math.cos(math.radians(latitude))
    earth_rotation_vertical = EARTH_ROTATION_RATE * math.sin(math.radians(latitude))
    
    # Calculate azimuth for xy gyro
    # Using formula: A = arctan[(Gx cos TF - Gy sin TF)cos I / (Gx sin TF + Gy cos TF + Ωv sin I)]
    azimuth = 0.0
    
    if inclination > 3.0 and inclination < 177.0:  # Avoid singularity near vertical
        inc_rad = math.radians(inclination)
        tf_rad = math.radians(toolface)
        sin_inc = math.sin(inc_rad)
        cos_inc = math.cos(inc_rad)
        sin_tf = math.sin(tf_rad)
        cos_tf = math.cos(tf_rad)
        
        # Formula from documentation (Image 3)
        numerator = (gyro_x * cos_tf - gyro_y * sin_tf) * cos_inc
        denominator = gyro_x * sin_tf + gyro_y * cos_tf + earth_rotation_vertical * sin_inc
        
        if abs(denominator) < 1e-10:  # Avoid division by zero
            azimuth = 90.0 if numerator > 0 else 270.0
        else:
            azimuth = math.degrees(math.atan2(numerator, denominator)) % 360.0
    
    # Return calculated parameters
    return {
        "inclination": float(inclination),
        "azimuth": float(azimuth),
        "toolface": float(toolface),
        "horizontal_rate": float(earth_rotation_horizontal),
        "vertical_rate": float(earth_rotation_vertical),
        "gravity_total": float(g_total)
    }

def calculate_xyz_gyro_params(gyro_x, gyro_y, gyro_z, acc_x, acc_y, acc_z, latitude):
    """
    Calculate directional parameters from xyz gyro and accelerometer readings
    
    Args:
        gyro_x, gyro_y, gyro_z: Gyro readings in deg/hr
        acc_x, acc_y, acc_z: Accelerometer readings in m/s²
        latitude: Local latitude in degrees
    
    Returns:
        dict: Containing calculated inclination, azimuth and toolface
    """
    # Calculate gravity magnitude
    g_total = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
    
    # Calculate Earth rotation vector components
    lat_rad = math.radians(latitude)
    earth_rotation_horizontal = EARTH_ROTATION_RATE * math.cos(lat_rad)
    earth_rotation_vertical = EARTH_ROTATION_RATE * math.sin(lat_rad)
    
    # Calculate total Earth rotation magnitude
    earth_rotation_total = EARTH_ROTATION_RATE  # Always constant
    
    # Calculate gyro total
    gyro_total = math.sqrt(gyro_x**2 + gyro_y**2 + gyro_z**2)
    
    # Calculate inclination from accelerometer readings
    # Using formula: I = arctan[√(Ax² + Ay²) / Az]
    inclination = math.degrees(math.acos(min(max(acc_z / g_total, -1.0), 1.0)))
    
    # Calculate toolface from accelerometer readings
    if inclination >= 3.0 and inclination <= 177.0:  # Not too close to vertical
        toolface = math.degrees(math.atan2(acc_y, acc_x))
        # Convert to 0-360 range
        toolface = (toolface + 360) % 360
    else:
        # Toolface is undefined in near-vertical wells
        toolface = 0.0  # Default value
    
    # Calculate azimuth using the full Earth rotation vector and xyz gyros
    azimuth = 0.0
    
    if inclination > 3.0 and inclination < 177.0:  # Avoid singularity near vertical
        inc_rad = math.radians(inclination)
        tf_rad = math.radians(toolface)
        sin_inc = math.sin(inc_rad)
        cos_inc = math.cos(inc_rad)
        sin_tf = math.sin(tf_rad)
        cos_tf = math.cos(tf_rad)
        
        # With xyz gyros, we have more complete information about rotation
        # Transform gyro readings from tool to Earth reference frame
        gyro_h_x = gyro_x * cos_tf + gyro_y * sin_tf  # Horizontal component in east direction
        gyro_h_y = -gyro_x * sin_tf + gyro_y * cos_tf  # Horizontal component in north direction
        gyro_v = gyro_z * cos_inc - (gyro_x * cos_tf + gyro_y * sin_tf) * sin_inc  # Vertical component
        
        # Using formula similar to xy gyros but enhanced with z-axis information
        numerator = (gyro_x * cos_tf - gyro_y * sin_tf) * cos_inc
        denominator = gyro_x * sin_tf + gyro_y * cos_tf + earth_rotation_vertical * sin_inc - gyro_z * cos_inc
        
        if abs(denominator) < 1e-10:  # Avoid division by zero
            azimuth = 90.0 if numerator > 0 else 270.0
        else:
            azimuth = math.degrees(math.atan2(numerator, denominator)) % 360.0
    
    # Return calculated parameters with additional data for xyz gyros
    return {
        "inclination": float(inclination),
        "azimuth": float(azimuth),
        "toolface": float(toolface),
        "gyro_total": float(gyro_total),
        "earth_rotation_horizontal": float(earth_rotation_horizontal),
        "earth_rotation_vertical": float(earth_rotation_vertical),
        "earth_rotation_total": float(earth_rotation_total),
        "gravity_total": float(g_total),
        "dip": float(math.degrees(math.atan2(gyro_z, math.sqrt(gyro_x**2 + gyro_y**2))))
    }