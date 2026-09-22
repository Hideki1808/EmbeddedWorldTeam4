"""App Lab entry point; also supports standalone MediaPipe on Linux/Windows."""

import argparse
from contextlib import ExitStack
import logging
from pathlib import Path
import signal
import sys
import time

from gesture_app.config import ConfigError, load_config

LOG = logging.getLogger("gesture-app")
DEFAULT_CONFIG = Path(__file__).with_name("config.json")


def _stop_on_signal(signum, frame):
    raise KeyboardInterrupt


def run(config, camera_test=False):
    from gesture_app.camera import Camera

    # Raise out of blocking inference so cleanup also runs on App Lab Stop.
    previous = signal.signal(signal.SIGTERM, _stop_on_signal)
    try:
        with ExitStack() as stack:
            if not camera_test:
                from gesture_app.backends import create_backend
                from gesture_app.output import Outputs, connect_bridge
                from gesture_app.linux_leds import connect_linux_leds
                from gesture_app.recognition import StableGesture

                backend = create_backend(config)
                stack.callback(backend.close)
                linux_leds = connect_linux_leds(config)
                if linux_leds is not None:
                    stack.callback(linux_leds.close)
                outputs = Outputs(config, connect_bridge(config), linux_leds=linux_leds)
                stack.callback(outputs.close)
                filtering = StableGesture(config.data["recognition"]["min_confidence"], config.data["recognition"]["stable_frames"])
            camera = Camera(config.data["camera"])
            stack.callback(camera.close)
            if camera_test:
                frame, _ = camera.read()
                LOG.info("USB camera OK: received %sx%s pixels", frame.shape[1], frame.shape[0])
                return
            LOG.info("Running %s backend; raised palm = red / two beeps, thumbs up = green / one beep. Ctrl+C stops.", config.backend)
            while True:
                started = time.monotonic()
                frame, timestamp_ms = camera.read()
                detections = backend.recognize(frame, timestamp_ms)
                outputs.update(filtering.update(detections))
                time.sleep(max(0, 1 / config.data["camera"]["fps"] - (time.monotonic() - started)))
    finally:
        signal.signal(signal.SIGTERM, previous)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--check-config", action="store_true", help="Validate JSON without camera, Arduino, or MediaPipe imports")
    parser.add_argument("--camera-test", action="store_true", help="Capture one frame without starting inference or the LED")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO", help="Terminal logging verbosity (default INFO)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S", stream=sys.stderr)
    try:
        config = load_config(args.config)
        if args.check_config:
            LOG.info("Config OK: backend=%s, camera=%r, LED=%s", config.backend, config.data["camera"]["device"], config.data["led"]["enabled"])
            return 0
        run(config, args.camera_test)
        return 0
    except KeyboardInterrupt:
        LOG.info("Stopped")
        return 0
    except (ConfigError, RuntimeError, OSError, ImportError, ValueError) as exc:
        LOG.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
