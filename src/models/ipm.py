class IPMFile:
    def __init__(self, content: str | Path):
        self.error_terms = []
        self._index = {}  # Primary index by (name, vector, tie_on)
        self._name_index = {}  # Secondary index by name for faster lookups
        self.metadata = {}  # Store metadata (ShortName, Description, etc.)
        self.parse_content(content)
    
    def parse_content(self, content):
        """More robust parsing with metadata handling"""
        lines = content.splitlines() if isinstance(content, str) else content.read_text().splitlines()
        
        # Parse metadata and error terms
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('#'):
                if ':' in line:  # Metadata line
                    key, value = line[1:].split(':', 1)
                    self.metadata[key.strip()] = value.strip()
                continue
                
            # Handle different whitespace patterns
            parts = line.split(None, 5)  # Split by any whitespace
            if len(parts) < 5:
                continue  # Skip malformed lines
                
            # Ensure we have 6 parts (add empty formula if needed)
            while len(parts) < 6:
                parts.append("")
                
            name, vector, tie_on, unit_raw, value_raw, formula = parts
            
            try:
                val_raw = float(value_raw)
            except ValueError:
                val_raw = 0.0  # Default for invalid values
            
            # Normalize and convert
            val_canon, unit_canon = self._canonicalize(val_raw, unit_raw.lower())
            
            term = {
                "name": name,
                "vector": vector,
                "tie_on": tie_on,
                "unit_raw": unit_raw,
                "value_raw": val_raw,
                "value": val_canon,
                "unit": unit_canon,
                "formula": formula,
            }
            
            self.error_terms.append(term)
            
            # Index by tuple and normalize name
            key = (name, vector, tie_on)
            self._index[key] = term
            
            # Also index by name-only for fast lookups with wildcards
            norm_name = name.upper()  # Normalize case
            if norm_name not in self._name_index:
                self._name_index[norm_name] = []
            self._name_index[norm_name].append(term)
            
            # Add alternative name format (replace hyphens with underscores and vice versa)
            alt_name = name.replace('-', '_') if '-' in name else name.replace('_', '-')
            alt_key = (alt_name, vector, tie_on)
            if alt_key not in self._index:
                self._index[alt_key] = term
                
                norm_alt = alt_name.upper()
                if norm_alt not in self._name_index:
                    self._name_index[norm_alt] = []
                self._name_index[norm_alt].append(term)
    
    def _canonicalize(self, value, unit):
        """Enhanced unit mapping with more comprehensive coverage"""
        # Expanded unit mapping
        unit_map = {
            # Magnetic units
            "µt": ("nT", 1000.0),
            "ut": ("nT", 1000.0),
            "uT": ("nT", 1000.0),
            "μt": ("nT", 1000.0),
            "nt": ("nT", 1.0),
            "nT": ("nT", 1.0),
            "dnt": ("nT", 1.0),  # deg*nT treated as nT
            
            # Angular units
            "rad/s": ("deg/hr", 57.29577951308232 * 3600.0),
            "rad/s2": ("deg/hr²", 57.29577951308232 * 3600.0),
            "deg/hr": ("deg/hr", 1.0),
            "d": ("deg", 1.0),
            "deg": ("deg", 1.0),
            
            # Length units
            "ft": ("m", 0.3048),
            "feet": ("m", 0.3048),
            "m": ("m", 1.0),
            
            # Acceleration units
            "m/s2": ("g", 1.0/9.80665),  # Convert to g-units
            "g": ("g", 1.0),
            
            # Dimensionless
            "-": ("-", 1.0),
            "im": ("-", 1.0),  # Inverse meters
            "1/m": ("-", 1.0),
        }
        
        if unit in unit_map:
            canonical_unit, factor = unit_map[unit]
            return value * factor, canonical_unit
        
        # Return as-is if not found
        return value, unit
    
    def get_error_term(self, name, vector="", tie_on=""):
        """More flexible error term lookup with normalization"""
        # Try direct lookup first
        if (name, vector, tie_on) in self._index:
            return self._index[(name, vector, tie_on)]
        
        # Try normalized name variations
        variations = [
            name.upper(),
            name.lower(),
            name.replace('-', '_').upper(),
            name.replace('_', '-').upper()
        ]
        
        for var_name in variations:
            if var_name in self._name_index:
                # Found candidates, filter by vector and tie_on if provided
                candidates = self._name_index[var_name]
                for term in candidates:
                    if (not vector or term["vector"] == vector) and \
                       (not tie_on or term["tie_on"] == tie_on):
                        return term
        
        # Not found after all attempts
        return None
    
    # Other methods remain the same with appropriate enhancements