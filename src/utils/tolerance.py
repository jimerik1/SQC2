def get_error_term_value(ipm_data, term_name, error_type, sigma_type):
    """
    Get error term value from IPM data
    
    Args:
        ipm_data (dict): IPM data containing error terms
        term_name (str): Name of the error term (e.g. 'MBX')
        error_type (str): Type of error ('e' for error, 's' for sigma)
        sigma_type (str): Type of sigma ('s' for systematic, 'r' for random)
        
    Returns:
        float: Error term value
    """
    if isinstance(ipm_data, str):
        from .ipm_parser import parse_ipm_file
        ipm_data = parse_ipm_file(ipm_data)
    
    return ipm_data.get(term_name, {}).get(error_type, {}).get(sigma_type, 0.0) 