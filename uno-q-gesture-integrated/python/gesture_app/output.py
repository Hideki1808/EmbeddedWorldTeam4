"""Terminal logs, JSON events, RGB LEDs, and Modulino buzzer feedback."""

import json
import logging
import time

LOG = logging.getLogger(__name__)
COLOR_CODES = {"off": 0, "red": 1, "green": 2}


class Outputs:
    def __init__(self, config, bridge=None, emit=print, linux_leds=None):
        self._backend = config.backend
        self._owns_bridge = config.runtime == "standalone"
        self._led = config.data["led"]
        self._buzzer = config.data["buzzer"]["enabled"]
        self._linux_leds = linux_leds
        self._repeat = config.data["recognition"]["repeat_seconds"]
        self._bridge, self._emit = bridge, emit
        self._last_key = None
        self._last_event = float("-inf")
        self._last_led_time = float("-inf")
        self._last_led_state = None
        self._bridge_warning_time = float("-inf")
        self._linux_warning_time = float("-inf")
        self._hardware_status = None

    def update(self, detection, now=None):
        now = time.monotonic() if now is None else now
        key = (detection.gesture, detection.hand) if detection else None
        color = self._led["gesture_colors"].get(detection.gesture, "off") if detection else "off"
        led_color = color if self._led["enabled"] else "off"
        if key != self._last_key or (detection and now - self._last_event >= self._repeat):
            event = {"backend": self._backend, "timestamp": time.time(), "gesture": "None", "confidence": 0.0, "hand": None, "raw_label": None}
            if detection:
                event.update(detection.to_dict())
            event["led_color"] = led_color
            self._emit(json.dumps(event), flush=True)
            LOG.info("Gesture=%s confidence=%.0f%% hand=%s LEDs=%s",
                     event["gesture"], event["confidence"] * 100, event["hand"] or "unknown", led_color)
            self._last_event = now
        self._last_key = key
        changed = color != self._last_led_state
        if changed or now - self._last_led_time >= self._led["heartbeat_seconds"]:
            if self._bridge is not None:
                try:
                    status = self._bridge.call("set_gesture_feedback", COLOR_CODES[color], self._led["enabled"], self._buzzer, timeout=0.5)
                    if type(status) is int and status != self._hardware_status:
                        LOG.info("Modulino detection at startup: Pixels=%s Buzzer=%s", "found" if status & 1 else "missing", "found" if status & 2 else "missing")
                        if self._led["enabled"] and not status & 1:
                            LOG.warning("Modulino Pixels missing: check its Qwiic cable and restart the sketch")
                        if self._buzzer and not status & 2:
                            LOG.warning("Modulino Buzzer missing: check its Qwiic cable and restart the sketch")
                        self._hardware_status = status
                    if changed and color != "off" and self._buzzer:
                        LOG.info("Buzzer requested: %s short beep(s)", 2 if color == "red" else 1)
                except Exception as exc:
                    if now - self._bridge_warning_time >= 5:
                        LOG.warning("Feedback Bridge call failed (recognition continues): %s", exc)
                        self._bridge_warning_time = now
            if self._linux_leds is not None:
                try:
                    self._linux_leds.set_color(led_color)
                except OSError as exc:
                    if now - self._linux_warning_time >= 5:
                        LOG.warning("Linux RGB LED update failed: %s", exc)
                        self._linux_warning_time = now
            self._last_led_state = color
            self._last_led_time = now

    def close(self):
        if self._bridge is not None:
            try:
                self._bridge.call("set_gesture_feedback", 0, False, False, timeout=0.5)
            except Exception:
                LOG.warning("Could not clear MCU LEDs/Pixels/buzzer through Bridge; the sketch watchdog will clear them")
            finally:
                if self._owns_bridge:
                    self._bridge.disconnect()


def connect_bridge(config):
    if not config.data["led"]["enabled"] and not config.data["buzzer"]["enabled"]:
        return None
    if config.runtime == "standalone":
        try:
            from arduino.router_bridge import Bridge as RouterBridge
        except ImportError as exc:
            raise RuntimeError("Install arduino-ide/requirements.txt for the standalone Arduino Router Bridge") from exc
        bridge = RouterBridge("unix:///var/run/arduino-router.sock")
        try:
            if not bridge.connect(timeout=5):
                raise RuntimeError("Cannot connect to arduino-router. Run this program on the UNO Q and check: systemctl status arduino-router")
            # Verify the matching MCU sketch before starting the camera.
            bridge.call("set_gesture_feedback", 0, False, False, timeout=1)
            return bridge
        except BaseException:
            bridge.disconnect()
            raise
    try:
        from arduino.app_utils import Bridge
        return Bridge
    except ImportError as exc:
        raise RuntimeError("Feedback requires Arduino App Lab and the supplied MCU sketch. For a desktop MediaPipe run, set led.enabled and buzzer.enabled to false.") from exc
