"""Common results and a filter operating on fresh inference frames only."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Detection:
    gesture: str
    confidence: float
    hand: str | None = None
    raw_label: str | None = None

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
