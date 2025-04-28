# services/survey/analyzer.py
import math
import numpy as np
from src.models.survey import Survey

def analyze_surveys(surveys_data):
    """
    Analyzes a set of survey measurements for consistency and trends
    
    Args:
        surveys_data (list): List of survey data dictionaries
        
    Returns:
        dict: Analysis results including statistics and potential issues
    """
    result = {
        'statistics': {},
        'consistency': {},
        'anomalies': []
    }
    
    # Convert to Survey objects if needed
    surveys = []
    for survey_data in surveys_data:
        if isinstance(survey_data, dict):
            surveys.append(Survey(survey_data))
        else:
            surveys.append(survey_data)
    
    if len(surveys) < 2:
        result['statistics']['count'] = len(surveys)
        return result
    
    # Extract arrays of key measurements
    depths = np.array([s.depth for s in surveys])
    inclinations = np.array([s.inclination for s in surveys])
    azimuths = np.array([s.azimuth for s in surveys])
    
    # Basic statistics
    result['statistics']['count'] = len(surveys)
    result['statistics']['depth'] = {
        'min': float(np.min(depths)),
        'max': float(np.max(depths)),
        'average': float(np.mean(depths))
    }
    result['statistics']['inclination'] = {
        'min': float(np.min(inclinations)),
        'max': float(np.max(inclinations)),
        'average': float(np.mean(inclinations))
    }
    result['statistics']['azimuth'] = {
        'min': float(np.min(azimuths)),
        'max': float(np.max(azimuths)),
        'average': float(np.mean(azimuths))
    }
    
    # Calculate dogleg severity between survey stations
    doglegs = []
    for i in range(1, len(surveys)):
        prev = surveys[i-1]
        curr = surveys[i]
        
        # Calculate dogleg severity in degrees per 30m
        inc1_rad = math.radians(prev.inclination)
        inc2_rad = math.radians(curr.inclination)
        azi1_rad = math.radians(prev.azimuth)
        azi2_rad = math.radians(curr.azimuth)
        
        # Compute dogleg angle
        cos_dogleg = math.cos(inc1_rad) * math.cos(inc2_rad) + \
                     math.sin(inc1_rad) * math.sin(inc2_rad) * math.cos(azi2_rad - azi1_rad)
        # Clamp to valid range for arccos
        cos_dogleg = max(min(cos_dogleg, 1.0), -1.0)
        dogleg_rad = math.acos(cos_dogleg)
        dogleg_deg = math.degrees(dogleg_rad)
        
        # Normalize to degrees per 30m
        depth_diff = curr.depth - prev.depth
        if depth_diff > 0:
            dogleg_per_30m = dogleg_deg * (30.0 / depth_diff)
            doglegs.append(dogleg_per_30m)
    
    if doglegs:
        result['statistics']['dogleg_severity'] = {
            'min': float(np.min(doglegs)),
            'max': float(np.max(doglegs)),
            'average': float(np.mean(doglegs))
        }
        
        # Check for excessive dogleg
        if np.max(doglegs) > 5.0:  # 5 degrees per 30m is often considered high
            result['anomalies'].append({
                'type': 'excessive_dogleg',
                'value': float(np.max(doglegs)),
                'threshold': 5.0,
                'description': 'Excessive dogleg severity detected'
            })
    
    # Check for unusual changes in inclination
    inc_changes = np.abs(np.diff(inclinations))
    if len(inc_changes) > 0 and np.max(inc_changes) > 3.0:
        result['anomalies'].append({
            'type': 'rapid_inclination_change',
            'value': float(np.max(inc_changes)),
            'threshold': 3.0,
            'description': 'Unusually rapid change in inclination detected'
        })
    
    # Check for unusual changes in azimuth for non-vertical sections
    non_vertical_idx = np.where(inclinations[1:] > 5.0)[0]  # Indices where inclination > 5 degrees
    if len(non_vertical_idx) > 0:
        # Get changes in azimuth for non-vertical sections
        azi_changes = np.abs(np.diff(azimuths))[non_vertical_idx]
        # Handle wrap-around (e.g., 359 to 1 degrees)
        azi_changes = np.minimum(azi_changes, 360 - azi_changes)
        
        if len(azi_changes) > 0 and np.max(azi_changes) > 10.0:
            result['anomalies'].append({
                'type': 'rapid_azimuth_change',
                'value': float(np.max(azi_changes)),
                'threshold': 10.0,
                'description': 'Unusually rapid change in azimuth detected'
            })
    
    # Check data consistency
    depth_spacing = np.diff(depths)
    result['consistency']['depth_spacing'] = {
        'min': float(np.min(depth_spacing)),
        'max': float(np.max(depth_spacing)),
        'average': float(np.mean(depth_spacing)),
        'std_dev': float(np.std(depth_spacing))
    }
    
    # Identify inconsistent survey spacing
    if np.std(depth_spacing) > 0.5 * np.mean(depth_spacing):
        result['anomalies'].append({
            'type': 'inconsistent_spacing',
            'value': float(np.std(depth_spacing)),
            'threshold': 0.5 * float(np.mean(depth_spacing)),
            'description': 'Survey stations have inconsistent depth spacing'
        })
    
    return result