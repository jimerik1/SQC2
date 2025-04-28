from flask import Blueprint, request, jsonify
from services.survey.validator import validate_survey
from services.survey.analyzer import analyze_surveys
from services.survey.corrector import correct_surveys

survey_bp = Blueprint('survey', __name__)

@survey_bp.route('/validate', methods=['POST'])
def validate():
    data = request.get_json()
    result = validate_survey(data)
    return jsonify(result)

@survey_bp.route('/validate-batch', methods=['POST'])
def validate_batch():
    data = request.get_json()
    results = [validate_survey(survey) for survey in data['surveys']]
    return jsonify({'results': results})

@survey_bp.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    result = analyze_surveys(data['surveys'])
    return jsonify(result)

@survey_bp.route('/correct', methods=['POST'])
def correct():
    data = request.get_json()
    result = correct_surveys(data['surveys'])
    return jsonify(result)

@survey_bp.route('/export', methods=['POST'])
def export():
    data = request.get_json()
    # Add export format parameter support
    format_type = request.args.get('format', 'json')
    result = correct_surveys(data['surveys'])
    
    if format_type == 'json':
        return jsonify(result)
    elif format_type == 'csv':
        # Logic to convert to CSV
        return "CSV data", 200, {'Content-Type': 'text/csv'}
    else:
        return jsonify({"error": "Unsupported export format"}), 400
    
