"""Person detection using OpenCV background subtraction.

Runs in a background thread, sets a threading.Event when a person
(significant motion or face) is detected in the camera frame.

Simulator fallback: antenna press is used instead — detection is
disabled when no camera worker is available.
"""

import logging
import threading
import time

import cv2
import numpy as np
from numpy.typing import NDArray


logger = logging.getLogger(__name__)

# Tunable thresholds — will need adjustment on physical hardware
MOTION_AREA_THRESHOLD = 3000   # minimum contour area in pixels to count as motion
FACE_CONFIDENCE_THRESHOLD = 0.7
DETECTION_COOLDOWN_S = 5.0     # seconds before re-triggering after a detection


class PersonDetector(threading.Thread):
    """Background thread that watches camera frames for approaching people.

    Sets `person_detected` event when triggered. The main app resets
    the event after handling the greeting.
    """

    def __init__(self, camera_worker: object, person_detected: threading.Event) -> None:
        super().__init__(name="PersonDetector", daemon=True)
        self._camera_worker = camera_worker
        self.person_detected = person_detected
        self._stop_event = threading.Event()
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=100, varThreshold=40, detectShadows=False
        )
        self._last_trigger_time: float = 0.0

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        logger.info("PersonDetector started")
        while not self._stop_event.is_set():
            frame = self._camera_worker.get_latest_frame()  # type: ignore[attr-defined]
            if frame is not None:
                if self._motion_detected(frame):
                    now = time.monotonic()
                    if now - self._last_trigger_time > DETECTION_COOLDOWN_S:
                        logger.info("Person detected — triggering greeting")
                        self._last_trigger_time = now
                        self.person_detected.set()
            time.sleep(0.1)

    def _motion_detected(self, frame: NDArray[np.uint8]) -> bool:
        """Return True if significant motion is detected in the frame."""
        small = cv2.resize(frame, (320, 240))
        fg_mask = self._bg_subtractor.apply(small)
        # Remove noise
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        total_area = sum(cv2.contourArea(c) for c in contours)
        return total_area > MOTION_AREA_THRESHOLD
