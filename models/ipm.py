class IPMFile:
    """Class representing a parsed IPM file for error modeling"""
    
    def __init__(self, content):
        self.short_name = ""
        self.description = ""
        self.error_terms = []
        self.parse_content(content)
    
    def parse_content(self, content):
        """Parse IPM file content"""
        lines = content.strip().split('\n')
        
        for line in lines:
            if line.startswith('#ShortName:'):
                self.short_name = line.replace('#ShortName:', '').strip()
            elif line.startswith('#Description:'):
                self.description = line.replace('#Description:', '').strip()
            elif not line.startswith('#') and line.strip():
                # Parse error term line
                parts = line.split()
                if len(parts) >= 6:
                    error_term = {
                        'name': parts[0],
                        'vector': parts[1],
                        'tie_on': parts[2],
                        'unit': parts[3],
                        'value': float(parts[4]),
                        'formula': ' '.join(parts[5:])
                    }
                    self.error_terms.append(error_term)
    
    def get_error_term(self, name, vector='', tie_on=''):
        """Get a specific error term by name and optional vector and tie-on"""
        for term in self.error_terms:
            if (term['name'] == name and
                (not vector or term['vector'] == vector) and
                (not tie_on or term['tie_on'] == tie_on)):
                return term
        return None