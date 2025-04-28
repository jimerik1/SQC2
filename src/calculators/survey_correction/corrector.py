# services/survey/corrector.py
import math
import numpy as np
from src.models.survey import Survey
from utils.ipm_parser import parse_ipm_file

def correct_surveys(surveys_data, ipm_data=None):
    """
    Applies corrections to survey data based on error terms
    
    Args:
        surveys_data (list): List of survey data dictionaries
        ipm_data (dict, optional): Instrument Performance Model data
        
    Returns:
        list: Corrected survey data
    """
    # Convert to Survey objects if needed
    surveys = []
    for survey_data in surveys_data:
        if isinstance(survey_data, dict):
            surveys.append(Survey(survey_data))
        else:
            surveys.append(survey_data)
    
    # Parse IPM if provided
    ipm = None
    if ipm_data:
        if isinstance(ipm_data, str):
            ipm = parse_ipm_file(ipm_data)
        else:
            ipm = ipm_data
    
    corrected_surveys = []
    
    for survey in surveys:
        # Create a copy of the survey
        corrected = Survey(survey.to_dict())
        
        # Apply sensor corrections if IPM is available
        if ipm:
            corrected = apply_sensor_corrections(corrected, ipm)
        
        # Apply geomagnetic model corrections for magnetic tools
        if hasattr(corrected, 'Bx') and hasattr(corrected, 'By') and hasattr(corrected, 'Bz'):
            corrected = apply_magnetic_corrections(corrected)
        
        corrected_surveys.append(corrected)
    
    # Apply multi-station corrections if multiple surveys are available
    if len(corrected_surveys) > 1:
        corrected_surveys = apply_multi_station_corrections(corrected_surveys, ipm)
    
    # Convert back to dictionaries
    return [survey.to_dict() for survey in corrected_surveys]

