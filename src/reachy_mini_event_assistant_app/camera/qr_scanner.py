"""QR code scanning from an OpenCV frame.

Uses pyzbar for decoding. On the simulator (no camera), returns None.
"""

import logging

import numpy as np
from numpy.typing import NDArray


logger = logging.getLogger(__name__)

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    _PYZBAR_AVAILABLE = True
except ImportError:
    logger.warning("pyzbar not available — QR scanning will not work")
    _PYZBAR_AVAILABLE = False


def scan_qr_from_frame(frame: NDArray[np.uint8]) -> str | None:
    """Decode the first QR code found in an OpenCV BGR frame.

    Returns the decoded string payload, or None if no QR code found.
    """
    if not _PYZBAR_AVAILABLE:
        return None

    try:
        decoded = pyzbar_decode(frame)
        for obj in decoded:
            if obj.type == "QRCODE":
                return obj.data.decode("utf-8")
    except Exception:
        logger.debug("QR decode error", exc_info=True)
    return None
