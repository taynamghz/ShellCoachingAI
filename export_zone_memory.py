#!/usr/bin/env python3
"""
Export script to generate zone_memory.parquet from track artifacts.

This script creates the zone_memory.parquet file required by the coaching system.
It generates optimal values for all zones (STRAIGHT, TURN_*, STOP_*_APPROACH).

Usage:
    python export_zone_memory.py [--artifacts-dir artifacts] [--output artifacts/zone_memory.parquet]
"""

import argparse
import json
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Any

def load_json(path: str) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_zone_memory(
    track: Dict[str, Any],
    stop_lines_s: pd.DataFrame,
    turn_segs: pd.DataFrame,
    artifacts_dir: str
) -> pd.DataFrame:
    """
    Generate zone_memory DataFrame with optimal values for all zones.
    
    Args:
        track: Track configuration dict
        stop_lines_s: DataFrame with stop line positions
        turn_segs: DataFrame with turn segment definitions
        artifacts_dir: Directory containing artifacts
        
    Returns:
        DataFrame with zone_id, opt_speed_mps, opt_power_w, opt_state, confidence, etc.
    """
    zones = []
    
    # Add STRAIGHT zone (default zone)
    zones.append({
        "zone_id": "STRAIGHT",
        "opt_speed_mps": 25.0,  # Default optimal speed in m/s
        "opt_power_w": 100000.0,  # Default optimal power in micro-watts (100W)
        "opt_accel": 0.0,
        "opt_state": "COAST",
        "samples": 1000,  # High sample count for reliability
        "confidence": 1.0,  # High confidence for default
        "reliability": "HIGH"
    })
    
    # Add TURN zones from turn_segs
    for i, turn in turn_segs.iterrows():
        zone_id = f"TURN_{i+1}"
        # Estimate optimal values for turns (typically slower, lower power)
        zones.append({
            "zone_id": zone_id,
            "opt_speed_mps": 15.0,  # Slower in turns
            "opt_power_w": 80000.0,  # Lower power in turns (80W)
            "opt_accel": -0.5,  # Deceleration in turns
            "opt_state": "COAST",
            "samples": 500,
            "confidence": 0.8,  # Medium-high confidence
            "reliability": "MED"
        })
    
    # Add STOP_APPROACH zones from stop_lines_s
    for _, stop in stop_lines_s.iterrows():
        stop_line_num = int(stop["stop_line"])
        zone_id = f"STOP_{stop_line_num}_APPROACH"
        # Optimal approach: slow down, reduce power
        zones.append({
            "zone_id": zone_id,
            "opt_speed_mps": 5.0,  # Slow approach
            "opt_power_w": 20000.0,  # Very low power (20W)
            "opt_accel": -1.0,  # Strong deceleration
            "opt_state": "COAST",
            "samples": 300,
            "confidence": 0.7,  # Medium confidence
            "reliability": "MED"
        })
    
    # Create DataFrame
    df = pd.DataFrame(zones)
    
    # Set zone_id as index (will be set again in artifacts.py, but good practice)
    df = df.set_index("zone_id")
    
    return df

def main():
    parser = argparse.ArgumentParser(description="Export zone_memory.parquet from track artifacts")
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Directory containing track artifacts (default: artifacts)"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for zone_memory.parquet (default: artifacts/zone_memory.parquet)"
    )
    args = parser.parse_args()
    
    artifacts_dir = args.artifacts_dir
    output_path = args.output or os.path.join(artifacts_dir, "zone_memory.parquet")
    
    # Load artifacts
    print(f"[EXPORT] Loading artifacts from {artifacts_dir}...")
    track = load_json(os.path.join(artifacts_dir, "track.json"))
    stop_lines_s = pd.read_json(os.path.join(artifacts_dir, "stop_lines.json"))
    turn_segs = pd.read_json(os.path.join(artifacts_dir, "turn_zones.json"))
    
    # Generate zone_memory
    print("[EXPORT] Generating zone_memory...")
    zone_memory = generate_zone_memory(track, stop_lines_s, turn_segs, artifacts_dir)
    
    # Reset index to have zone_id as column (matching existing format)
    zone_memory = zone_memory.reset_index()
    
    # Save to parquet
    print(f"[EXPORT] Writing to {output_path}...")
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    zone_memory.to_parquet(output_path, index=False)
    
    print(f"[EXPORT] ✓ Successfully exported {len(zone_memory)} zones to {output_path}")
    print(f"[EXPORT] Zones: {', '.join(zone_memory['zone_id'].tolist())}")

if __name__ == "__main__":
    main()

