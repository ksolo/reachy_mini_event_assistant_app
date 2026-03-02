import logging
import time
from typing import Any, Dict

from reachy_mini_event_assistant_app.camera.qr_scanner import scan_qr_from_frame
from reachy_mini_event_assistant_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)

QR_SCAN_TIMEOUT_S = 10.0
QR_SCAN_POLL_S = 0.2


class CheckinGuest(Tool):
    """Scan a guest's QR code and check them in to the event."""

    name = "checkin_guest"
    description = (
        "Scan the guest's QR code using the camera and check them in to the event. "
        "Ask the guest to hold their QR code up to the camera before calling this tool."
    )
    parameters_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        if deps.event_provider is None:
            return {"error": "Event provider not configured"}
        if deps.camera_worker is None:
            return {"error": "Camera not available"}

        qr_data = self._wait_for_qr(deps.camera_worker)
        if qr_data is None:
            return {
                "result": "I wasn't able to scan a QR code in time. "
                "Could you hold it a bit closer and try again?"
            }

        logger.info("QR code scanned: %s", qr_data)
        result = deps.event_provider.checkin_guest(qr_data)
        return {
            "success": result.success,
            "guest_name": result.guest_name,
            "message": result.message,
        }

    @staticmethod
    def _wait_for_qr(camera_worker: Any) -> str | None:
        """Poll camera frames until a QR code is decoded or timeout."""
        deadline = time.monotonic() + QR_SCAN_TIMEOUT_S
        while time.monotonic() < deadline:
            frame = camera_worker.get_latest_frame()
            if frame is not None:
                qr_data = scan_qr_from_frame(frame)
                if qr_data:
                    return qr_data
            time.sleep(QR_SCAN_POLL_S)
        return None
