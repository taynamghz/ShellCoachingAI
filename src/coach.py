# src/coach.py
import time
from collections import deque
from typing import Dict, Any, Optional, Tuple, List

import numpy as np
import pandas as pd

from .track_map import gps_to_local_xy, project_to_polyline
from .zones import assign_zone_id

class Coach:
    def __init__(self, cfg: Dict[str, Any], track: Dict, stop_lines_s: pd.DataFrame, turn_segs: pd.DataFrame, zone_memory: pd.DataFrame):
        self.cfg = cfg
        self.track = track
        self.stop_lines_s = stop_lines_s
        self.turn_segs = turn_segs
        self.zone_memory = zone_memory
        self.L = float(track["length_m"])

        self.lat0 = None
        self.lon0 = None

        self.buf = deque()  # list of dict samples
        self.last_cue_time = {}  # cue_key -> ts
        self.last_cue_by_zone = {}  # zone_id -> ts (for zone cooldown)
        self.last_cue_by_type = {}  # cue_type -> ts (for type cooldown)
        self.last_zone_id = None  # for hysteresis
        self.last_zone_type = None  # for hysteresis
        self.last_zone_s = None  # track position when zone changed
        self.last_cue_state = {}  # zone_id -> last state (green/red) for tracking improvements
        self.last_cue_values = {}  # zone_id -> (speed, power) tuple to track if driver is responding

    def ingest(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        msg is one telemetry JSON from MQTT.
        Returns a cue dict or None.
        """

        # -------- 1) extract fields (robust to missing keys) --------
        # Support both "timestamp" and "ts" fields
        ts = float(msg.get("timestamp") or msg.get("ts", time.time()))
        lat = msg.get("latitude", None)
        lon = msg.get("longitude", None)
        speed_kmh = msg.get("speed", None)
        power_w = msg.get("power", None)
        current_a = msg.get("current", None)
        voltage_v = msg.get("voltage", None)

        if lat is None or lon is None or speed_kmh is None:
            print(f"[DEBUG] Missing required fields: lat={lat}, lon={lon}, speed={speed_kmh}")  # TEMP DEBUG
            return None

        lat = float(lat); lon = float(lon)
        speed_kmh = float(speed_kmh)
        
        # Sanity filter for speed
        speed_min = float(self.cfg.get("SPEED_MIN_KMH", 0.0))
        speed_max = float(self.cfg.get("SPEED_MAX_KMH", 200.0))
        if speed_kmh < speed_min or speed_kmh > speed_max:
            return None  # Invalid speed reading
        
        speed_mps = speed_kmh / 3.6
        
        # Extract and validate voltage/current
        voltage_v = float(voltage_v) if voltage_v is not None else None
        current_a = float(current_a) if current_a is not None else None
        
        # Sanity filters for voltage and current
        if voltage_v is not None:
            v_min = float(self.cfg.get("VOLTAGE_MIN_V", 0.0))
            v_max = float(self.cfg.get("VOLTAGE_MAX_V", 500.0))
            if voltage_v < v_min or voltage_v > v_max:
                voltage_v = None  # Invalid, will use fallback
        
        if current_a is not None:
            i_min = float(self.cfg.get("CURRENT_MIN_A", -100.0))
            i_max = float(self.cfg.get("CURRENT_MAX_A", 200.0))
            if current_a < i_min or current_a > i_max:
                current_a = None  # Invalid, will use fallback
        
        # Compute power: prefer provided, fallback to V*I, else None
        if power_w is not None:
            power_w = float(power_w)
            # Sanity filter for power
            p_min = float(self.cfg.get("POWER_MIN_W", -1000.0))
            p_max = float(self.cfg.get("POWER_MAX_W", 5000.0))
            if power_w < p_min or power_w > p_max:
                power_w = None  # Invalid, try fallback
        
        # Fallback: compute power from voltage * current
        if power_w is None and voltage_v is not None and current_a is not None:
            power_w = voltage_v * abs(current_a)  # Use absolute current for power calculation
        
        if power_w is None:
            return None  # Cannot proceed without power
        
        # Final sanity check on computed/validated power
        p_min = float(self.cfg.get("POWER_MIN_W", -1000.0))
        p_max = float(self.cfg.get("POWER_MAX_W", 5000.0))
        if power_w < p_min or power_w > p_max:
            return None  # Still invalid after fallback

        # -------- 2) init GPS reference --------
        if self.lat0 is None:
            self.lat0, self.lon0 = lat, lon

        x_m, y_m = gps_to_local_xy(lat, lon, self.lat0, self.lon0)
        s_m, d_m = project_to_polyline(x_m, y_m, self.track)

        # -------- 3) buffer --------
        sample = {
            "ts": ts,
            "lat": lat, "lon": lon,
            "x_m": x_m, "y_m": y_m,
            "s_m": s_m, "d_m": d_m,
            "speed_mps": speed_mps,
            "power_w": power_w,
            "current_a": current_a,
        }
        self.buf.append(sample)

        # drop old
        horizon = float(self.cfg["BUFFER_SECONDS"])
        while self.buf and (ts - self.buf[0]["ts"]) > horizon:
            self.buf.popleft()

        if len(self.buf) < int(self.cfg["MIN_SAMPLES_FOR_CUE"]):
            print(f"[DEBUG] Buffer too small: {len(self.buf)} < {self.cfg['MIN_SAMPLES_FOR_CUE']}")  # TEMP DEBUG
            return None

        # -------- 4) light smoothing (rolling median) --------
        win = int(self.cfg["SMOOTH_WIN"])
        recent = list(self.buf)[-win:]
        sm_speed = float(np.median([r["speed_mps"] for r in recent]))
        sm_power = float(np.median([r["power_w"] for r in recent]))

        # -------- 5) zone assignment with hysteresis --------
        zone_type, zone_id = assign_zone_id(
            s_now=s_m,
            stop_lines_s=self.stop_lines_s,
            turn_segs=self.turn_segs,
            L=self.L,
            stop_approach_m=float(self.cfg["STOP_APPROACH_M"]),
        )
        
        # Zone hysteresis: avoid flickering near boundaries
        hysteresis_m = float(self.cfg.get("ZONE_HYSTERESIS_M", 5.0))
        if self.last_zone_id is not None and self.last_zone_id != zone_id and self.last_zone_s is not None:
            # Check if we're still within hysteresis distance of previous zone
            dist_from_last_change = abs(s_m - self.last_zone_s)
            if dist_from_last_change < hysteresis_m:
                # Stay in previous zone
                zone_type = self.last_zone_type
                zone_id = self.last_zone_id
        
        # Update zone tracking
        if self.last_zone_id != zone_id:
            self.last_zone_id = zone_id
            self.last_zone_type = zone_type
            self.last_zone_s = s_m

        # -------- 6) lookup zone optimal --------
        if zone_id not in self.zone_memory.index:
            print(f"[DEBUG] Zone {zone_id} not found in zone_memory. Available zones: {list(self.zone_memory.index)}")  # TEMP DEBUG
            return None

        ref = self.zone_memory.loc[zone_id]
        conf = float(ref.get("confidence", 1.0))
        if conf < float(self.cfg["CONFIDENCE_MIN"]):
            return None

        opt_speed = float(ref["opt_speed_mps"])  # Already in m/s
        # opt_power_w in zone_memory is stored in micro-watts (µW), convert to watts
        opt_power = float(ref["opt_power_w"]) / 1e6
        opt_state = str(ref.get("opt_state", "UNKNOWN"))

        # -------- 7) generate cues by comparing real-time telemetry to optimal (INDEPENDENT) --------
        speed_margin_pct = float(self.cfg["SPEED_MARGIN_PCT"])
        power_margin_w = float(self.cfg["POWER_MARGIN_W"])
        
        # Generate cues based on deviation from optimal (this is independent of state)
        cues: List[Tuple[str, str]] = []
        
        # Check if speed is too high compared to optimal
        speed_ok = sm_speed <= opt_speed * (1.0 + speed_margin_pct)
        if not speed_ok:
            cues.append(("SPEED_HIGH", f"{zone_id}: Too fast → Coast / reduce throttle"))

        # Check if power is too high compared to optimal
        power_ok = sm_power <= opt_power + power_margin_w
        if not power_ok:
            if zone_type == "TURN":
                cues.append(("TURN_POWER_SPIKE", f"{zone_id}: Power spike in turn → Smooth throttle"))
            elif zone_type == "STOP_APPROACH":
                cues.append(("STOP_APPROACH_POWER", f"{zone_id}: Stop ahead → Coast earlier, keep power low"))
            else:
                cues.append(("POWER_HIGH", f"{zone_id}: Power too high → Reduce throttle"))

        # -------- 8) evaluate state (green/red) separately - how close is behavior to optimal --------
        # State evaluation: green if close to optimal, red if not
        base_state = "green" if (speed_ok and power_ok) else "red"
        
        # Track if driver is responding to cues (improving behavior)
        is_responding = False
        if zone_id in self.last_cue_values and zone_id in self.last_cue_state:
            last_speed, last_power = self.last_cue_values[zone_id]
            last_state = self.last_cue_state[zone_id]
            
            # If was red and now green, driver is responding to cues
            if last_state == "red" and base_state == "green":
                is_responding = True
            # If was red and still red, check if values improved (moving toward optimal)
            elif last_state == "red" and base_state == "red":
                # Check if speed improved (decreased toward optimal)
                speed_improved = (sm_speed < last_speed and sm_speed > opt_speed) or (sm_speed <= opt_speed and last_speed > opt_speed)
                # Check if power improved (decreased toward optimal)
                power_improved = (sm_power < last_power and sm_power > opt_power) or (sm_power <= opt_power and last_power > opt_power)
                is_responding = speed_improved or power_improved
        
        # Final state: green if optimal OR responding to cues, red if suboptimal and not responding
        driving_state = "green" if (base_state == "green" or is_responding) else "red"
        
        # Update tracking
        self.last_cue_state[zone_id] = driving_state
        self.last_cue_values[zone_id] = (sm_speed, sm_power)
        
        # -------- 9) only skip if no cues generated AND already driving optimally --------
        # If no cues are generated and driving is already optimal, don't publish
        if not cues and driving_state == "green" and base_state == "green" and not is_responding:
            return None

        # -------- 9) debounce cues (zone + type cooldown) --------
        if not cues:
            return None

        cue_key, cue_text = cues[0]
        now = time.time()
        
        # Check global cue key cooldown
        min_dt = float(self.cfg.get("MIN_SECONDS_BETWEEN_SAME_CUE", 2.0))
        last = self.last_cue_time.get(cue_key, 0.0)
        if (now - last) < min_dt:
            return None
        
        # Check zone cooldown
        zone_cooldown = float(self.cfg.get("CUE_COOLDOWN_BY_ZONE", 3.0))
        last_zone_cue = self.last_cue_by_zone.get(zone_id, 0.0)
        if (now - last_zone_cue) < zone_cooldown:
            return None
        
        # Check cue type cooldown (extract type from cue_key, e.g., "SPEED_HIGH" -> "SPEED")
        cue_type = cue_key.split("_")[0] if "_" in cue_key else cue_key
        type_cooldown = float(self.cfg.get("CUE_COOLDOWN_BY_TYPE", 2.0))
        last_type_cue = self.last_cue_by_type.get(cue_type, 0.0)
        if (now - last_type_cue) < type_cooldown:
            return None
        
        # All checks passed, update timestamps
        self.last_cue_time[cue_key] = now
        self.last_cue_by_zone[zone_id] = now
        self.last_cue_by_type[cue_type] = now

        # -------- 10) return structured cue payload with state --------
        # Compute reason/explanation
        reason_parts = []
        speed_diff_pct = ((sm_speed - opt_speed) / opt_speed * 100) if opt_speed > 0 else 0
        power_diff_w = sm_power - opt_power
        
        if cue_key == "SPEED_HIGH":
            reason_parts.append(f"Speed {speed_diff_pct:.1f}% above optimal")
        elif "POWER" in cue_key:
            reason_parts.append(f"Power {power_diff_w:.1f}W above optimal")
        elif cue_key == "DRIVING_OPTIMAL":
            reason_parts.append("Driving within optimal parameters")
        
        reason = "; ".join(reason_parts) if reason_parts else f"Zone {zone_id} threshold exceeded"
        
        return {
            "ts": now,
            "zone_id": zone_id,
            "zone_type": zone_type,
            "confidence": conf,
            "opt_state": opt_state,
            # Driving state: green (optimal/responding) or red (needs improvement)
            "state": driving_state,
            "is_responding": is_responding,  # True if driver is improving/responding to cues
            # Current vs optimal comparison
            "current_speed_kmh": sm_speed * 3.6,
            "optimal_speed_kmh": opt_speed * 3.6,
            "speed_diff_pct": speed_diff_pct,
            "current_power_w": sm_power,
            "optimal_power_w": opt_power,
            "power_diff_w": power_diff_w,
            # Cue information
            "cue_key": cue_key,
            "cue_text": cue_text,
            "reason": reason,
            # Legacy fields for backward compatibility
            "opt_speed_kmh": opt_speed * 3.6,
            "opt_power_w": opt_power,
            "speed_kmh": sm_speed * 3.6,
            "power_w": sm_power,
        }
