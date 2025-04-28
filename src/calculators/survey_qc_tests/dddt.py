# services/qc/dddt.py
"""
Dual-Depth Difference Test (DDDT)

Implements Appendix 1 H of Ekseth et al. (2006).
Key fix: stretch-term now uses depth * TVD * ΔDST, per Eq. 13.
"""
import math
from src.models.qc_result import QCResult
from src.utils.ipm_parser import parse_ipm_file
from src.utils.tolerance import get_error_term_value


# --------------------------------------------------------------------------- #
#  Public API
# --------------------------------------------------------------------------- #
def perform_dddt(pipe_depth: float,
                 wireline_depth: float,
                 survey: dict,
                 ipm_data):
    """
    Dual-Depth Difference Test (DDDT)

    Args
    ----
    pipe_depth : float
        Depth from pipe tally [m].
    wireline_depth : float
        Depth from wireline (e.g. CCL) [m].
    survey : dict
        Must contain 'inclination' (deg) and may contain 'true_vertical_depth'.
    ipm_data : str | dict
        Raw IPM text or parsed IPMFile.

    Returns
    -------
    dict  – QCResult.as_dict()
    """
    inc_deg = survey.get("inclination", 0.0)

    # TVD – if caller did not supply it, approximate assuming straight hole
    tvd = survey.get("true_vertical_depth")
    if tvd is None:
        tvd = pipe_depth * math.cos(math.radians(inc_deg))

    depth_diff = pipe_depth - wireline_depth
    tol = calculate_dddt_tolerance(ipm_data, pipe_depth, tvd)

    result = QCResult("DDDT")
    result.set_validity(abs(depth_diff) <= tol)
    result.add_measurement("pipe_depth", pipe_depth)
    result.add_measurement("wireline_depth", wireline_depth)
    result.add_error("depth_difference", depth_diff)
    result.add_tolerance("depth_difference", tol)
    result.add_detail("true_vertical_depth", tvd)

    return result.to_dict()


# --------------------------------------------------------------------------- #
#  Core tolerance math
# --------------------------------------------------------------------------- #
def calculate_dddt_tolerance(ipm_data,
                             depth: float,
                             true_vertical_depth: float) -> float:
    """
    3-σ tolerance for ΔΔD  (Eq. 13, Ekseth 2006).

        ΔΔD = ΔDREF + Dt·ΔDSF + Dt·Dv·ΔDST

    where Dt = measured depth, Dv = TVD.
    """
    ipm = parse_ipm_file(ipm_data) if isinstance(ipm_data, str) else ipm_data

    # 1-σ sigmas from IPM
    dref_p = get_error_term_value(ipm, "DREF-PIPE", "e", "s")
    dref_w = get_error_term_value(ipm, "DREF-WIRE", "e", "s")
    dsf_p  = get_error_term_value(ipm, "DSF-PIPE",  "e", "s")
    dsf_w  = get_error_term_value(ipm, "DSF-WIRE",  "e", "s")
    dst_p  = get_error_term_value(ipm, "DST-PIPE",  "e", "s")
    dst_w  = get_error_term_value(ipm, "DST-WIRE",  "e", "s")

    # Combine independent pipe + wire sigmas (root-sum-square)
    dref_diff = math.hypot(dref_p, dref_w)
    dsf_diff  = math.hypot(dsf_p,  dsf_w)
    dst_diff  = math.hypot(dst_p,  dst_w)

    # Full 3-σ tolerance
    tol = 3.0 * math.sqrt(
        dref_diff ** 2 +
        (depth * dsf_diff) ** 2 +
        (depth * true_vertical_depth * dst_diff) ** 2      # ← fixed term
    )
    return tol