# Shell Coaching AI

Real-time coaching system for Shell Eco-marathon vehicles using MQTT telemetry and optimal driving data.

## Overview

This system analyzes real-time vehicle telemetry, compares it against optimal driving patterns, and provides coaching cues to help drivers improve efficiency and performance.

## Features

- **Real-time telemetry processing** via MQTT
- **Zone-based coaching** (straights, turns, stop approaches)
- **State evaluation** (green/red) based on optimal driving patterns
- **Intelligent cue generation** with debouncing and hysteresis
- **Session gating** via MQTT control topic
- **Sanity filters** for voltage/current/power/speed with fallback calculations

## Quick Start

### Prerequisites

- Docker
- MQTT broker access
- Python 3.8+

### Setup

1. Clone the repository:
```bash
git clone https://github.com/taynamghz/ShellCoachingAI.git
cd ShellCoachingAI
```

2. Create `.env` file from template:
```bash
cp env.template .env
# Edit .env with your MQTT credentials
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run locally:
```bash
python -m src.main
```

## Docker Deployment

### The Golden Rule 🔁

**🔁 You only rebuild Docker when code or dependencies change**

**🔄 You only restart Docker when data or config changes**

### Deployment Workflows

#### ✅ 1) Code Changes (Python files, requirements.txt)

**Examples:**
- Logic in `coach.py`
- Thresholds
- MQTT logic
- Import fixes
- Changes to `requirements.txt`

**👉 You must rebuild the image:**

```bash
cd ~/apps/ShellCoachingAI
git pull
docker rm -f shell-coach 2>/dev/null || true
docker build -t shell-coach:latest .
docker run -d --name shell-coach --restart unless-stopped --env-file .env shell-coach:latest
```

**Why:** Python code is baked into the Docker image.

#### ⚡ 2) Artifacts Only (artifacts/*.json, .parquet)

**Examples:**
- New optimal racing line
- New track
- Updated zone memory

**👉 NO rebuild needed**

**Just restart the container:**

```bash
cd ~/apps/ShellCoachingAI
git pull
docker restart shell-coach
```

**Why:** Artifacts are runtime data, not code.

#### ⚙️ 3) Config Changes (.env file)

**Examples:**
- MQTT credentials
- Topics
- Flags

**👉 NO rebuild needed**

```bash
docker restart shell-coach
```

### 🔥 Best Practice Scripts

Add these two scripts to your repo for faster deployments:

#### `deploy_full.sh` (code changes)

```bash
#!/usr/bin/env bash

set -e

git pull

docker rm -f shell-coach 2>/dev/null || true

docker build -t shell-coach:latest .

docker run -d --name shell-coach --restart unless-stopped --env-file .env shell-coach:latest
```

#### `deploy_artifacts.sh` (artifacts only)

```bash
#!/usr/bin/env bash

set -e

git pull

docker restart shell-coach
```

### Quick Reference

| What Changed | Command |
|-------------|---------|
| Code / ML logic | `bash deploy_full.sh` |
| Artifacts only | `bash deploy_artifacts.sh` |
| MQTT creds | `docker restart shell-coach` |

## Project Structure

```
ShellOffTrack/
├── src/
│   ├── main.py          # Entry point
│   ├── coach.py         # Core coaching logic
│   ├── config.py        # Configuration
│   ├── mqtt_client.py   # MQTT client
│   ├── zones.py         # Zone assignment
│   ├── track_map.py     # Track mapping
│   └── artifacts.py     # Artifact loading
├── artifacts/           # Track data, zones, optimal patterns
├── requirements.txt     # Python dependencies
├── env.template         # Environment variables template
└── README.md           # This file
```

## MQTT Topics

- **Telemetry**: `car/telemetry` (incoming)
- **Cues**: `car/cues` (outgoing)
- **Status**: `coach/status` (heartbeat)
- **Control**: `coach/control` (session gating)

## Export Pipeline

### Generating zone_memory.parquet

The coaching system requires `artifacts/zone_memory.parquet` to function. This file contains optimal driving parameters for each zone.

**Generate the file:**

```bash
python export_zone_memory.py
```

This script:
- Reads track artifacts (`track.json`, `stop_lines.json`, `turn_zones.json`)
- Generates optimal values for all zones (STRAIGHT, TURN_*, STOP_*_APPROACH)
- Creates `artifacts/zone_memory.parquet`

**Options:**
```bash
python export_zone_memory.py --artifacts-dir artifacts --output artifacts/zone_memory.parquet
```

**Note:** The default values in the export script are placeholders. For production, you should:
1. Analyze optimal driving data from your track
2. Update the `generate_zone_memory()` function with real optimal values
3. Or modify the script to load optimal values from your analysis pipeline

## Configuration

Configuration is managed through:
- `src/config.py` - Main configuration dictionary
- `.env` file - MQTT credentials and sensitive data

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

