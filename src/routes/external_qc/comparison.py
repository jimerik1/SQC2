# src/routes/external_qc/comparison.py
from flask import Blueprint, request, jsonify
from src.calculators.comparison_tests.iomt import perform_iomt
from src.calculators.comparison_tests.cadt import perform_cadt
from src.calculators.comparison_tests.idt import perform_idt
from src.calculators.comparison_tests.adt import perform_adt
from src.calculators.comparison_tests.codt import perform_codt

external_qc_bp = Blueprint('external_qc', __name__)

@external_qc_bp.route('/iomt', methods=['POST'])
def in_out_misalignment_test():
    """
    Perform In-run/Out-run Misalignment Test (IOMT)
    
    Expected input format:
    {
        "in_run": [
            {
                "depth": float,
                "inclination": float,
                "toolface": float  # gyro toolface near vertical
            },
            ...
        ],
        "out_run": [
            {
                "depth": float,
                "inclination": float,
                "toolface": float  # gyro toolface near vertical
            },
            ...
        ],
        "ipm": string or object  # IPM file content or parsed object
    }
    """
    data = request.get_json()
    
    if 'in_run' not in data or 'out_run' not in data:
        return jsonify({'error': 'Both in_run and out_run data are required'}), 400
    
    if 'ipm' not in data:
        return jsonify({'error': 'IPM data is required'}), 400
    
    result = perform_iomt(data['in_run'], data['out_run'], data['ipm'])
    return jsonify(result)

@external_qc_bp.route('/cadt', methods=['POST'])
def continuous_azimuth_drift_test():
    """
    Perform Continuous Azimuth Drift Test (CADT)
    
    Expected input format:
    {
        "in_run": [
            {
                "depth": float,
                "azimuth": float
            },
            ...
        ],
        "out_run": [
            {
                "depth": float,
                "azimuth": float
            },
            ...
        ],
        "average_running_speed": float,  # meters/hour
        "ipm": string or object  # IPM file content or parsed object
    }
    """
    data = request.get_json()
    
    if 'in_run' not in data or 'out_run' not in data:
        return jsonify({'error': 'Both in_run and out_run data are required'}), 400
    
    if 'average_running_speed' not in data:
        return jsonify({'error': 'Average running speed is required'}), 400
    
    if 'ipm' not in data:
        return jsonify({'error': 'IPM data is required'}), 400
    
    result = perform_cadt(data['in_run'], data['out_run'], data['average_running_speed'], data['ipm'])
    return jsonify(result)

@external_qc_bp.route('/idt', methods=['POST'])
def inclination_difference_test():
    """
    Perform Inclination Difference Test (IDT)
    
    Expected input format:
    {
        "survey1": [
            {
                "depth": float,
                "inclination": float,
                "error_model": {
                    "inclination_std": float  # standard deviation in degrees
                }
            },
            ...
        ],
        "survey2": [
            {
                "depth": float,
                "inclination": float,
                "error_model": {
                    "inclination_std": float  # standard deviation in degrees
                }
            },
            ...
        ],
        "max_stations": integer  # Optional, default is 15
    }
    """
    data = request.get_json()
    
    if 'survey1' not in data or 'survey2' not in data:
        return jsonify({'error': 'Both survey1 and survey2 data are required'}), 400
    
    max_stations = data.get('max_stations', 15)
    
    result = perform_idt(data['survey1'], data['survey2'], max_stations)
    return jsonify(result)

@external_qc_bp.route('/adt', methods=['POST'])
def azimuth_difference_test():
    """
    Perform Azimuth Difference Test (ADT)
    
    Expected input format:
    {
        "survey1": [
            {
                "depth": float,
                "azimuth": float,
                "error_model": {
                    "azimuth_std": float  # standard deviation in degrees
                }
            },
            ...
        ],
        "survey2": [
            {
                "depth": float,
                "azimuth": float,
                "error_model": {
                    "azimuth_std": float  # standard deviation in degrees
                }
            },
            ...
        ],
        "max_stations": integer  # Optional, default is 15
    }
    """
    data = request.get_json()
    
    if 'survey1' not in data or 'survey2' not in data:
        return jsonify({'error': 'Both survey1 and survey2 data are required'}), 400
    
    max_stations = data.get('max_stations', 15)
    
    result = perform_adt(data['survey1'], data['survey2'], max_stations)
    return jsonify(result)

@external_qc_bp.route('/codt', methods=['POST'])
def coordinate_difference_test():
    """
    Perform Co-ordinate Difference Test (CODT)
    
    Expected input format:
    {
        "survey1": [
            {
                "depth": float,
                "north": float,
                "east": float,
                "tvd": float,
                "inclination": float,
                "azimuth": float,
                "error_model": {
                    "lateral_std": float,
                    "highside_std": float,
                    "alonghole_std": float
                }
            },
            ...
        ],
        "survey2": [
            {
                "depth": float,
                "north": float,
                "east": float,
                "tvd": float,
                "inclination": float,
                "azimuth": float,
                "error_model": {
                    "lateral_std": float,
                    "highside_std": float,
                    "alonghole_std": float
                }
            },
            ...
        ],
        "max_stations": integer  # Optional, default is 15
    }
    """
    data = request.get_json()
    
    if 'survey1' not in data or 'survey2' not in data:
        return jsonify({'error': 'Both survey1 and survey2 data are required'}), 400
    
    max_stations = data.get('max_stations', 15)
    
    result = perform_codt(data['survey1'], data['survey2'], max_stations)
    return jsonify(result)