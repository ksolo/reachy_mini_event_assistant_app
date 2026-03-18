import asyncio
import logging
import time
from typing import Any, Dict

from reachy_mini.utils import create_head_pose

from reachy_mini_event_assistant_app.camera.qr_scanner import scan_qr_from_frame
from reachy_mini_event_assistant_app.dance_emotion_moves import GotoQueueMove
from reachy_mini_event_assistant_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)

QR_SCAN_TIMEOUT_S = 10.0
QR_SCAN_POLL_S = 0.2
# Pitch angle (degrees) to look down toward a guest's phone
QR_LOOK_PITCH_DEG = 20
# Duration for the look-down movement, then settle time before scanning
QR_LOOK_DURATION_S = 1.0
QR_SETTLE_DELAY_S = 0.3


class CheckinGuest(Tool):
    """Scan a guest's QR code and check them in to the event."""

    name = "checkin_guest"
    description = (
        "Stop what you're doing and scan the guest's QR code using the camera to check "
        "them in to the event. Call this as soon as the guest wants to check in — the tool "
        "stops any ongoing movement, looks toward the guest's phone, then scans for up to 10 seconds."
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

        # Stop any ongoing movement (idle sweep, etc.)
        deps.movement_manager.clear_move_queue()
        logger.info("Movement queue cleared; looking down for QR scan")

        # Orient the head downward toward where a guest would hold their phone
        try:
            target_pose = create_head_pose(0, 0, 0, 0, QR_LOOK_PITCH_DEG, 0, degrees=True)
            current_head_pose = deps.reachy_mini.get_current_head_pose()
            _, current_antennas = deps.reachy_mini.get_current_joint_positions()
            look_down = GotoQueueMove(
                target_head_pose=target_pose,
                start_head_pose=current_head_pose,
                target_antennas=(0, 0),
                start_antennas=(current_antennas[0], current_antennas[1]),
                target_body_yaw=0,
                start_body_yaw=current_antennas[0],
                duration=QR_LOOK_DURATION_S,
            )
            deps.movement_manager.queue_move(look_down)
            deps.movement_manager.set_moving_state(QR_LOOK_DURATION_S)
        except Exception:
            logger.warning("Could not queue look-down move; continuing with current head position", exc_info=True)

        # Wait for look-down to complete then settle
        await asyncio.sleep(QR_LOOK_DURATION_S + QR_SETTLE_DELAY_S)

        logger.info("Starting QR scan (timeout=%.1fs)", QR_SCAN_TIMEOUT_S)
        qr_data = await self._wait_for_qr(deps.camera_worker)
        if qr_data is None:
            logger.warning("QR scan timed out after %.1fs — no code detected", QR_SCAN_TIMEOUT_S)
            return {
                "result": "no_qr_detected",
                "message": "No QR code detected in time. Ask the guest to hold it closer and steadier.",
            }

        logger.info("QR code scanned: %s", qr_data)
        result = deps.event_provider.checkin_guest(qr_data)
        return {
            "success": result.success,
            "guest_name": result.guest_name,
            "message": result.message,
        }

    @staticmethod
    async def _wait_for_qr(camera_worker: Any) -> str | None:
        """Poll camera frames until a QR code is decoded or timeout."""
        deadline = time.monotonic() + QR_SCAN_TIMEOUT_S
        frames_checked = 0
        null_frames = 0
        while time.monotonic() < deadline:
            frame = camera_worker.get_latest_frame()
            if frame is None:
                null_frames += 1
                if null_frames % 10 == 1:
                    logger.warning("Camera returned None frame (count=%d)", null_frames)
            else:
                frames_checked += 1
                qr_data = scan_qr_from_frame(frame)
                if qr_data:
                    logger.info("QR detected after %d frames checked", frames_checked)
                    return qr_data
            await asyncio.sleep(QR_SCAN_POLL_S)
        logger.info("QR scan finished: %d frames checked, %d null frames", frames_checked, null_frames)
        return None
