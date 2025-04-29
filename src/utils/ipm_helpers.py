"""
Helper functions for consistent IPM handling across the codebase
"""
import logging
from typing import Union, Dict, Any, List, Optional
from src.models.ipm import IPMFile
from src.utils.ipm_parser import parse_ipm_file

# Configure logging
logger = logging.getLogger(__name__)

def prepare_ipm(ipm_data):
    """Consistently prepare IPM data from various input formats"""
    if isinstance(ipm_data, IPMFile):
        return ipm_data
    
    if isinstance(ipm_data, str):
        try:
            return parse_ipm_file(ipm_data)
        except Exception as e:
            logger.error(f"Error parsing IPM content: {e}")
            # Return minimal IPM to avoid cascading failures
            return IPMFile("#ShortName:Error\n")
    
    # Other input types (dict, etc.) could be handled here
    logger.error(f"Unsupported IPM data type: {type(ipm_data)}")
    return IPMFile("#ShortName:Empty\n")

def get_required_terms(ipm_data, required_terms, confidence=3.0):
    """
    Get multiple error terms at once with consistent handling
    
    Args:
        ipm_data: IPM data in any supported format
        required_terms: List of (name, error_type, tie_on) tuples
        confidence: Confidence level multiplier (3.0 = 3σ)
    """
    from src.utils.tolerance import get_error_term_value
    
    ipm = prepare_ipm(ipm_data)
    result = {}
    missing = []
    
    for name, error_type, tie_on in required_terms:
        value = get_error_term_value(ipm, name, error_type, tie_on)
        if value == 0.0:  # Assume default when not found
            missing.append(name)
        result[name] = value * confidence
    
    if missing:
        logger.warning(f"Terms not found in IPM: {', '.join(missing)}")
    
    return result

def verify_ipm_compatibility(ipm_data, test_name, required_terms):
    """Check if an IPM file is compatible with a specific test"""
    ipm = prepare_ipm(ipm_data)
    
    missing = []
    for term in required_terms:
        if not ipm.get_error_term(term):
            missing.append(term)
    
    if missing:
        return False, f"Missing required terms for {test_name}: {', '.join(missing)}"
    
    return True, f"IPM is compatible with {test_name}"