# src/replay_offline.py
import time
import pandas as pd

from .config import CONFIG
from .artifacts import load_artifacts
from .coach import Coach

# ---------- EDIT THIS MAPPING ONCE ----------
# Map your CSV column names -> fields Coach expects
CSV_MAP = {
    "timestamp": "obc_timestamp",   # seconds (unix)
    "latitude": "gps_latitude",
    "longitude": "gps_longitude",
    "speed": "gps_speed",           # km/h
    "voltage": "jm3_voltage",       # microvolts (will be converted)
    "current": "jm3_current",       # A
}

def parse_timestamp(v):
    """
    Accepts:
      - unix seconds
      - unix milliseconds
      - ISO strings
    Returns float seconds since epoch.
    """
    if pd.isna(v):
        return None

    # numeric?
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        v = float(v)
        # heuristic: ms if too large
        if v > 1e12:
            return v / 1000.0
        return v

    # try parse ISO-like
    try:
        dt = pd.to_datetime(v, utc=True)
        return dt.value / 1e9  # ns -> s
    except Exception:
        return None

def row_to_msg(row):
    msg = {}
    ts = parse_timestamp(row.get(CSV_MAP["timestamp"]))
    if ts is None:
        ts = time.time()

    msg["timestamp"] = ts
    msg["latitude"] = float(row.get(CSV_MAP["latitude"])) if pd.notna(row.get(CSV_MAP["latitude"])) else None
    msg["longitude"] = float(row.get(CSV_MAP["longitude"])) if pd.notna(row.get(CSV_MAP["longitude"])) else None
    msg["speed"] = float(row.get(CSV_MAP["speed"])) if pd.notna(row.get(CSV_MAP["speed"])) else None
    
    # Calculate power from voltage * current
    # Voltage is in millivolts (mV), current is in amperes (A)
    voltage_col = CSV_MAP.get("voltage")
    current_col = CSV_MAP.get("current")
    if voltage_col and current_col and pd.notna(row.get(voltage_col)) and pd.notna(row.get(current_col)):
        voltage_mv = float(row.get(voltage_col))  # millivolts
        current_a = float(row.get(current_col))  # amperes
        # Convert mV to V, then calculate power: P = V * I
        voltage_v = voltage_mv / 1000.0  # Convert mV to V
        msg["power"] = voltage_v * abs(current_a)  # Power in watts (use absolute value for current since negative means regen)
        msg["current"] = current_a
    else:
        msg["power"] = None
        msg["current"] = None

    return msg

def replay_csv(csv_path: str, speedup: float = 10.0, max_rows: int | None = None):
    track, stop_lines_s, turn_segs, zone_memory = load_artifacts(CONFIG["ARTIFACTS_DIR"])
    coach = Coach(CONFIG, track, stop_lines_s, turn_segs, zone_memory)

    df = pd.read_csv(csv_path)
    if max_rows:
        df = df.iloc[:max_rows].copy()

    # Build messages
    msgs = []
    for _, r in df.iterrows():
        try:
            msgs.append(row_to_msg(r))
        except Exception:
            continue

    if len(msgs) < 5:
        raise RuntimeError("Not enough valid rows after mapping. Check CSV_MAP and columns.")

    # sort by timestamp
    msgs.sort(key=lambda m: m["timestamp"])

    print(f"[REPLAY OFFLINE] Loaded {len(msgs)} msgs from {csv_path}")
    print(f"[REPLAY OFFLINE] speedup={speedup}x (bigger = faster replay)\n")

    t0_wall = time.time()
    t0_data = msgs[0]["timestamp"]

    cues_count = 0

    for i, m in enumerate(msgs):
        # compute when to emit this message
        dt_data = m["timestamp"] - t0_data
        target_wall = t0_wall + (dt_data / speedup)

        # sleep until it's time
        now = time.time()
        if target_wall > now:
            time.sleep(target_wall - now)

        cue = coach.ingest(m)
        if cue:
            cues_count += 1
            print(f"[CUE] {cue['cue_text']} | zone={cue['zone_id']} conf={cue['confidence']:.2f} "
                  f"cur_speed={cue['speed_kmh']:.1f} opt={cue['opt_speed_kmh']:.1f} "
                  f"cur_power={cue['power_w']:.0f} opt={cue['opt_power_w']:.0f}")

        # occasional progress
        if i % 200 == 0:
            print(f"... replayed {i}/{len(msgs)}")

    print(f"\n[REPLAY OFFLINE] Done. Total cues emitted: {cues_count}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Replay CSV telemetry data offline")
    parser.add_argument("--csv", required=True, help="Path to CSV file")
    parser.add_argument("--speedup", type=float, default=1.0, help="Speedup factor (e.g., 20 for 20x speed)")
    args = parser.parse_args()
    
    replay_csv(args.csv, speedup=args.speedup, max_rows=None)


if __name__ == "__main__":
    main()
