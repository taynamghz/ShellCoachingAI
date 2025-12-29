# src/artifacts.py
import json
import os
import pandas as pd
from typing import Dict, Any, Tuple

def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_artifacts(art_dir: str) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame]:
    track = load_json(os.path.join(art_dir, "track.json"))
    stop_lines_s = pd.read_json(os.path.join(art_dir, "stop_lines.json"))
    turn_segs = pd.read_json(os.path.join(art_dir, "turn_zones.json"))
    zone_memory = pd.read_parquet(os.path.join(art_dir, "zone_memory.parquet"))

    # index zone_memory for quick lookup
    zone_memory = zone_memory.set_index("zone_id")

    return track, stop_lines_s, turn_segs, zone_memory
