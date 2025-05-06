from flask import Blueprint, request, jsonify
from src.calculators.survey_qc_tests.get import perform_get
from src.calculators.survey_qc_tests.tfdt import perform_tfdt
from src.calculators.survey_qc_tests.hert import perform_hert
from src.calculators.survey_qc_tests.rsmt import perform_rsmt
from src.calculators.survey_qc_tests.dddt import perform_dddt  

single_station_bp = Blueprint('single_station', __name__)
measurement_bp = Blueprint('measurement', __name__)

@single_station_bp.route('/get', methods=['POST'])
def gravity_error_test():
    """
    Perform Gravity Error Test (GET) on a survey station
    
    Expected input format:
    {
        "survey": {
            "accelerometer_x": float,  # g units
            "accelerometer_y": float,  # g units
            "accelerometer_z": float,  # g units
            "inclination": float,      # degrees (optional)
            "toolface": float,         # degrees (optional)
            "depth": float,            # meters
            "expected_gravity": float, # g units (from EGM2008 API)
            "azimuth": float           # degrees (optional, for enhanced warnings)
            "sigma": float             # dimensionless (optional, for adjusted thresholds)
        },
        "ipm": string or object        # IPM file content or parsed object
    }
    """
    data = request.get_json()
    
    # Validate required inputs
    required_fields = ['accelerometer_x', 'accelerometer_y', 'accelerometer_z', 
                      'depth', 'expected_gravity']
    
    for field in required_fields:
        if field not in data['survey']:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    theory_g = data['survey']['expected_gravity']
    
    # Extract sigma value with default of 3.0 if not specified
    sigma = data['survey'].get('sigma', 3.0)

    result = perform_get(data['survey'], data['ipm'], theory_g, sigma)
    return jsonify(result)

@single_station_bp.route('/tfdt', methods=['POST'])
def total_field_dip_test():
    """
    Perform Total Field + Dip Test (TFDT) on a survey station
    
    Expected input format:
    {
        "survey": {
            "mag_x": float,            # nT
            "mag_y": float,            # nT
            "mag_z": float,            # nT
            "accelerometer_x": float,  # g units
            "accelerometer_y": float,  # g units
            "accelerometer_z": float,  # g units
            "latitude": float,         # degrees (optional, used for warnings only)
            "sigma": float,            # dimensionless (optional, for adjusted thresholds)
            "expected_geomagnetic_field": {
                "total_field": float,   # nT
                "dip": float,           # degrees
                "declination": float    # degrees
            }
        },
        "ipm": string or object        # IPM file content or parsed object
    }
    """
    data = request.get_json()
    
    # Validate required inputs
    required_fields = ['mag_x', 'mag_y', 'mag_z', 'accelerometer_x', 'accelerometer_y', 
                      'accelerometer_z', 'expected_geomagnetic_field']
    
    for field in required_fields:
        if field not in data['survey']:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Validate geomagnetic field data
    geo_fields = ['total_field', 'dip', 'declination']
    for field in geo_fields:
        if field not in data['survey']['expected_geomagnetic_field']:
            return jsonify({'error': f'Missing required field in expected_geomagnetic_field: {field}'}), 400
    
    # Add default latitude if not provided
    if 'latitude' not in data['survey']:
        data['survey']['latitude'] = 0.0  # Default value, no high-latitude warnings will be triggered
    
    # Extract sigma value with default of 3.0 if not specified
    sigma = data['survey'].get('sigma', 3.0)
    
    # Pass sigma to perform_tfdt
    result = perform_tfdt(data['survey'], data['ipm'], sigma)
    return jsonify(result)

@single_station_bp.route('/hert', methods=['POST'])
def horizontal_earth_rate_test():
    """
    Perform Horizontal Earth Rate Test (HERT) on a survey station
    
    Expected input format:
    {
        "survey": {
            "gyro_x": float,           # deg/hr
            "gyro_y": float,           # deg/hr
            "inclination": float,      # degrees
            "azimuth": float,          # degrees
            "toolface": float,         # degrees
            "latitude": float,         # degrees
            "expected_horizontal_rate": float  # deg/hr
        },
        "ipm": string or object        # IPM file content or parsed object
    }
    """
    data = request.get_json()
    
    # Validate required inputs
    required_fields = ['gyro_x', 'gyro_y', 'inclination', 'azimuth', 
                      'toolface', 'latitude', 'expected_horizontal_rate']
    
    for field in required_fields:
        if field not in data['survey']:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    result = perform_hert(data['survey'], data['ipm'])
    return jsonify(result)

@single_station_bp.route('/rsmt', methods=['POST'])
def rotation_shot_misalignment_test():
    """
    Perform Rotation-Shot Misalignment Test (RSMT) on a set of survey measurements
    
    Expected input format:
    {
        "surveys": [
            {
                "inclination": float,  # degrees
                "toolface": float      # degrees
            },
            ...
        ],
        "ipm": string or object        # IPM file content or parsed object
    }
    """
    data = request.get_json()
    
    # Validate required inputs
    if not data.get('surveys') or not isinstance(data['surveys'], list) or len(data['surveys']) < 3:
        return jsonify({'error': 'At least 3 survey measurements required for RSMT'}), 400
    
    # Check each survey has required fields
    for i, survey in enumerate(data['surveys']):
        if 'inclination' not in survey or 'toolface' not in survey:
            return jsonify({'error': f'Survey at index {i} missing required field: inclination or toolface'}), 400
    
    result = perform_rsmt(data['surveys'], data['ipm'])
    return jsonify(result)

@measurement_bp.route('/dddt', methods=['POST'])
def dual_depth_difference_test():
    """
    Perform Dual Depth Difference Test (DDDT) on pipe and wireline depth measurements
    
    Expected input format:
    {
        "pipe_depth": float,           # meters
        "wireline_depth": float,       # meters
        "survey": {
            "inclination": float,      # degrees
            "azimuth": float,          # degrees
            "true_vertical_depth": float  # meters (optional, will be calculated if not provided)
        },
        "ipm": string or object        # IPM file content or parsed object
    }
    """
    data = request.get_json()
    
    # Validate required inputs
    if 'pipe_depth' not in data or 'wireline_depth' not in data:
        return jsonify({'error': 'Missing required fields: pipe_depth or wireline_depth'}), 400
    
    if 'survey' not in data or 'inclination' not in data['survey']:
        return jsonify({'error': 'Missing required field: survey with inclination data'}), 400
    
    result = perform_dddt(data['pipe_depth'], data['wireline_depth'], data['survey'], data['ipm'])
    return jsonify(result)