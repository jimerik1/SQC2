from flask import Blueprint, request, jsonify
from src.calculators.synthetic_raw_data_calculator.generator import (
    generate_synthetic_raw_data, 
    validate_synthetic_data
)
import re

synthetic_data_bp = Blueprint('synthetic_data', __name__)
parse_bp = Blueprint('parse', __name__)

@synthetic_data_bp.route('/test', methods=['GET'])
def test():
    return jsonify({"message": "Synthetic data blueprint is working"})

@synthetic_data_bp.route('/generate', methods=['POST'])
def generate_raw_data():
    """
    Generate synthetic raw sensor data from trajectory data
    
    Expected input format:
    {
        "trajectory": {
            "Depth": [0, 30, 60, ...],  # meters
            "Inc": [0, 5, 10, ...],     # degrees
            "Azi": [0, 10, 20, ...],    # degrees
            "tfo": [0, 0, 0, ...]       # degrees (optional)
        },
        "parameters": {
            "magnetic_dip": 73.484,          # degrees
            "magnetic_field_strength": 51541.551,  # nT
            "gravity": 9.81,                 # m/s²
            "declination": 1.429,            # degrees
            "add_noise": false,              # boolean (optional)
            "noise_level": 0.001             # ratio (optional)
        },
        "validate": true,              # boolean (optional)
        "include_stats": true          # boolean (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        if 'trajectory' not in data:
            return jsonify({"error": "Trajectory data is required"}), 400
            
        trajectory_data = data['trajectory']
        required_fields = ['Depth', 'Inc', 'Azi']
        
        for field in required_fields:
            if field not in trajectory_data:
                return jsonify({"error": f"Missing required field in trajectory data: {field}"}), 400
                
        # Extract parameters with defaults
        parameters = data.get('parameters', {})
        magnetic_dip = parameters.get('magnetic_dip', 73.484)
        magnetic_field_strength = parameters.get('magnetic_field_strength', 51541.551)
        gravity = parameters.get('gravity', 9.81)
        declination = parameters.get('declination', 1.429)
        add_noise = parameters.get('add_noise', False)
        noise_level = parameters.get('noise_level', 0.001)
        
        # Generate synthetic data
        result = generate_synthetic_raw_data(
            trajectory_data,
            magnetic_dip=magnetic_dip,
            magnetic_field_strength=magnetic_field_strength,
            gravity=gravity,
            declination=declination,
            add_noise=add_noise,
            noise_level=noise_level
        )
        
        # Optionally validate the synthetic data
        if data.get('validate', False):
            validation = validate_synthetic_data(
                result,
                magnetic_dip=magnetic_dip,
                magnetic_field_strength=magnetic_field_strength,
                gravity=gravity,
                declination=declination
            )
            result['validation'] = validation
            
        # Remove stats if not requested
        if not data.get('include_stats', True):
            if 'stats' in result:
                del result['stats']
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@synthetic_data_bp.route('/validate', methods=['POST'])
def validate_raw_data():
    """
    Validate synthetic raw sensor data against trajectory data
    
    Expected input format:
    {
        "sensor_data": {
            "Depth": [0, 30, 60, ...],  # meters
            "Inc": [0, 5, 10, ...],     # degrees
            "Azi": [0, 10, 20, ...],    # degrees
            "Gx": [0, 0.1, 0.2, ...],   # g units
            "Gy": [0, 0.1, 0.2, ...],   # g units
            "Gz": [1.0, 0.9, 0.8, ...], # g units
            "Bx": [10000, 15000, ...],  # nT
            "By": [10000, 15000, ...],  # nT
            "Bz": [40000, 40000, ...]   # nT
        },
        "parameters": {
            "magnetic_dip": 73.484,          # degrees
            "magnetic_field_strength": 51541.551,  # nT
            "gravity": 9.81,                 # m/s²
            "declination": 1.429             # degrees
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        if 'sensor_data' not in data:
            return jsonify({"error": "Sensor data is required"}), 400
            
        sensor_data = data['sensor_data']
        required_fields = ['Depth', 'Inc', 'Azi', 'Gx', 'Gy', 'Gz', 'Bx', 'By', 'Bz']
        
        for field in required_fields:
            if field not in sensor_data:
                return jsonify({"error": f"Missing required field in sensor data: {field}"}), 400
                
        # Extract parameters with defaults
        parameters = data.get('parameters', {})
        magnetic_dip = parameters.get('magnetic_dip', 73.484)
        magnetic_field_strength = parameters.get('magnetic_field_strength', 51541.551)
        gravity = parameters.get('gravity', 9.81)
        declination = parameters.get('declination', 1.429)
        
        # Validate the synthetic data
        result = validate_synthetic_data(
            sensor_data,
            magnetic_dip=magnetic_dip,
            magnetic_field_strength=magnetic_field_strength,
            gravity=gravity,
            declination=declination
        )
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@parse_bp.route('/parse', methods=['POST'])
def parse_text_to_json():
    """
    Parse text input (CSV, tab-delimited, or pasted table) and convert to JSON payload
    for the /generate endpoint.
    
    Accepts:
    - JSON: {"text": "..."}
    - Raw body: text/plain or text/csv (copied table or file upload)
    """
    try:
        # Get text content either from JSON or raw text body
        text = None
        if request.is_json:
            data = request.get_json()
            text = data.get('text') if data else None
        if not text:
            text = request.get_data(as_text=True).strip()

        if not text:
            return jsonify({"error": "No text content provided"}), 400

        # Parse the trajectory data
        trajectory_data = parse_trajectory_text(text)

        if not trajectory_data:
            return jsonify({"error": "Could not parse trajectory data from text"}), 400

        # Construct full payload
        payload = {
            "trajectory": trajectory_data,
            "parameters": {
                "magnetic_dip": 73.484,
                "magnetic_field_strength": 51541.551,
                "gravity": 9.81,
                "declination": 1.429,
                "add_noise": False,
                "noise_level": 0.001
            },
            "validate": True,
            "include_stats": True
        }

        return jsonify(payload)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def parse_trajectory_text(text):
    """
    Parse plain table text (CSV, tab, or space-delimited) into trajectory dict.
    Supports decimal comma format (e.g., '96,154').
    """
    lines = text.strip().split('\n')

    # Find the header line
    header_line = None
    for i, line in enumerate(lines):
        if 'md' in line.lower() and 'inc' in line.lower() and 'azi' in line.lower():
            header_line = i
            break

    if header_line is None:
        return None

    headers = re.split(r'[,\t\s]+', lines[header_line].strip().lower())
    md_idx = headers.index('md') if 'md' in headers else None
    inc_idx = headers.index('inc') if 'inc' in headers else None
    azi_idx = headers.index('azi') if 'azi' in headers else None
    tfo_idx = headers.index('tfo') if 'tfo' in headers else None

    if md_idx is None or inc_idx is None or azi_idx is None:
        return None

    # Data lists
    depths, incs, azis = [], [], []
    tfos = [] if tfo_idx is not None else None

    # Skip header + assumed units row
    for line in lines[header_line + 2:]:
        if not line.strip():
            continue
        fields = re.split(r'[,\t\s]+', line.strip())

        try:
            depths.append(float(fields[md_idx].replace(',', '.')))
            incs.append(float(fields[inc_idx].replace(',', '.')))
            azis.append(float(fields[azi_idx].replace(',', '.')))
            if tfos is not None and len(fields) > tfo_idx:
                tfos.append(float(fields[tfo_idx].replace(',', '.')))
        except (ValueError, IndexError):
            continue

    result = {
        "Depth": depths,
        "Inc": incs,
        "Azi": azis
    }
    if tfos:
        result["tfo"] = tfos

    return result