# src/calculators/sag_correction/models.py
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import numpy as np

class Material(Enum):
    """Material types for BHA components."""
    STEEL = 1
    NON_MAGNETIC = 2

@dataclass
class BHAElement:
    """Represents a single element in the BHA structure."""
    description: str
    od: float  # Outer diameter in meters
    id: float  # Inner diameter in meters
    max_od: float  # Maximum outer diameter in meters
    length: float  # Length in meters
    weight: float  # Weight in metric tons
    material: Material = Material.STEEL
    
    @property
    def weight_per_meter(self) -> float:
        """Calculate the weight per meter of the element."""
        return self.weight / self.length if self.length > 0 else 0

@dataclass
class Stabilizer:
    """Represents a stabilizer blade in the BHA."""
    blade_od: float  # Outer diameter in meters
    distance_to_bit: float  # Distance from mid-point to bit in meters
    length: float  # Length in meters

@dataclass
class Trajectory:
    """Represents a survey measurement point."""
    md: float  # Measured depth in meters
    inc: float  # Inclination in degrees

@dataclass
class BHA:
    """Represents a complete Bottom Hole Assembly."""
    structure: List[BHAElement] = field(default_factory=list)
    stabilizers: List[Stabilizer] = field(default_factory=list)
    dni_to_bit: float = 0.0  # Distance from D&I sensor to bit in meters
    bend_angle: float = 0.0  # Bend angle in radians
    bend_to_bit: float = 0.0  # Distance from bend to bit in meters

@dataclass
class SagResult:
    """Results of a sag correction calculation."""
    sag: float            # rad
    grid: np.ndarray      # z-coords (m, measured from bit)
    opt: np.ndarray       # lateral position (m)
    low: np.ndarray       # lower boundary
    top: np.ndarray       # upper boundary
    mid: np.ndarray       # midline
    od: np.ndarray        # outer diameter
    id: np.ndarray        # inner diameter
    slope: np.ndarray     # θ(z) (rad)
    moment: np.ndarray    # M(z) (N·m)
    shear: np.ndarray     # V(z) (N)
    valid: bool           # validity flag