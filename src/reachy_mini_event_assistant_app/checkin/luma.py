"""Luma check-in provider.

Uses Luma's internal (undocumented) check-in endpoint, derived by
observing HTTP requests from the Luma organizer web app.

QR code URL format:
    https://luma.com/check-in/{event_api_id}?pk={rsvp_api_id}

Endpoint:
    POST https://api2.luma.com/event/admin/update-check-in

Auth:
    Cookie: luma.auth-session-key={LUMA_SESSION_KEY}

Fragility notes:
    - This is an undocumented internal API and may break without warning.
    - LUMA_CLIENT_VERSION is a Luma frontend deploy hash. If check-in
      stops working, capture a fresh value from browser devtools and
      update the LUMA_CLIENT_VERSION env var.
    - LUMA_SESSION_KEY is a browser session cookie that will eventually
      expire. Re-capture from devtools when it does.
"""

import logging
from urllib.parse import parse_qs, urlparse

import requests

from reachy_mini_event_assistant_app.checkin.base import CheckinResult, EventProvider


logger = logging.getLogger(__name__)

_CHECKIN_ENDPOINT = "https://api2.luma.com/event/admin/update-check-in"
_LUMA_CHECK_IN_BASE_URL = "https://luma.com/check-in"


class LumaProvider(EventProvider):
    def __init__(self, session_key: str, client_version: str) -> None:
        self._session_key = session_key
        self._client_version = client_version

    def get_event_name(self) -> str:
        return "the event"

    def checkin_guest(self, qr_data: str) -> CheckinResult:
        event_api_id, rsvp_api_id = self._parse_qr(qr_data)
        if not event_api_id or not rsvp_api_id:
            return CheckinResult(
                success=False,
                guest_name=None,
                message="I couldn't read that QR code. Could you try again?",
            )

        try:
            resp = requests.post(
                _CHECKIN_ENDPOINT,
                json={
                    "event_api_id": event_api_id,
                    "check_in_method": "guest-list",
                    "check_in_status": "checked-in",
                    "type": "guest",
                    "rsvp_api_id": rsvp_api_id,
                },
                headers={
                    "accept": "*/*",
                    "content-type": "application/json",
                    "x-luma-client-type": "luma-web",
                    "x-luma-client-version": self._client_version,
                    "x-luma-web-url": f"{_LUMA_CHECK_IN_BASE_URL}/{event_api_id}",
                },
                cookies={"luma.auth-session-key": self._session_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            guest = data.get("guest", {})
            guest_name = guest.get("first_name") or guest.get("name")
            name_str = f", {guest_name}" if guest_name else ""
            return CheckinResult(
                success=True,
                guest_name=guest_name,
                message=f"You're checked in{name_str}! Enjoy the event!",
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
        """Parse event_api_id and rsvp_api_id from a Luma QR code URL.

        Expected format: https://luma.com/check-in/{event_api_id}?pk={rsvp_api_id}
        """
        try:
            parsed = urlparse(qr_data)
            path_parts = parsed.path.strip("/").split("/")
            # path: check-in/{event_api_id}
            event_api_id = path_parts[-1] if len(path_parts) >= 2 else None
            pk_list = parse_qs(parsed.query).get("pk")
            rsvp_api_id = pk_list[0] if pk_list else None
            return event_api_id, rsvp_api_id
        except Exception:
            logger.warning("Failed to parse Luma QR data: %r", qr_data)
            return None, None
