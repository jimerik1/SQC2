# blueprints/qc/multi_station.py
from flask import Blueprint, request, jsonify
from src.calculators.survey_qc_tests.msat import perform_msat, perform_msat_with_corrections
from src.calculators.survey_qc_tests.msgt import perform_msgt
from src.calculators.survey_qc_tests.msmt import perform_msmt
from src.calculators.survey_qc_tests.mse import perform_mse
import numpy as np

multi_station_bp = Blueprint('multi_station', __name__)

@multi_station_bp.route('/msat', methods=['POST'])
def multi_station_accelerometer_test():
    """
    Perform Multi-Station Accelerometer Test (MSAT) on a set of survey measurements
    
    Expected input format:
    {
        "surveys": [
            {
                "accelerometer_x": float,  # m/s² units
                "accelerometer_y": float,  # m/s² units
                "accelerometer_z": float,  # m/s² units
                "inclination": float,      # degrees
                "toolface": float,         # degrees
                "expected_gravity": float  # m/s² units
            },
            ...  # at least 10 surveys required
        ],
        "ipm": string or object,  # IPM file content or parsed object
        "sigma": float,           # optional, for adjusted thresholds (default: 3.0)
        "apply_corrections": bool # optional, whether to apply corrections (default: false)
    }
    """
    data = request.get_json()
    
    # Validate required inputs
    if 'surveys' not in data or not isinstance(data['surveys'], list):
        return jsonify({'error': 'Survey data is required as a list'}), 400
    
    if len(data['surveys']) < 10:
        return jsonify({'error': 'At least 10 survey measurements required for MSAT'}), 400
    
    if 'ipm' not in data:
        return jsonify({'error': 'IPM data is required'}), 400
    
    # Extract sigma value with default of 3.0 if not specified
    sigma = data.get('sigma', 3.0)
    
    # Check if corrections should be applied (from request body)
    apply_corrections = data.get('apply_corrections', False)
    
    if apply_corrections:
        result = perform_msat_with_corrections(data['surveys'], data['ipm'], sigma=sigma)
    else:
        result = perform_msat(data['surveys'], data['ipm'], sigma=sigma)
    
    return jsonify(result)

@multi_station_bp.route('/msgt', methods=['POST'])
def multi_station_gyro_test():
    """Perform Multi-Station Gyro Test (MSGT) on a set of survey measurements"""
    data = request.get_json()
    result = perform_msgt(data['surveys'], data['ipm'])
    return jsonify(result)

@multi_station_bp.route('/msmt', methods=['POST'])
def multi_station_magnetometer_test():
    """
    Perform Multi-Station Magnetometer Test (MSMT) on a set of survey measurements
    
    Expected input format:
    {
        "surveys": [
            {
                "mag_x": float,           # nT units
                "mag_y": float,           # nT units
                "mag_z": float,           # nT units
                "accelerometer_x": float, # m/s² units
                "accelerometer_y": float, # m/s² units
                "accelerometer_z": float, # m/s² units
                "inclination": float,     # degrees
                "azimuth": float,         # degrees
                "toolface": float,        # degrees
                "expected_geomagnetic_field": {
                    "total_field": float, # nT
                    "dip": float          # degrees
                }
            },
            ...  # at least 10 surveys required
        ],
        "ipm": string or object,  # IPM file content or parsed object
        "sigma": float            # optional, for adjusted thresholds (default: 3.0)
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid JSON data in request"}), 400
        
        # Basic validation
        if 'surveys' not in data or not isinstance(data['surveys'], list):
            return jsonify({"error": "Survey data is required as a list"}), 400
        
        if len(data['surveys']) < 10:
            return jsonify({"error": "At least 10 survey measurements required for MSMT"}), 400
        
        if 'ipm' not in data:
            return jsonify({"error": "IPM data is required"}), 400
        
        # Validate sigma is a positive number
        try:
            sigma = float(data.get('sigma', 3.0))
            if sigma <= 0:
                return jsonify({"error": "Sigma must be positive"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "Sigma must be a valid number"}), 400
        
        # Run the MSMT with comprehensive error handling
        try:
            result = perform_msmt(data['surveys'], data['ipm'], sigma=sigma)
            return jsonify(result)
        except (ValueError, KeyError) as e:
            # Handle validation errors
            return jsonify({"error": f"Validation error: {str(e)}"}), 422
        except np.linalg.LinAlgError as e:
            # Handle numerical computation errors
            return jsonify({"error": f"Linear algebra error: {str(e)}"}), 422
        except (ArithmeticError, OverflowError, FloatingPointError) as e:
            # Handle math domain errors and other numerical issues
            return jsonify({"error": f"Numerical computation error: {str(e)}"}), 422
        except Exception as e:
            # Catch any other unexpected errors
            return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
            
    except Exception as e:
        # Last resort error handler
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    
    
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
