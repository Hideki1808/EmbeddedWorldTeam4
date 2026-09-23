"""Backend adapters. Import only the selected inference library."""

import math

from .recognition import Detection

INTEGRATED_LABELS = {
    "five": "Open_Palm",
    "good": "Thumb_Up",
    "neut": "Closed_Fist",
    "peace": "Victory",
}


def _normalized_center(box, image_width, image_height):
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(value) for value in box)
    except (TypeError, ValueError):
        return None
    if image_width <= 0 or image_height <= 0 or x2 <= x1 or y2 <= y1:
        return None
    return (min(1.0, max(0.0, (x1 + x2) / (2 * image_width))),
            min(1.0, max(0.0, (y1 + y2) / (2 * image_height))))


def integrated_results(result, image_width=1, image_height=1):
    # Arduino ObjectDetection returns percentage strings, including values < 1%.
    detections = []
    for item in (result or {}).get("detection", []):
        raw = item["class_name"]
        confidence = float(item["confidence"]) / 100.0
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError(f"Invalid integrated confidence: {item['confidence']!r}")
        if raw not in INTEGRATED_LABELS:
            raise RuntimeError(f"Unexpected label {raw!r}. Select the hand-gestures model in app.yaml.")
        center = _normalized_center(item.get("bounding_box_xyxy"), image_width, image_height)
        detections.append(Detection(INTEGRATED_LABELS[raw], confidence, raw_label=raw, center=center))
    return detections


def mediapipe_results(result):
    detections = []
    for index, categories in enumerate(result.gestures):
        if not categories:
            continue
        top = max(categories, key=lambda category: category.score)
        if not top.category_name or top.category_name == "None":
            continue
        hand = None
        if index < len(result.handedness) and result.handedness[index]:
            hand = result.handedness[index][0].category_name.lower()
        center = None
        if index < len(result.hand_landmarks) and result.hand_landmarks[index]:
            landmarks = result.hand_landmarks[index]
            center = (sum(point.x for point in landmarks) / len(landmarks),
                      sum(point.y for point in landmarks) / len(landmarks))
        detections.append(Detection(top.category_name, float(top.score), hand, top.category_name, center))
    return detections


class IntegratedBackend:
    def __init__(self, config):
        try:
            from arduino.app_bricks.object_detection import ObjectDetection
            import cv2
        except ImportError as exc:
            raise RuntimeError("Integrated mode requires Arduino App Lab on the UNO Q, with the Object Detection brick and hand-gestures model.") from exc
        self._cv2 = cv2
        self._detector = ObjectDetection(confidence=config.data["recognition"]["min_confidence"])

    def recognize(self, bgr_frame, timestamp_ms):
        ok, encoded = self._cv2.imencode(".jpg", bgr_frame)
        if not ok:
            raise RuntimeError("Could not encode the camera frame")
        result = self._detector.detect(encoded.tobytes(), image_type="jpg")
        if result is None:
            raise RuntimeError("Arduino inference returned no result. Check the Object Detection service logs in App Lab.")
        height, width = bgr_frame.shape[:2]
        return integrated_results(result, width, height)

    def close(self):
        pass  # The App Lab service lifecycle belongs to App Lab.


class MediaPipeBackend:
    def __init__(self, config):
        if not config.model_path.is_file():
            raise RuntimeError(f"Missing MediaPipe model: {config.model_path}. Run scripts/download_model.py before deployment.")
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
        except ImportError as exc:
            raise RuntimeError("MediaPipe is unavailable. Install requirements-mediapipe.txt or rebuild the MediaPipe App Lab package.") from exc
        self._cv2, self._mp = cv2, mp
        options = config.data["mediapipe"]
        self._recognizer = vision.GestureRecognizer.create_from_options(
            vision.GestureRecognizerOptions(
                base_options=python.BaseOptions(model_asset_path=str(config.model_path)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=options["num_hands"],
                min_hand_detection_confidence=options["min_hand_detection_confidence"],
                min_hand_presence_confidence=options["min_hand_presence_confidence"],
                min_tracking_confidence=options["min_tracking_confidence"],
            )
        )
        self._last_timestamp = -1

    def recognize(self, bgr_frame, timestamp_ms):
        # VIDEO mode is synchronous and uses tracking. Strictly increasing
        # monotonic timestamps also handle cameras faster than the clock's ms tick.
        timestamp_ms = max(timestamp_ms, self._last_timestamp + 1)
        self._last_timestamp = timestamp_ms
        rgb = self._cv2.cvtColor(bgr_frame, self._cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        return mediapipe_results(self._recognizer.recognize_for_video(image, timestamp_ms))

    def close(self):
        self._recognizer.close()


def create_backend(config):
    if config.backend == "integrated":
        if config.runtime == "standalone":
            from .edge_impulse_backend import EdgeImpulseBackend
            return EdgeImpulseBackend(config)
        return IntegratedBackend(config)
    if config.backend == "mediapipe":
        return MediaPipeBackend(config)
    raise ValueError(f"Unknown backend: {config.backend}")
