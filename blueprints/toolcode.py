# blueprints/toolcode.py
from flask import Blueprint, request, jsonify
from utils.ipm_parser import parse_ipm_file
from services.toolcode.tolerance import get_error_term_value, calculate_get_tolerance

toolcode_bp = Blueprint('toolcode', __name__)

@toolcode_bp.route('/parse-ipm', methods=['POST'])
def parse_ipm():
    """Parse and return the contents of an IPM file"""
    data = request.get_json()
    
    if 'ipm_content' not in data:
        return jsonify({'error': 'IPM content is required'}), 400
    
    try:
        ipm = parse_ipm_file(data['ipm_content'])
        
        return jsonify({
            'short_name': ipm.short_name,
            'description': ipm.description,
            'error_terms': ipm.error_terms
        })
    except Exception as e:
        return jsonify({'error': f'Failed to parse IPM file: {str(e)}'}), 400

@toolcode_bp.route('/error-term', methods=['POST'])
def get_error_term():
    """Get a specific error term from an IPM file"""
    data = request.get_json()
    
    if 'ipm_content' not in data:
        return jsonify({'error': 'IPM content is required'}), 400
    if 'name' not in data:
        return jsonify({'error': 'Error term name is required'}), 400
    
    vector = data.get('vector', '')
    tie_on = data.get('tie_on', '')
    
    try:
        ipm = parse_ipm_file(data['ipm_content'])
        error_term = ipm.get_error_term(data['name'], vector, tie_on)
        
        if error_term:
            return jsonify(error_term)
        else:
            return jsonify({'error': 'Error term not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Failed to get error term: {str(e)}'}), 400

@toolcode_bp.route('/calculate-get-tolerance', methods=['POST'])
def calc_get_tolerance():
    """Calculate tolerance for Gravity Error Test based on IPM"""
    data = request.get_json()
    
    if 'ipm_content' not in data:
        return jsonify({'error': 'IPM content is required'}), 400
    if 'inclination' not in data:
        return jsonify({'error': 'Inclination is required'}), 400
    if 'toolface' not in data:
        return jsonify({'error': 'Toolface is required'}), 400
    
    try:
        ipm = parse_ipm_file(data['ipm_content'])
        tolerance = calculate_get_tolerance(ipm, data['inclination'], data['toolface'])
        
        return jsonify({
            'tolerance': tolerance,
            'inclination': data['inclination'],
            'toolface': data['toolface']
        })
    except Exception as e:
        return jsonify({'error': f'Failed to calculate tolerance: {str(e)}'}), 400

@toolcode_bp.route('/supported-tests', methods=['GET'])
def get_supported_tests():
    """Return information about supported QC tests"""
    tests = [
        {
            'id': 'get',
            'name': 'Gravity Error Test',
            'description': 'Tests accelerometer measurements against theoretical gravity',
            'endpoint': '/api/v1/qc/single-station/get',
            'method': 'POST'
        },
        {
            'id': 'tfdt',
            'name': 'Total Field + Dip Test',
            'description': 'Tests magnetometer measurements against theoretical magnetic field',
            'endpoint': '/api/v1/qc/single-station/tfdt',
            'method': 'POST'
        },
        {
            'id': 'hert',
            'name': 'Horizontal Earth Rate Test',
            'description': 'Tests gyroscope measurements against theoretical Earth rotation rate',
            'endpoint': '/api/v1/qc/single-station/hert',
            'method': 'POST'
        },
        {
            'id': 'rsmt',
            'name': 'Rotation-Shot Misalignment Test',
            'description': 'Tests for misalignment using measurements at different toolfaces',
            'endpoint': '/api/v1/qc/single-station/rsmt',
            'method': 'POST'
        },
        {
            'id': 'dddt',
            'name': 'Dual Depth Difference Test',
            'description': 'Tests depth measurements from two independent systems',
            'endpoint': '/api/v1/qc/measurement/dddt',
            'method': 'POST'
        },
        {
            'id': 'msat',
            'name': 'Multi-Station Accelerometer Test',
            'description': 'Tests accelerometer errors using multiple survey stations',
            'endpoint': '/api/v1/qc/multi-station/msat',
            'method': 'POST'
        },
        {
            'id': 'msgt',
            'name': 'Multi-Station Gyro Test',
            'description': 'Tests gyroscope errors using multiple survey stations',
            'endpoint': '/api/v1/qc/multi-station/msgt',
            'method': 'POST'
        },
        {
            'id': 'msmt',
            'name': 'Multi-Station Magnetometer Test',
            'description': 'Tests magnetometer errors using multiple survey stations',
            'endpoint': '/api/v1/qc/multi-station/msmt',
            'method': 'POST'
        }
    ]
    
    return jsonify(tests)