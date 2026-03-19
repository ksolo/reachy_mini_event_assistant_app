"""Luma check-in provider.

Uses Luma's internal (undocumented) check-in endpoint, derived by
observing HTTP requests from the Luma organizer web app.

QR code URL format:
    https://luma.com/check-in/{event_api_id}?pk={proxy_key}

The `pk` value in the QR code is a proxy_key, NOT the rsvp_api_id.
A lookup step is required to resolve it to the actual guest api_id (gst-...).

Endpoints:
    GET  https://api2.luma.com/event/admin/get-guest?event_api_id={id}&proxy_key={pk}
         → returns guest JSON with api_id (gst-...) = the real rsvp_api_id
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
from reachy_mini_event_assistant_app.config import config


logger = logging.getLogger(__name__)

_CHECKIN_ENDPOINT = "https://api2.luma.com/event/admin/update-check-in"
_GET_GUEST_ENDPOINT = "https://api2.luma.com/event/admin/get-guest"
_LUMA_CHECK_IN_BASE_URL = "https://luma.com/check-in"


class LumaProvider(EventProvider):
    def __init__(self, session_key: str, client_version: str, event_name: str = "the event") -> None:
        self._session_key = session_key
        self._client_version = client_version
        self._event_name = event_name

    def get_event_name(self) -> str:
        return config.EVENT_NAME or self._event_name

    def checkin_guest(self, qr_data: str) -> CheckinResult:
        session_key = config.LUMA_SESSION_KEY or self._session_key
        client_version = config.LUMA_CLIENT_VERSION or self._client_version

        logger.info("Raw QR data: %r", qr_data)
        event_api_id, proxy_key = self._parse_qr(qr_data)
        logger.info("Parsed QR — event_api_id=%r  proxy_key=%r", event_api_id, proxy_key)
        if not event_api_id or not proxy_key:
            return CheckinResult(
                success=False,
                guest_name=None,
                message="I couldn't read that QR code. Could you try again?",
            )

        # Resolve proxy_key → actual guest api_id (gst-...) required by the check-in endpoint
        rsvp_api_id = self._resolve_rsvp_api_id(
            proxy_key=proxy_key,
            event_api_id=event_api_id,
            session_key=session_key,
            client_version=client_version,
        )
        if rsvp_api_id is None:
            return CheckinResult(
                success=False,
                guest_name=None,
                message="I couldn't find your registration. Please check with the organizers.",
            )
        logger.info("Resolved rsvp_api_id=%r", rsvp_api_id)

        payload = {
            "event_api_id": event_api_id,
            "check_in_method": "guest-list",
            "check_in_status": "checked-in",
            "type": "guest",
            "rsvp_api_id": rsvp_api_id,
        }
        request_headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "x-luma-client-type": "luma-web",
            "x-luma-client-version": client_version,
            "x-luma-web-url": f"{_LUMA_CHECK_IN_BASE_URL}/{event_api_id}",
        }
        logger.info(
            "POST %s  payload=%r  headers=%r  session_key_set=%s",
            _CHECKIN_ENDPOINT,
            payload,
            request_headers,
            bool(session_key),
        )
        try:
            resp = requests.post(
                _CHECKIN_ENDPOINT,
                json=payload,
                headers=request_headers,
                cookies={"luma.auth-session-key": session_key},
                timeout=10,
            )
            logger.info("Response status: %s  body: %r", resp.status_code, resp.text[:500])
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
            body = e.response.text[:500] if e.response is not None else ""
            logger.warning("Luma check-in HTTP error: %s  response_body=%r", e, body)
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

    def _resolve_rsvp_api_id(
        self,
        proxy_key: str,
        event_api_id: str,
        session_key: str,
        client_version: str,
    ) -> str | None:
        """Look up the guest's actual api_id (gst-...) from their proxy_key.

        The proxy_key comes from the QR code `pk` param and is NOT the same
        as the rsvp_api_id needed by the check-in endpoint.
        """
        headers = {
            "accept": "*/*",
            "x-luma-client-type": "luma-web",
            "x-luma-client-version": client_version,
            "x-luma-web-url": f"{_LUMA_CHECK_IN_BASE_URL}/{event_api_id}",
        }
        params = {"event_api_id": event_api_id, "proxy_key": proxy_key}
        logger.info("GET %s  params=%r", _GET_GUEST_ENDPOINT, params)
        try:
            resp = requests.get(
                _GET_GUEST_ENDPOINT,
                params=params,
                headers=headers,
                cookies={"luma.auth-session-key": session_key},
                timeout=10,
            )
            logger.info("get-guest status: %s  body: %r", resp.status_code, resp.text[:500])
            resp.raise_for_status()
            data = resp.json()
            guest_api_id = data.get("guest", {}).get("api_id")
            return guest_api_id or None
        except Exception as e:
            logger.warning("Failed to resolve proxy_key %r: %s", proxy_key, e, exc_info=True)
            return None

    @staticmethod
    def _parse_qr(qr_data: str) -> tuple[str | None, str | None]:
        """Parse event_api_id and proxy_key from a Luma QR code URL.

        Expected format: https://luma.com/check-in/{event_api_id}?pk={proxy_key}
        Note: pk is a proxy_key, not the rsvp_api_id — a lookup step is needed.
        """
        try:
            parsed = urlparse(qr_data)
            path_parts = parsed.path.strip("/").split("/")
            # path: check-in/{event_api_id}
            event_api_id = path_parts[-1] if len(path_parts) >= 2 else None
            pk_list = parse_qs(parsed.query).get("pk")
            proxy_key = pk_list[0] if pk_list else None
            return event_api_id, proxy_key
        except Exception:
            logger.warning("Failed to parse Luma QR data: %r", qr_data)
            return None, None
