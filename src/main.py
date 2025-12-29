# src/main.py
import time
from config import CONFIG
from mqtt_client import MqttClient
from artifacts import load_artifacts
from coach import Coach

def main():
    track, stop_lines_s, turn_segs, zone_memory = load_artifacts(CONFIG["ARTIFACTS_DIR"])

    coach = Coach(CONFIG, track, stop_lines_s, turn_segs, zone_memory)

    mqttc = MqttClient(CONFIG)

    def handle_msg(payload):
        # Only process if session is enabled
        if not mqttc.is_session_enabled():
            return
        cue = coach.ingest(payload)
        if cue is not None:
            mqttc.publish_json(CONFIG["CUES_TOPIC"], cue)
            print("[CUE]", cue["cue_text"])

    mqttc.set_message_handler(handle_msg)
    mqttc.connect()

    # Heartbeat loop in background-ish (simple)
    last_hb = 0.0

    def on_loop():
        nonlocal last_hb
        now = time.time()
        if now - last_hb > 2.0:
            mqttc.heartbeat("alive")
            last_hb = now

    # Use loop_start + manual sleep so we can heartbeat
    mqttc.client.loop_start()
    print("[MAIN] Coaching system running. Waiting for telemetry...")

    try:
        while True:
            on_loop()
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[MAIN] Stopping...")
    finally:
        mqttc.client.loop_stop()
        mqttc.client.disconnect()

