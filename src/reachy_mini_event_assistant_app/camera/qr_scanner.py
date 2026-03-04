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
    """
    try:
        data, _, _ = _detector.detectAndDecode(frame)
        return data if data else None
    except Exception:
        logger.debug("QR decode error", exc_info=True)
    return None
