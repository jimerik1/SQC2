# src/utils/ipm_parser.py
from src.models.ipm import IPMFile

def parse_ipm_file(file_content):
    """Parse IPM file content and return an IPMFile object"""
    return IPMFile(file_content)