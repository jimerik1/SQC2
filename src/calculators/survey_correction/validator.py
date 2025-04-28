# services/survey/validator.py
import math
from src.models.survey import Survey

def validate_survey(survey_data):
    """
    Validates survey data against basic quality criteria
    
    Args:
        survey_data (dict): Survey data to validate
        
    Returns:
        dict: Validation results with errors and warnings
    """
    result = {
        'is_valid': True,
        'errors': [],
        'warnings': []
    }
    
    # Create Survey object if dict was provided
    if isinstance(survey_data, dict):
        survey = Survey(survey_data)
    else:
        survey = survey_data
    
    # Validate depth (must be positive)
    if survey.depth <= 0:
        result['errors'].append('Depth must be positive')
        result['is_valid'] = False
        
    # Validate inclination (0-180 degrees)
    if not (0 <= survey.inclination <= 180):
        result['errors'].append('Inclination must be between 0 and 180 degrees')
        result['is_valid'] = False
        
    # Validate azimuth (0-360 degrees)
    if not (0 <= survey.azimuth < 360):
        result['errors'].append('Azimuth must be between 0 and 360 degrees')
        result['is_valid'] = False
        
    # Validate toolface (0-360 degrees)
    if not (0 <= survey.toolface < 360):
        result['errors'].append('Toolface must be between 0 and 360 degrees')
        result['is_valid'] = False
        
    # Validate accelerometer readings consistency
    if hasattr(survey, 'Gx') and hasattr(survey, 'Gy') and hasattr(survey, 'Gz'):
        # Calculate gravity magnitude (should be close to 1g)
        g_mag = math.sqrt(survey.Gx**2 + survey.Gy**2 + survey.Gz**2)
        if abs(g_mag - 1.0) > 0.1:  # 10% tolerance
            result['warnings'].append(f'Accelerometer magnitude {g_mag:.3f}g differs from expected 1g')
            
    # Validate magnetometer readings if available
    if hasattr(survey, 'Bx') and hasattr(survey, 'By') and hasattr(survey, 'Bz'):
        # Check if magnetometer readings are non-zero
        if survey.Bx == 0 and survey.By == 0 and survey.Bz == 0:
            result['errors'].append('Magnetometer readings are all zero')
            result['is_valid'] = False
            
    # Validate latitude/longitude if present
    if hasattr(survey, 'latitude') and (not -90 <= survey.latitude <= 90):
        result['errors'].append('Latitude must be between -90 and 90 degrees')
        result['is_valid'] = False
        
    if hasattr(survey, 'longitude') and (not -180 <= survey.longitude <= 180):
        result['errors'].append('Longitude must be between -180 and 180 degrees')
        result['is_valid'] = False
        
    return result