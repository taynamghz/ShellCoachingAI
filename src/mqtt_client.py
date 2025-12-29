# src/mqtt_client.py
import json
import ssl
import time
from typing import Callable, Optional, Dict, Any

import paho.mqtt.client as mqtt

class MqttClient:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.username_pw_set(cfg["MQTT_USERNAME"], cfg["MQTT_PASSWORD"])

        if cfg.get("MQTT_TLS", True):
            context = ssl.create_default_context()
            self.client.tls_set_context(context)

        self._on_msg_cb: Optional[Callable[[Dict[str, Any]], None]] = None
        self._on_control_cb: Optional[Callable[[Dict[str, Any]], None]] = None
        self.session_enabled = True  # default enabled

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def set_message_handler(self, cb: Callable[[Dict[str, Any]], None]):
        self._on_msg_cb = cb

    def set_control_handler(self, cb: Callable[[Dict[str, Any]], None]):
        self._on_control_cb = cb

    def is_session_enabled(self) -> bool:
        return self.session_enabled

    def connect(self):
        self.client.connect(self.cfg["MQTT_HOST"], int(self.cfg["MQTT_PORT"]), keepalive=30)

    def loop_forever(self):
        self.client.loop_forever(retry_first_connection=True)

    def publish_json(self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False):
        self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def heartbeat(self, text: str = "alive"):
        self.publish_json(self.cfg["STATUS_TOPIC"], {"ts": time.time(), "status": text})

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("[MQTT] Connected OK")
            client.subscribe(self.cfg["TELEMETRY_TOPIC"], qos=0)
            client.subscribe(self.cfg["CONTROL_TOPIC"], qos=0)
            self.heartbeat("connected")
        else:
            print("[MQTT] Connect failed:", reason_code)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return

        # CONTROL
        if msg.topic == self.cfg["CONTROL_TOPIC"]:
            if self._on_control_cb:
                self._on_control_cb(payload)
            # Accept BOTH payload styles:
            # 1) {"action":"enable"/"disable"}
            # 2) {"enabled": true/false}
            enabled = payload.get("enabled", None)

            action = str(payload.get("action", "")).lower().strip()
            if action == "enable":
                enabled = True
            elif action == "disable":
                enabled = False

            if enabled is not None:
                self.session_enabled = bool(enabled)
                print(f"[MQTT] Session enabled={self.session_enabled} via control topic")

            return

        # TELEMETRY
        if msg.topic == self.cfg["TELEMETRY_TOPIC"]:
            print("[TEL] got telemetry", payload)   # TEMP DEBUG
            if self.session_enabled and self._on_msg_cb:
                self._on_msg_cb(payload)
