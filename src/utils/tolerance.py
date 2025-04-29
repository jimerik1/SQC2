def get_error_term_value(ipm_data, term_name, error_type="e", tie_on="s", default=0.0):
    """
    Enhanced error term value retrieval with better fallbacks
    
    Args:
        ipm_data: IPM data or raw content
        term_name: Name of the error term (e.g. 'MBX')
        error_type: Type of error ('e' for error, 's' for sigma)
        tie_on: Tie-on value ('s' for systematic, 'r' for random)
        default: Default value if term not found
    """
    try:
        # Parse IPM if needed
        if isinstance(ipm_data, str):
            from .ipm_parser import parse_ipm_file
            ipm_data = parse_ipm_file(ipm_data)
        
        # Try variations of the term name
        variations = [
            term_name,
            term_name.upper(),
            term_name.lower(),
            term_name.replace('-', '_'),
            term_name.replace('_', '-')
        ]
        
        # Try each variation
        for name in variations:
            term = ipm_data.get_error_term(name, error_type, tie_on)
            if term and "value" in term:
                return term["value"]
        
        # Look for alternative formats (e.g., ABXY-TI1S vs ABXY_TI1)
        if "-TI" in term_name:
            base = term_name.split("-TI")[0]
            alt_name = f"{base}_TI1"
            term = ipm_data.get_error_term(alt_name, error_type, tie_on)
            if term and "value" in term:
                return term["value"]
        
        # Not found after all attempts
        return default
    
    except Exception as e:
        # Log error and return default
        return default