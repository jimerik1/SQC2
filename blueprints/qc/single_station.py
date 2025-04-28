from flask import Blueprint, request, jsonify
from services.qc.get import perform_get
from services.qc.tfdt import perform_tfdt
from services.qc.hert import perform_hert
from services.qc.rsmt import perform_rsmt
from measurement.qc.dddt import perform_dddt


single_station_bp = Blueprint('single_station', __name__)
measurement_bp = Blueprint('measurement', __name__)

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

@single_station_bp.route('/rsmt', methods=['POST'])
def rotation_shot_misalignment_test():
    """Perform Rotation-Shot Misalignment Test (RSMT) on a set of survey measurements"""
    data = request.get_json()
    result = perform_rsmt(data['surveys'], data['ipm'])
    return jsonify(result)

@measurement_bp.route('/dddt', methods=['POST'])
def dual_depth_difference_test():
    """Perform Dual Depth Difference Test (DDDT) on pipe and wireline depth measurements"""
    data = request.get_json()
    result = perform_dddt(data['pipe_depth'], data['wireline_depth'], data['survey'], data['ipm'])
    return jsonify(result)
