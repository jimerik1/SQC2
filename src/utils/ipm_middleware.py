# src/utils/ipm_middleware.py

from typing import Dict, Any, Union, Optional
from pathlib import Path
from src.models.ipm import IPMFile
from src.utils.ipm_parser import parse_ipm_file
import logging

logger = logging.getLogger(__name__)

class IPMHandler:
    """Centralized IPM handling to avoid changes in calculator modules"""
    
    @staticmethod
    def prepare_ipm(ipm_data: Union[str, Dict, IPMFile, Path, None]) -> IPMFile:
        """Convert any IPM input format to a consistent IPMFile object"""
        if ipm_data is None:
            logger.warning("No IPM data provided, returning empty IPM")
            return IPMFile("#ShortName:Empty\n")
            
        if isinstance(ipm_data, IPMFile):
            return ipm_data
            
        if isinstance(ipm_data, (str, Path)):
            try:
                return parse_ipm_file(ipm_data)
            except Exception as e:
                logger.error(f"Error parsing IPM content: {e}")
                return IPMFile("#ShortName:Error\n")
                
        if isinstance(ipm_data, dict) and "ipm_content" in ipm_data:
            # Handle dict with ipm_content key
            return IPMHandler.prepare_ipm(ipm_data["ipm_content"])
            
        logger.error(f"Unsupported IPM data type: {type(ipm_data)}")
        return IPMFile("#ShortName:Empty\n")
        
    @staticmethod
    def get_term_value(ipm_data, name, vector="e", tie_on="s", default=0.0):
        """Get error term with robust fallbacks"""
        ipm = IPMHandler.prepare_ipm(ipm_data)
        
        # Try variations of the term name
        name_variations = [
            name,
            name.upper(),
            name.lower(),
            name.replace('-', '_'),
            name.replace('_', '-')
        ]
        
        for variant in name_variations:
            term = ipm.get_error_term(variant, vector, tie_on)
            if term and "value" in term:
                return term["value"]
        
        # Special case handling for common patterns
        if "-TI" in name:
            base = name.split("-TI")[0]
            # Try different numbering patterns
            for suffix in ["1", "1S", "2", "2S", "3", "3S"]:
                alt_name = f"{base}_TI{suffix}"
                term = ipm.get_error_term(alt_name, vector, tie_on)
                if term and "value" in term:
                    return term["value"]
                    
        return default

# Create a global instance for easy import
ipm_handler = IPMHandler()