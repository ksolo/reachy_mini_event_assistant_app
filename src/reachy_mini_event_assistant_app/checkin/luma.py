"""Luma check-in provider.

Uses Luma's internal (undocumented) check-in endpoint, derived by
observing HTTP requests from the Luma organizer web app.

QR code URL format:
    https://luma.com/check-in/{event_id}?pk={participant_key}

TODO: Capture the exact endpoint, headers, and request body by opening
the Luma organizer check-in page and inspecting the Network tab in
browser devtools while scanning a QR code.
"""

import logging
from urllib.parse import parse_qs, urlparse

import requests

from reachy_mini_event_assistant_app.checkin.base import CheckinResult, EventProvider


logger = logging.getLogger(__name__)

# TODO: Replace with the real internal endpoint once captured from browser devtools
_CHECKIN_ENDPOINT = "https://api.lu.ma/v1/event/check-in"  # placeholder


class LumaProvider(EventProvider):
    def __init__(self, auth_token: str, event_name: str) -> None:
        self._auth_token = auth_token
        self._event_name = event_name

    def get_event_name(self) -> str:
        return self._event_name

    def checkin_guest(self, qr_data: str) -> CheckinResult:
        event_id, pk = self._parse_qr(qr_data)
        if not event_id or not pk:
            return CheckinResult(
                success=False,
                guest_name=None,
                message="I couldn't read that QR code. Could you try again?",
            )

        try:
            resp = requests.post(
                _CHECKIN_ENDPOINT,
                json={"event_id": event_id, "pk": pk},
                headers={
                    "Authorization": f"Bearer {self._auth_token}",
                    "Content-Type": "application/json",
                    # TODO: add any additional headers captured from browser devtools
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            guest_name = data.get("name") or data.get("guest_name")
            name_str = f", {guest_name}" if guest_name else ""
            return CheckinResult(
                success=True,
                guest_name=guest_name,
                message=f"You're checked in{name_str}! Welcome to {self._event_name}!",
            )
        except requests.HTTPError as e:
            logger.warning("Luma check-in HTTP error: %s", e)
            if e.response is not None and e.response.status_code == 404:
                return CheckinResult(
                    success=False,
                    guest_name=None,
                    message="I couldn't find your registration. Please check with the organizers.",
                )
            return CheckinResult(
                success=False,
                guest_name=None,
                message="Something went wrong checking you in. Please see the organizers.",
            )
        except Exception as e:
            logger.error("Luma check-in unexpected error: %s", e, exc_info=True)
            return CheckinResult(
                success=False,
                guest_name=None,
                message="I'm having trouble connecting right now. Please see the organizers.",
            )

    @staticmethod
    def _parse_qr(qr_data: str) -> tuple[str | None, str | None]:
        """Parse event_id and pk from a Luma QR code URL.

        Expected format: https://luma.com/check-in/{event_id}?pk={key}
        """
        try:
            parsed = urlparse(qr_data)
            path_parts = parsed.path.strip("/").split("/")
            # path: check-in/{event_id}
            event_id = path_parts[-1] if len(path_parts) >= 2 else None
            pk_list = parse_qs(parsed.query).get("pk")
            pk = pk_list[0] if pk_list else None
            return event_id, pk
        except Exception:
            logger.warning("Failed to parse Luma QR data: %r", qr_data)
            return None, None
