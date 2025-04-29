# blueprints/toolcode.py
from flask import Blueprint, request, jsonify
from src.utils.ipm_parser import parse_ipm_file

toolcode_bp = Blueprint('toolcode', __name__)

@toolcode_bp.route('/parse-ipm', methods=['POST'])
def parse_ipm():
    """Parse and return the contents of an IPM file"""
    data = request.get_json()
    
    if 'ipm_content' not in data:
        return jsonify({'error': 'IPM content is required'}), 400
    
    try:
        ipm = parse_ipm_file(data['ipm_content'])
        
        # Create a response using the to_dict() method but handle missing attributes
        response = {
            'short_name': getattr(ipm, 'short_name', ""),
            'description': getattr(ipm, 'description', ""),
            'error_terms': ipm.error_terms
        }
        
        return jsonify(response)
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

@toolcode_bp.route('/available-tests', methods=['GET'])
def get_available_tests():
    """Return information about all available QC tests with categorization"""
    tests = [
        {
            'id': 'get',
            'name': 'Gravity Error Test',
            'description': 'Tests accelerometer measurements against theoretical gravity',
            'endpoint': '/api/v1/qc/internal/single-station/get',
            'method': 'POST',
            'test_category': 'Single Station Test',
            'functional_category': 'Georeference QC Test'
        },
        {
            'id': 'tfdt',
            'name': 'Total Field + Dip Test',
            'description': 'Tests magnetometer measurements against theoretical magnetic field',
            'endpoint': '/api/v1/qc/internal/single-station/tfdt',
            'method': 'POST',
            'test_category': 'Single Station Test',
            'functional_category': 'Georeference QC Test'
        },
        {
            'id': 'hert',
            'name': 'Horizontal Earth Rate Test',
            'description': 'Tests gyroscope measurements against theoretical Earth rotation rate',
            'endpoint': '/api/v1/qc/internal/single-station/hert',
            'method': 'POST',
            'test_category': 'Single Station Test',
            'functional_category': 'Georeference QC Test'
        },
        {
            'id': 'rsmt',
            'name': 'Rotation-Shot Misalignment Test',
            'description': 'Tests for misalignment using measurements at different toolfaces',
            'endpoint': '/api/v1/qc/internal/single-station/rsmt',
            'method': 'POST',
            'test_category': 'Repeated Measurements Test',
            'functional_category': 'Repeated Measurements Test'
        },
        {
            'id': 'dddt',
            'name': 'Dual Depth Difference Test',
            'description': 'Tests depth measurements from two independent systems',
            'endpoint': '/api/v1/qc/measurement/dddt',
            'method': 'POST',
            'test_category': 'Single Station Test',
            'functional_category': 'Repeated Measurements Test'
        },
        {
            'id': 'msat',
            'name': 'Multi-Station Accelerometer Test',
            'description': 'Tests accelerometer errors using multiple survey stations',
            'endpoint': '/api/v1/qc/internal/multi-station/msat',
            'method': 'POST',
            'test_category': 'Multi-Station Test',
            'functional_category': 'Multistation Test'
        },
        {
            'id': 'msgt',
            'name': 'Multi-Station Gyro Test',
            'description': 'Tests gyroscope errors using multiple survey stations',
            'endpoint': '/api/v1/qc/internal/multi-station/msgt',
            'method': 'POST',
            'test_category': 'Multi-Station Test',
            'functional_category': 'Multistation Test'
        },
        {
            'id': 'msmt',
            'name': 'Multi-Station Magnetometer Test',
            'description': 'Tests magnetometer errors using multiple survey stations',
            'endpoint': '/api/v1/qc/internal/multi-station/msmt',
            'method': 'POST',
            'test_category': 'Multi-Station Test',
            'functional_category': 'Multistation Test'
        },
        {
            'id': 'mse',
            'name': 'Multi-Station Estimation',
            'description': 'Comprehensive estimation of all systematic errors',
            'endpoint': '/api/v1/qc/internal/multi-station/mse',
            'method': 'POST',
            'test_category': 'Multi-Station Test',
            'functional_category': 'Multistation Test'
        },
        {
            'id': 'iomt',
            'name': 'In-Run/Out-Run Misalignment Test',
            'description': 'Tests for misalignment in continuous surveys',
            'endpoint': '/api/v1/qc/external/iomt',
            'method': 'POST',
            'test_category': 'Comparison Test',
            'functional_category': 'Repeated Measurements Test'
        },
        {
            'id': 'cadt',
            'name': 'Continuous Azimuth Drift Test',
            'description': 'Tests for gyro drift and random walk errors',
            'endpoint': '/api/v1/qc/external/cadt',
            'method': 'POST',
            'test_category': 'Comparison Test',
            'functional_category': 'Repeated Measurements Test'
        },
        {
            'id': 'idt',
            'name': 'Inclination Difference Test',
            'description': 'Tests inclination differences between independent surveys',
            'endpoint': '/api/v1/qc/external/idt',
            'method': 'POST',
            'test_category': 'Comparison Test',
            'functional_category': 'Independent-Survey Test'
        },
        {
            'id': 'adt',
            'name': 'Azimuth Difference Test',
            'description': 'Tests azimuth differences between independent surveys',
            'endpoint': '/api/v1/qc/external/adt',
            'method': 'POST',
            'test_category': 'Comparison Test',
            'functional_category': 'Independent-Survey Test'
        },
        {
            'id': 'codt',
            'name': 'Co-ordinate Difference Test',
            'description': 'Tests coordinate differences between independent surveys',
            'endpoint': '/api/v1/qc/external/codt',
            'method': 'POST',
            'test_category': 'Comparison Test',
            'functional_category': 'Independent-Survey Test'
        }
    ]
    
    return jsonify(tests)
