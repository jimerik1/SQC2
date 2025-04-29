# models/ipm.py
"""
IPMFile – in-memory representation of an ISCWSA Instrument
Performance Model.

Key design goals
----------------
1. Parse once, then answer look-ups in O(1).
2. Never hide unit conversions that depend on run-time context
   (e.g. local gravity).  Return the raw unit so the caller can
   decide how to scale.
3. Provide a best-effort canonical value **only** when the mapping
   is context-free (µT → nT, rad/s → deg/h, ft → m, …).

Typical use
-----------
>>> ipm = parse_ipm_file(txt)
>>> val, unit = ipm.get_sigma("ABXY-TI1S")   # ('value', 'unit')
>>> if unit == "m/s2":
...     val /= g_local                       # convert to g-units
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Tuple, Optional, List

# --------------------------------------------------------------------------- #
#  Unit maps (context-free conversions only)
# --------------------------------------------------------------------------- #

_STATIC_CONVERT: Dict[str, Tuple[str, float]] = {
    #   raw → (canonical, factor)
    "µt":   ("nT", 1_000.0),
    "ut":   ("nT", 1_000.0),
    "uT":   ("nT", 1_000.0),
    "μt":   ("nT", 1_000.0),
    "nt":   ("nT", 1.0),
    "nT":   ("nT", 1.0),

    "rad/s": ("deg/hr", 57.29577951308232 * 3600.0),
    "rad/s2": ("deg/hr²", 57.29577951308232 * 3600.0),  # rarely used
    "deg/hr": ("deg/hr", 1.0),

    "ft": ("m", 0.3048),
    "feet": ("m", 0.3048),
    "m": ("m", 1.0),
    "-": ("-", 1.0),          # dimensionless scale terms
}

def _canonicalise(value: float, unit_raw: str) -> Tuple[float, str]:
    """Return (value_in_canonical, canonical_unit).  If unknown unit,
    return raw value and raw unit."""
    u = unit_raw.lower()
    if u in _STATIC_CONVERT:
        canonical_unit, factor = _STATIC_CONVERT[u]
        return value * factor, canonical_unit
    return value, unit_raw


# --------------------------------------------------------------------------- #
#  Main class
# --------------------------------------------------------------------------- #

class IPMFile:
    """
    Parses an IPM text and provides fast σ look-ups.

    error_terms : List[dict] – each dict contains
        name, vector, tie_on, unit_raw, value_raw, value, unit
    """

    # ------------------------------ #
    def __init__(self, content: str | Path):
        if isinstance(content, Path):
            content = content.read_text(encoding="utf-8", errors="ignore")
        self.error_terms: List[Dict[str, object]] = []
        self._index: Dict[Tuple[str, str, str], Dict[str, object]] = {}
        self.parse_content(content)

    # ------------------------------ #
    def parse_content(self, txt: str):
        for ln in txt.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue

            parts = ln.split(maxsplit=5)
            if len(parts) < 6:
                # malformed line – skip or raise
                continue

            name, vector, tie_on, unit_raw, value_raw, formula = parts
            val_raw = float(value_raw)
            val_canon, unit_canon = _canonicalise(val_raw, unit_raw)

            term = {
                "name": name,
                "vector": vector,
                "tie_on": tie_on,
                "unit_raw": unit_raw,
                "value_raw": val_raw,
                "value": val_canon,   # canonical *if static-convertible*
                "unit": unit_canon,
                "formula": formula,
            }
            self.error_terms.append(term)
            self._index[(name, vector, tie_on)] = term

    # ------------------------------ #
    def get_error_term(
        self,
        name: str,
        vector: str = "",
        tie_on: str = "",
    ) -> Optional[Dict[str, object]]:
        """Return the stored term dict or None if not present."""
        # empty string = wildcard
        if vector or tie_on:
            return self._index.get((name, vector, tie_on))
        # wildcard search: first match
        for (nm, vec, to), term in self._index.items():
            if nm == name:
                if (not vector or vec == vector) and (not tie_on or to == tie_on):
                    return term
        return None

    # ------------------------------ #
    def get_sigma(
        self,
        name: str,
        vector: str = "e",
        tie_on: str = "s",
    ) -> Tuple[float, str]:
        """Return (value, unit).  0.0,'' if term missing."""
        term = self._index.get((name, vector, tie_on))
        if not term:
            return 0.0, ""
        return term["value"], term["unit"]

    # ------------------------------ #
    # Convenience: text-roundtrip
    def to_dict(self) -> Dict[str, object]:
        return {
            "short_name": getattr(self, "short_name", ""),
            "description": getattr(self, "description", ""),
            "error_terms": self.error_terms,
        }

    # ------------------------------ #
    def __repr__(self):
        return f"<IPMFile {len(self.error_terms)} terms>"


# --------------------------------------------------------------------------- #
#  Helper entry point for the rest of the code base
# --------------------------------------------------------------------------- #

def parse_ipm_file(content: str | Path) -> IPMFile:
    """Thin wrapper used elsewhere in the code base."""
    return IPMFile(content)

# --------------------------------------------------------------------------- #
#  Dictionary-like get method for compatibility
# --------------------------------------------------------------------------- #
def get(self, name, default=None):
    """Dictionary-like get method for compatibility"""
    # Implementation depends on what data structure this method should access
    # This is just a placeholder example
    return getattr(self, name, default)
