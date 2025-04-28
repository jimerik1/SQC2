from flask import Blueprint, request, jsonify
from services.qc.accelerometer import perform_get
from services.qc.magnetometer import perform_tfdt
from services.qc.gyroscope import perform_hert

single_station_bp = Blueprint('single_station', __name__)

@single_station_bp.route('/get', methods=['POST'])
def gravity_error_test():
    """Perform Gravity Error Test (GET) on a survey station"""
    data = request.get_json()
    result = perform_get(data['survey'], data['ipm'])
    return jsonify(result)

@single_station_bp.route('/tfdt', methods=['POST'])
def total_field_dip_test():
    """Perform Total Field + Dip Test (TFDT) on a survey station"""
    data = request.get_json()
    result = perform_tfdt(data['survey'], data['ipm'])
    return jsonify(result)

@single_station_bp.route('/hert', methods=['POST'])
def horizontal_earth_rate_test():
    """Perform Horizontal Earth Rate Test (HERT) on a survey station"""
    data = request.get_json()
    result = perform_hert(data['survey'], data['ipm'])
    return jsonify(result)