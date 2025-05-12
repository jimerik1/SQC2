# blueprints/qc/test_generator.py
from flask import Blueprint, request, jsonify
import numpy as np

test_generator_bp = Blueprint('test_generator', __name__)

@test_generator_bp.route('/msat', methods=['POST'])
def generate_msat_payload():
    """
    Generate a Multi-Station Accelerometer Test (MSAT) payload from trajectory data
    
    Takes the trajectory data directly as input, with optional parameters:
    - apply_corrections: bool (optional, default: false)
    - sigma: float (optional, default: 3.0)
    - custom_ipm: string (optional)
    """
    data = request.get_json()
    
    # Validate required inputs
    if not data:
        return jsonify({'error': 'Trajectory data is required'}), 400
    
    # Extract optional parameters if provided
    apply_corrections = data.get('apply_corrections', False)
    sigma = data.get('sigma', 3.0)
    
    # Set default IPM data if not provided
    default_ipm = (
        "ABXY-TI1S e s m/s2 0.0039 Accelerometer bias X Y\n"
        "ABZ e s m/s2 0.0039 Accelerometer bias Z\n"
        "ASXY-TI1S e s - 0.0005 Accelerometer scale factor X Y\n"
        "ASZ e s - 0.0005 Accelerometer scale factor Z"
    )
    custom_ipm = data.get('custom_ipm', default_ipm)
    
    # Generate MSAT payload from trajectory data
    payload = convert_trajectory_to_msat(data, apply_corrections, sigma, custom_ipm)
    return jsonify(payload)

def convert_trajectory_to_msat(trajectory_data, apply_corrections, sigma, ipm):
    """
    Convert trajectory data to MSAT payload format
    """
    # Extract sensor data from trajectory data
    sensor_data = trajectory_data.get('sensor_data', {})
    parameters = trajectory_data.get('parameters', {})
    
    # Check if all required fields are present
    required_fields = ['Gx', 'Gy', 'Gz', 'Inc', 'tfo']
    for field in required_fields:
        if field not in sensor_data:
            return {'error': f'Missing required field in trajectory data: {field}'}
    
    # Extract expected gravity value from parameters or use default 9.81
    expected_gravity = parameters.get('gravity', 9.81)
    
    # Build surveys array
    surveys = []
    num_points = len(sensor_data['Gx'])
    
    for i in range(num_points):
        survey = {
            "accelerometer_x": sensor_data['Gx'][i],
            "accelerometer_y": sensor_data['Gy'][i],
            "accelerometer_z": sensor_data['Gz'][i],
            "inclination": sensor_data['Inc'][i],
            "toolface": sensor_data['tfo'][i],
            "expected_gravity": expected_gravity
        }
        surveys.append(survey)
    
    # Build complete payload
    payload = {
        "surveys": surveys,
        "apply_corrections": apply_corrections,
        "sigma": sigma,
        "ipm": ipm
    }
    
    return payload

# You can add more routes for other test types here
# @test_generator_bp.route('/msgt', methods=['POST'])
# def generate_msgt_payload():
#     # Similar implementation for MSGT
#     pass
#
# @test_generator_bp.route('/msmt', methods=['POST'])
# def generate_msmt_payload():
#     # Similar implementation for MSMT
#     pass