# src/zones.py
import numpy as np
import pandas as pd
from typing import Tuple, Optional

def assign_zone_id(
    s_now: float,
    stop_lines_s: pd.DataFrame,
    turn_segs: pd.DataFrame,
    L: float,
    stop_approach_m: float
) -> Tuple[str, str]:
    """
    Returns (zone_type, zone_id)
    Priority: TURN > STOP_APPROACH > STRAIGHT
    """

    # TURN (wrap-safe)
    for i, z in turn_segs.iterrows():
        a = float(z["s_start"]); b = float(z["s_end"])
        if a <= b:
            in_turn = (a <= s_now <= b)
        else:
            in_turn = (s_now >= a) or (s_now <= b)

        if in_turn:
            return "TURN", f"TURN_{i+1}"

    # STOP_APPROACH: if within [0, stop_approach_m] ahead of stop line
    # choose nearest stop ahead
    best = None
    for _, r in stop_lines_s.iterrows():
        s_stop = float(r["s_stop_m"])
        d = s_stop - s_now
        if d < 0:
            d += L
        if 0 < d <= stop_approach_m:
            if best is None or d < best[0]:
                best = (d, int(r["stop_line"]))

    if best is not None:
        return "STOP_APPROACH", f"STOP_{best[1]}_APPROACH"

    return "STRAIGHT", "STRAIGHT"
