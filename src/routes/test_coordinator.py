from flask import Blueprint, request, jsonify
import json

test_coordinator_bp = Blueprint('test_coordinator', __name__)

@test_coordinator_bp.route('/station-complete', methods=['POST'])
def run_station_complete_tests():
    """Run all recommended tests for a completed station"""
    data = request.get_json()
    survey_type = data.get('survey_type')
    
    # Call the appropriate endpoints internally
    # This would need implementation of internal function calls
    # instead of endpoint redirects
    
    return jsonify({
        "message": f"Tests for {survey_type} station complete",
        "recommended_tests": _get_recommended_tests_for_stage("station", survey_type),
        "uncontrolled_error_terms": _get_uncontrolled_terms_for_stage("station", survey_type)
    })

@test_coordinator_bp.route('/survey-section-complete', methods=['POST'])
def run_section_complete_tests():
    """Run all recommended tests for a completed survey section"""
    data = request.get_json()
    survey_type = data.get('survey_type')
    
    return jsonify({
        "message": f"Tests for {survey_type} section complete",
        "recommended_tests": _get_recommended_tests_for_stage("section", survey_type),
        "uncontrolled_error_terms": _get_uncontrolled_terms_for_stage("section", survey_type)
    })

@test_coordinator_bp.route('/new-drill-section', methods=['POST'])
def run_new_section_tests():
    """Run all recommended tests for beginning a new drill section"""
    data = request.get_json()
    survey_type = data.get('survey_type')
    
    return jsonify({
        "message": f"Tests for new {survey_type} drill section",
        "recommended_tests": _get_recommended_tests_for_stage("new-section", survey_type),
        "uncontrolled_error_terms": _get_uncontrolled_terms_for_stage("new-section", survey_type)
    })

@test_coordinator_bp.route('/verification-survey-complete', methods=['POST'])
def run_verification_tests():
    """Run all recommended tests after a verification survey is completed"""
    data = request.get_json()
    survey_type = data.get('survey_type')
    verification_type = data.get('verification_type')
    
    return jsonify({
        "message": f"Tests for {survey_type} verification with {verification_type}",
        "recommended_tests": _get_recommended_tests_for_stage("verification", survey_type, verification_type),
        "uncontrolled_error_terms": _get_uncontrolled_terms_for_stage("verification", survey_type, verification_type)
    })

def _get_recommended_tests_for_stage(stage, survey_type, verification_type=None):
    """Return list of recommended tests for a given stage and survey type"""
    # This would be implemented based on the test recommendations table
    recommendations = {
        "station": {
            "magnetic": ["get", "tfdt"],
            "gyro": ["get", "hert"],
            "continuous-gyro": ["get", "hert"]
        },
        "section": {
            "magnetic": ["msat", "msmt"],
            "gyro": ["msat", "msgt"]
        },
        "new-section": {
            "magnetic": ["idt", "adt"],
            "gyro": ["idt", "adt"]
        },
        "verification": {
            "continuous-gyro": {
                "in-out": ["iomt", "cadt"],
                "independent": ["codt"]
            },
            "magnetic": {
                "independent": ["codt"]
            },
            "gyro": {
                "independent": ["codt"]
            }
        }
    }
    
    if stage == "verification":
        return recommendations[stage][survey_type].get(verification_type, [])
    else:
        return recommendations[stage].get(survey_type, [])

def _get_uncontrolled_terms_for_stage(stage, survey_type, verification_type=None):
    """Return list of uncontrolled error terms for a given stage and survey type"""
    # This would be implemented based on the uncontrolled error terms table
    uncontrolled = {
        "station": {
            "magnetic": ["Depth terms", "Sag", "Misalignments", "Declination"],
            "gyro": ["Depth terms", "Sag", "Misalignments"],
            "continuous-gyro": ["Depth terms", "Gyro drifts", "Misalignments"]
        },
        "section": {
            "magnetic": ["Depth terms", "Sag", "Declination"],
            "gyro": []
        },
        "new-section": {
            "magnetic": ["Depth terms", "Declination"],
            "gyro": ["Depth terms"]
        },
        "verification": {
            "continuous-gyro": {
                "in-out": ["Depth terms"],
                "independent": []
            },
            "magnetic": {
                "independent": []
            },
            "gyro": {
                "independent": []
            }
        }
    }
    
    if stage == "verification":
        return uncontrolled[stage][survey_type].get(verification_type, [])
    else:
        return uncontrolled[stage].get(survey_type, [])