def apply_sensor_corrections(survey, ipm):
    """
    Apply instrument error corrections based on IPM
    
    Args:
        survey (Survey): Survey object to correct
        ipm (IPMFile): Instrument Performance Model
        
    Returns:
        Survey: Corrected survey
    """
    # Create a copy of the survey
    corrected = Survey(survey.to_dict())
    
    # Apply accelerometer corrections
    if hasattr(survey, 'Gx') and hasattr(survey, 'Gy') and hasattr(survey, 'Gz'):
        # Get accelerometer bias terms
        abx = ipm.get_error_term('ABXY-TI1S', 'e', 's')
        abx_value = abx['value'] if abx else 0.0
        
        aby = ipm.get_error_term('ABXY-TI1S', 'e', 's')
        aby_value = aby['value'] if aby else 0.0
        
        abz = ipm.get_error_term('ABZ', 'e', 's')
        abz_value = abz['value'] if abz else 0.0
        
        # Get accelerometer scale factor terms
        asx = ipm.get_error_term('ASXY-TI1S', 'e', 's')
        asx_value = asx['value'] if asx else 0.0
        
        asy = ipm.get_error_term('ASXY-TI1S', 'e', 's')
        asy_value = asy['value'] if asy else 0.0
        
        asz = ipm.get_error_term('ASZ', 'e', 's')
        asz_value = asz['value'] if asz else 0.0
        
        # Apply corrections to accelerometer readings
        corrected.Gx = survey.Gx - abx_value
        corrected.Gy = survey.Gy - aby_value
        corrected.Gz = survey.Gz - abz_value
        
        # Apply scale factor corrections
        standard_g = 9.80665  # m/s^2
        corrected.Gx = corrected.Gx / (1 + asx_value * standard_g)
        corrected.Gy = corrected.Gy / (1 + asy_value * standard_g)
        corrected.Gz = corrected.Gz / (1 + asz_value * standard_g)
    
    # Apply magnetometer corrections
    if hasattr(survey, 'Bx') and hasattr(survey, 'By') and hasattr(survey, 'Bz'):
        # Get magnetometer bias terms
        mbx = ipm.get_error_term('MBX', 'e', 's')
        mbx_value = mbx['value'] if mbx else 0.0
        
        mby = ipm.get_error_term('MBY', 'e', 's')
        mby_value = mby['value'] if mby else 0.0
        
        mbz = ipm.get_error_term('MBZ', 'e', 's')
        mbz_value = mbz['value'] if mbz else 0.0
        
        # Get magnetometer scale factor terms
        msx = ipm.get_error_term('MSX', 'e', 's')
        msx_value = msx['value'] if msx else 0.0
        
        msy = ipm.get_error_term('MSY', 'e', 's')
        msy_value = msy['value'] if msy else 0.0
        
        msz = ipm.get_error_term('MSZ', 'e', 's')
        msz_value = msz['value'] if msz else 0.0
        
        # Apply corrections to magnetometer readings
        corrected.Bx = survey.Bx - mbx_value
        corrected.By = survey.By - mby_value
        corrected.Bz = survey.Bz - mbz_value
        
        # Apply scale factor corrections
        if hasattr(survey, 'expected_geomagnetic_field') and survey.expected_geomagnetic_field:
            bt = survey.expected_geomagnetic_field.get('total_field', 0)
            if bt > 0:
                corrected.Bx = corrected.Bx / (1 + msx_value * bt)
                corrected.By = corrected.By / (1 + msy_value * bt)
                corrected.Bz = corrected.Bz / (1 + msz_value * bt)
    
    # Apply gyro corrections if gyro data is present
    if hasattr(survey, 'gyro_x') and hasattr(survey, 'gyro_y'):
        # Get gyro bias terms
        gbx = ipm.get_error_term('GBX', 'e', 's')
        gbx_value = gbx['value'] if gbx else 0.0
        
        gby = ipm.get_error_term('GBY', 'e', 's')
        gby_value = gby['value'] if gby else 0.0
        
        # Apply corrections to gyro readings
        corrected.gyro_x = survey.gyro_x - gbx_value
        corrected.gyro_y = survey.gyro_y - gby_value
    
    # Recalculate inclination and azimuth based on corrected sensor readings
    if hasattr(corrected, 'Gx') and hasattr(corrected, 'Gy') and hasattr(corrected, 'Gz'):
        # Recalculate inclination
        g = math.sqrt(corrected.Gx**2 + corrected.Gy**2 + corrected.Gz**2)
        if g > 0:
            corrected.inclination = math.degrees(math.acos(corrected.Gz / g))
            
            # Recalculate toolface
            if corrected.inclination > 0.1:  # Non-vertical
                corrected.toolface = math.degrees(math.atan2(corrected.Gy, corrected.Gx))
                # Convert to 0-360 range
                if corrected.toolface < 0:
                    corrected.toolface += 360
    
    # Recalculate azimuth for magnetic tools
    if (hasattr(corrected, 'Bx') and hasattr(corrected, 'By') and hasattr(corrected, 'Bz') and
        hasattr(corrected, 'Gx') and hasattr(corrected, 'Gy') and hasattr(corrected, 'Gz')):
        
        # Calculate magnetic azimuth
        if corrected.inclination < 1.0 or corrected.inclination > 179.0:
            # Near-vertical - azimuth is unreliable
            pass
        else:
            # Get unit vectors
            g_mag = math.sqrt(corrected.Gx**2 + corrected.Gy**2 + corrected.Gz**2)
            gx_unit = corrected.Gx / g_mag if g_mag > 0 else 0
            gy_unit = corrected.Gy / g_mag if g_mag > 0 else 0
            gz_unit = corrected.Gz / g_mag if g_mag > 0 else 0
            
            # Calculate magnetic field components in horizontal plane
            bh_x = corrected.Bx - gz_unit * (corrected.Bx * gz_unit + corrected.By * gy_unit + corrected.Bz * gx_unit)
            bh_y = corrected.By - gy_unit * (corrected.Bx * gz_unit + corrected.By * gy_unit + corrected.Bz * gx_unit)
            
            # Calculate magnetic azimuth
            mag_azimuth = math.degrees(math.atan2(bh_y, bh_x))
            if mag_azimuth < 0:
                mag_azimuth += 360
                
            # Apply magnetic declination correction if available
            if hasattr(survey, 'expected_geomagnetic_field') and survey.expected_geomagnetic_field:
                declination = survey.expected_geomagnetic_field.get('declination', 0)
                corrected.azimuth = (mag_azimuth + declination) % 360
            else:
                corrected.azimuth = mag_azimuth
    
    return corrected

def apply_magnetic_corrections(survey):
    """Apply corrections for the geomagnetic field"""
    corrected = Survey(survey.to_dict())
    
    # Use provided reference field data
    if hasattr(survey, 'expected_geomagnetic_field') and survey.expected_geomagnetic_field:
        # Apply corrections based on the provided field data
        # (Implement actual correction algorithm here)
        pass
    else:
        raise ValueError("Expected geomagnetic field data not provided in survey input")
    
    return corrected

def apply_multi_station_corrections(surveys, ipm=None):
    """Apply corrections based on multi-station analysis"""
    # This would implement multi-station analysis corrections
    # For now, return a message that this is not implemented
    return surveys  # Return unmodified surveys with a logging message
