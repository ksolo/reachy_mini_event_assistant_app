"""QR code scanning from an OpenCV frame.

Uses OpenCV's built-in QRCodeDetector — no additional system libraries required.
On the simulator (no camera), returns None.
"""

import logging

import cv2
import numpy as np
from numpy.typing import NDArray


logger = logging.getLogger(__name__)

_detector = cv2.QRCodeDetector()


def scan_qr_from_frame(frame: NDArray[np.uint8]) -> str | None:
    """Decode the first QR code found in an OpenCV BGR frame.

    Returns the decoded string payload, or None if no QR code found.
    Tries color frame first, then grayscale for better detection.
    """
    try:
        data, _, _ = _detector.detectAndDecode(frame)
        if data:
            return data
        # Retry with grayscale — often improves detection reliability
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        data, _, _ = _detector.detectAndDecode(gray)
        return data if data else None
    except Exception:
        logger.warning("QR decode error", exc_info=True)
    return None
