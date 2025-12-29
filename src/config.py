# src/config.py

# =====================
# MQTT BROKER CONFIG
# =====================

MQTT_HOST = "8fac0c92ea0a49b8b56f39536ba2fd78.s1.eu.hivemq.cloud"
MQTT_PORT = 8884
MQTT_TLS  = True

MQTT_USERNAME = "ShellJM"
MQTT_PASSWORD = "psuEcoteam1st"

# =====================
# TOPICS
# =====================

TELEMETRY_TOPIC = "car/telemetry"   # incoming
CUES_TOPIC      = "car/cues"        # outgoing (to dashboard)
STATUS_TOPIC    = "coach/status"    # heartbeat / alive
CONTROL_TOPIC   = "coach/control"   # session gating (enable/disable)

# =====================
# CONFIG DICTIONARY
# =====================

CONFIG = {
    # MQTT
    "MQTT_HOST": MQTT_HOST,
    "MQTT_PORT": MQTT_PORT,
    "MQTT_TLS": MQTT_TLS,
    "MQTT_USERNAME": MQTT_USERNAME,
    "MQTT_PASSWORD": MQTT_PASSWORD,
    "TELEMETRY_TOPIC": TELEMETRY_TOPIC,
    "CUES_TOPIC": CUES_TOPIC,
    "STATUS_TOPIC": STATUS_TOPIC,
    "CONTROL_TOPIC": CONTROL_TOPIC,
    
    # Coaching thresholds
    "POWER_MARGIN_W": 30.0,
    "SPEED_MARGIN": 1.05,
    "CONFIDENCE_MIN": 0.4,
    
    # Buffering / smoothing
    "BUFFER_SECONDS": 20,        # rolling window size
    "SMOOTH_WIN": 7,             # rolling median window (samples)
    "MIN_SAMPLES_FOR_CUE": 10,   # don't cue until buffer has enough

    # Cue thresholds
    "SPEED_MARGIN_PCT": 0.05,    # 5% above optimal triggers cue
    "DECEL_AGGRESSIVE_DELTA": 0.15,

    # Stop coaching distances (meters along track)
    "STOP_APPROACH_M": 80.0,
    "STOP_EXIT_M": 40.0,

    # Turn coaching
    "TURN_POWER_SPIKE_W": 50.0,

    # Rate limiting cues
    "MIN_SECONDS_BETWEEN_SAME_CUE": 2.0,
    "CUE_COOLDOWN_BY_ZONE": 3.0,      # seconds between cues in same zone
    "CUE_COOLDOWN_BY_TYPE": 2.0,      # seconds between same cue type

    # Zone hysteresis (meters)
    "ZONE_HYSTERESIS_M": 5.0,         # avoid flickering near boundaries

    # Sanity filter ranges
    "SPEED_MIN_KMH": 0.0,
    "SPEED_MAX_KMH": 200.0,
    "POWER_MIN_W": -1000.0,           # allow negative for regen
    "POWER_MAX_W": 5000.0,
    "CURRENT_MIN_A": -100.0,          # allow negative for regen
    "CURRENT_MAX_A": 200.0,
    "VOLTAGE_MIN_V": 0.0,
    "VOLTAGE_MAX_V": 500.0,

    # Artifacts path
    "ARTIFACTS_DIR": "artifacts",
}
