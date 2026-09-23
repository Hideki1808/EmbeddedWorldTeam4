import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "uno-q-gesture-integrated" / "python"))

from gesture_app.backends import integrated_results
from gesture_app.recognition import Detection, SwipeDetector, StableGesture


def palm(x, y=0.5, confidence=0.9):
    return Detection("Open_Palm", confidence, raw_label="five", center=(x, y))


class SwipeDetectorTests(unittest.TestCase):
    def make_swipe(self, positions, start=0):
        detector = SwipeDetector()
        result = None
        for index, x in enumerate(positions):
            result = detector.update([palm(x)], start + index * 50) or result
        return result

    def test_right_and_left_swipes(self):
        self.assertEqual(self.make_swipe([0.12, 0.25, 0.40, 0.57, 0.72]).gesture, "Swipe")
        self.assertEqual(self.make_swipe([0.82, 0.68, 0.52, 0.35, 0.20]).gesture, "Swipe")

    def test_small_jitter_and_vertical_motion_do_not_trigger(self):
        self.assertIsNone(self.make_swipe([0.40, 0.43, 0.39, 0.44, 0.42]))
        self.assertIsNone(self.make_swipe([(0.5)] * 5))
        detector = SwipeDetector()
        result = None
        for index, y in enumerate([0.1, 0.25, 0.42, 0.62, 0.82]):
            result = detector.update([palm(0.5, y)], index * 50) or result
        self.assertIsNone(result)

    def test_single_box_jump_does_not_look_like_swipe(self):
        self.assertIsNone(self.make_swipe([0.35, 0.35, 0.85, 0.85, 0.85]))

    def test_only_one_event_per_cooldown(self):
        detector = SwipeDetector()
        events = []
        samples = [(0, .1), (50, .25), (100, .4), (150, .58), (200, .75),
                   (300, .8), (350, .65), (400, .48), (450, .3), (500, .15)]
        for timestamp, x in samples:
            event = detector.update([palm(x)], timestamp)
            if event:
                events.append(event)
        self.assertEqual([event.gesture for event in events], ["Swipe"])

    def test_requires_open_palm_and_confidence(self):
        detector = SwipeDetector()
        result = None
        for index, x in enumerate([0.1, 0.3, 0.55, 0.8]):
            result = detector.update([Detection("Thumb_Up", .99, center=(x, .5))], index * 50) or result
        self.assertIsNone(result)
        result = None
        for index, x in enumerate([0.1, 0.3, 0.55, 0.8]):
            result = detector.update([palm(x, confidence=.4)], 1000 + index * 50) or result
        self.assertIsNone(result)

    def test_box_center_extracted_from_integrated_detection(self):
        result = integrated_results({"detection": [{
            "class_name": "five", "confidence": "91", "bounding_box_xyxy": [20, 10, 60, 50]
        }]}, image_width=100, image_height=100)
        self.assertEqual(result[0].gesture, "Open_Palm")
        self.assertEqual(result[0].center, (0.4, 0.3))
        self.assertIsNone(integrated_results({"detection": [{
            "class_name": "five", "confidence": "91"
        }]})[0].center)

    def test_stable_static_gesture_still_works(self):
        stable = StableGesture(min_confidence=.6, stable_frames=3)
        for _ in range(2):
            self.assertIsNone(stable.update([Detection("Thumb_Up", .9)]))
        self.assertEqual(stable.update([Detection("Thumb_Up", .9)]).gesture, "Thumb_Up")


if __name__ == "__main__":
    unittest.main()
