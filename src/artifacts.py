# src/artifacts.py
import json
import os
import pandas as pd
from typing import Dict, Any, Tuple

def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_artifacts(art_dir: str):
    track = load_json(os.path.join(art_dir, "track.json"))
    stop_lines_s = pd.read_json(os.path.join(art_dir, "stop_lines.json"))
    turn_segs = pd.read_json(os.path.join(art_dir, "turn_zones.json"))
    zm_path = os.path.join(art_dir, "zone_memory.parquet")
    if os.path.exists(zm_path):
        zone_memory = pd.read_parquet(zm_path).set_index("zone_id")
    else:
        # Empty fallback so the container can boot
        zone_memory = pd.DataFrame().set_index(pd.Index([], name="zone_id"))
        print(f"[ARTIFACTS] WARNING: missing {zm_path}. Using empty zone_memory.")

    return track, stop_lines_s, turn_segs, zone_memory
