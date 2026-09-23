"""Common results and a filter operating on fresh inference frames only."""

from collections import deque
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Detection:
    gesture: str
    confidence: float
    hand: str | None = None
    raw_label: str | None = None
    center: tuple[float, float] | None = None

    def to_dict(self):
        return asdict(self)


class StableGesture:
    """Select the strongest gesture; require consecutive frames before accepting it.

    Multi-hand results are available from the backends, but this LED demo has one
    active gesture. A low-confidence/empty frame immediately clears its state.
    """

    def __init__(self, min_confidence, stable_frames):
        self.min_confidence = min_confidence
        self.stable_frames = stable_frames
        self._candidate = None
        self._count = 0

    def update(self, detections):
        eligible = [d for d in detections if d.gesture != "None" and d.confidence >= self.min_confidence]
        best = max(eligible, key=lambda d: d.confidence, default=None)
        key = (best.gesture, best.hand) if best else None
        if key is None:
            self._candidate, self._count = None, 0
            return None
        if key != self._candidate:
            self._candidate, self._count = key, 1
        else:
            self._count += 1
        return best if self._count >= self.stable_frames else None


class SwipeDetector:
    """Detect fast horizontal open-palm translation from normalized centers."""

    def __init__(self, min_confidence=0.55, min_displacement=0.40,
                 window_seconds=0.75, max_gap_seconds=0.30,
                 vertical_tolerance=0.22, min_directionality=0.65,
                 cooldown_seconds=1.2, min_points=4,
                 min_moving_steps=2, max_step=0.30):
        self.min_confidence = min_confidence
        self.min_displacement = min_displacement
        self.window_seconds = window_seconds
        self.max_gap_seconds = max_gap_seconds
        self.vertical_tolerance = vertical_tolerance
        self.min_directionality = min_directionality
        self.cooldown_seconds = cooldown_seconds
        self.min_points = min_points
        self.min_moving_steps = min_moving_steps
        self.max_step = max_step
        self._points = deque()
        self._last_event = float("-inf")

    def update(self, detections, timestamp_ms):
        now = timestamp_ms / 1000.0
        palms = [d for d in detections if d.gesture == "Open_Palm"
                 and d.center is not None and d.confidence >= self.min_confidence]
        palm = max(palms, key=lambda d: d.confidence, default=None)
        if palm is None:
            self._points.clear()
            return None
        if self._points and now - self._points[-1][0] > self.max_gap_seconds:
            self._points.clear()
        self._points.append((now, palm.center[0], palm.center[1], palm.confidence, palm.raw_label))
        while self._points and now - self._points[0][0] > self.window_seconds:
            self._points.popleft()
        if len(self._points) < self.min_points:
            return None

        first, last = self._points[0], self._points[-1]
        dx, dy = last[1] - first[1], last[2] - first[2]
        points = list(self._points)
        steps = [b[1] - a[1] for a, b in zip(points, points[1:])]
        path = sum(abs(step) for step in steps)
        moving_steps = [step for step in steps if abs(step) >= 0.035]
        if (abs(dx) >= self.min_displacement and abs(dy) <= self.vertical_tolerance
                and path > 0 and abs(dx) / path >= self.min_directionality
                and len(moving_steps) >= self.min_moving_steps
                and max(map(abs, steps), default=0) <= self.max_step
                and now - self._last_event >= self.cooldown_seconds):
            self._last_event = now
            confidence = sum(point[3] for point in points) / len(points)
            raw = last[4]
            self._points.clear()
            return Detection("Swipe", confidence, raw_label=raw)
        return None
