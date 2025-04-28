# blueprints/qc/multi_station.py
from flask import Blueprint, request, jsonify
from services.qc.msat import perform_msat
from services.qc.msgt import perform_msgt
from services.qc.msmt import perform_msmt
from services.qc.mse import perform_mse

multi_station_bp = Blueprint('multi_station', __name__)

@multi_station_bp.route('/msat', methods=['POST'])
def multi_station_accelerometer_test():
    """Perform Multi-Station Accelerometer Test (MSAT) on a set of survey measurements"""
    data = request.get_json()
    result = perform_msat(data['surveys'], data['ipm'])
    return jsonify(result)

@multi_station_bp.route('/msgt', methods=['POST'])
def multi_station_gyro_test():
    """Perform Multi-Station Gyro Test (MSGT) on a set of survey measurements"""
    data = request.get_json()
    result = perform_msgt(data['surveys'], data['ipm'])
    return jsonify(result)

@multi_station_bp.route('/msmt', methods=['POST'])
def multi_station_magnetometer_test():
    """Perform Multi-Station Magnetometer Test (MSMT) on a set of survey measurements"""
    data = request.get_json()
    result = perform_msmt(data['surveys'], data['ipm'])
    return jsonify(result)

@multi_station_bp.route('/mse', methods=['POST'])
def multi_station_estimation():
    """Perform Multi-Station Estimation (MSE) on a set of survey measurements"""
    data = request.get_json()
    
    if 'surveys' not in data or not data['surveys']:
        return jsonify({'error': 'Survey data is required'}), 400
    
    if 'ipm' not in data:
        return jsonify({'error': 'IPM data is required'}), 400
    
    result = perform_mse(data['surveys'], data['ipm'])
    return jsonify(result)
