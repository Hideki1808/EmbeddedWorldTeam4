"""Strict configuration loading, with paths relative to the config file."""

import json
import math
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    pass


def _object(value, name, keys, optional=()):
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be an object")
    unknown = value.keys() - set(keys) - set(optional)
    missing = set(keys) - value.keys()
    if unknown or missing:
        raise ConfigError(f"{name}: unknown keys {sorted(unknown)}, missing keys {sorted(missing)}")
    return value


def _number(value, name, minimum, maximum, integer=False):
    valid_type = type(value) is int if integer else type(value) in (int, float)
    if not valid_type or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be {'an integer' if integer else 'a number'} in [{minimum}, {maximum}]")


def _boolean(value, name):
    if type(value) is not bool:
        raise ConfigError(f"{name} must be true or false")


@dataclass(frozen=True)
class Config:
    path: Path
    data: dict

    @property
    def backend(self):
        return self.data["backend"]

    @property
    def runtime(self):
        return self.data.get("runtime", "app_lab")

    @property
    def integrated_model_path(self):
        model = self.data.get("integrated", {}).get("model_path", "models/hand-gestures.eim")
        return (self.path.parent / model).resolve()

    @property
    def model_path(self):
        return (self.path.parent / self.data["mediapipe"]["model_path"]).resolve()


def load_config(path):
    path = Path(path).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"Cannot read config {path}: {exc}") from exc
    _object(data, "config", ["backend", "camera", "recognition", "mediapipe", "led", "buzzer"], ["runtime", "integrated"])
    if data["backend"] not in ("integrated", "mediapipe"):
        raise ConfigError('backend must be "integrated" or "mediapipe"')
    if data.get("runtime", "app_lab") not in ("app_lab", "standalone"):
        raise ConfigError('runtime must be "app_lab" or "standalone"')
    if "integrated" in data:
        integrated = _object(data["integrated"], "integrated", ["model_path"])
        if not isinstance(integrated["model_path"], str) or not integrated["model_path"].strip():
            raise ConfigError("integrated.model_path must be a nonempty path")

    camera = _object(data["camera"], "camera", ["device", "width", "height", "fps", "mirror", "timeout_seconds"])
    device = camera["device"]
    if not ((type(device) is int and device >= 0) or (isinstance(device, str) and device.startswith(("/dev/video", "/dev/v4l/")))):
        raise ConfigError("camera.device must be a nonnegative integer or a Linux /dev/video or /dev/v4l/ device path")
    for key in ("width", "height"):
        _number(camera[key], f"camera.{key}", 16, 4096, integer=True)
    _number(camera["fps"], "camera.fps", 1, 60, integer=True)
    _number(camera["timeout_seconds"], "camera.timeout_seconds", 0.1, 60)
    _boolean(camera["mirror"], "camera.mirror")

    recognition = _object(data["recognition"], "recognition", ["min_confidence", "stable_frames", "repeat_seconds"])
    _number(recognition["min_confidence"], "recognition.min_confidence", 0, 1)
    _number(recognition["stable_frames"], "recognition.stable_frames", 1, 100, integer=True)
    _number(recognition["repeat_seconds"], "recognition.repeat_seconds", 0.1, 3600)

    mp = _object(data["mediapipe"], "mediapipe", ["model_path", "num_hands", "min_hand_detection_confidence", "min_hand_presence_confidence", "min_tracking_confidence"])
    if not isinstance(mp["model_path"], str) or not mp["model_path"].strip():
        raise ConfigError("mediapipe.model_path must be a nonempty path")
    _number(mp["num_hands"], "mediapipe.num_hands", 1, 4, integer=True)
    for key in ("min_hand_detection_confidence", "min_hand_presence_confidence", "min_tracking_confidence"):
        _number(mp[key], f"mediapipe.{key}", 0, 1)

    led = _object(data["led"], "led", ["enabled", "gesture_colors", "heartbeat_seconds"])
    _boolean(led["enabled"], "led.enabled")
    colors = led["gesture_colors"]
    if not isinstance(colors, dict) or not all(
        isinstance(gesture, str) and gesture and gesture != "None" and color in ("red", "green")
        for gesture, color in colors.items()
    ):
        raise ConfigError('led.gesture_colors must map gesture names to "red" or "green"')
    _number(led["heartbeat_seconds"], "led.heartbeat_seconds", 0.1, 0.75)
    buzzer = _object(data["buzzer"], "buzzer", ["enabled"])
    _boolean(buzzer["enabled"], "buzzer.enabled")
    return Config(path, data)
