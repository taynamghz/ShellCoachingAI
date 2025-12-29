# src/track.py
import numpy as np
from typing import Dict, Tuple

R_EARTH = 6371000.0

def gps_to_local_xy(lat: float, lon: float, lat0: float, lon0: float) -> Tuple[float, float]:
    lat_rad = np.deg2rad(lat)
    lon_rad = np.deg2rad(lon)
    lat0_rad = np.deg2rad(lat0)
    lon0_rad = np.deg2rad(lon0)

    x = (lon_rad - lon0_rad) * np.cos(lat0_rad) * R_EARTH
    y = (lat_rad - lat0_rad) * R_EARTH
    return float(x), float(y)

def project_to_polyline(x: float, y: float, track: Dict) -> Tuple[float, float]:
    px = np.asarray(track["x"], dtype=float)
    py = np.asarray(track["y"], dtype=float)
    ps = np.asarray(track["s"], dtype=float)

    best_dist2 = float("inf")
    best_s = 0.0
    best_sign = 1.0

    for i in range(len(px) - 1):
        ax, ay = px[i], py[i]
        bx, by = px[i+1], py[i+1]
        vx, vy = bx - ax, by - ay

        vv = vx*vx + vy*vy
        if vv < 1e-9:
            continue

        wx, wy = x - ax, y - ay
        t = (wx*vx + wy*vy) / vv
        t = max(0.0, min(1.0, t))

        cx, cy = ax + t*vx, ay + t*vy
        dx, dy = x - cx, y - cy
        dist2 = dx*dx + dy*dy

        if dist2 < best_dist2:
            best_dist2 = dist2
            seg_s = ps[i] + t * (ps[i+1] - ps[i])
            best_s = float(seg_s)

            cross = vx*(y - ay) - vy*(x - ax)
            best_sign = 1.0 if cross >= 0 else -1.0

    d_signed = best_sign * np.sqrt(best_dist2)
    return best_s, float(d_signed)

def forward_dist(s_now: float, s_target: float, L: float) -> float:
    d = s_target - s_now
    if d < 0:
        d += L
    return float(d)

