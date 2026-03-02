from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CheckinResult:
    success: bool
    guest_name: str | None
    message: str  # spoken back to the guest by the robot


class EventProvider(ABC):
    @abstractmethod
    def checkin_guest(self, qr_data: str) -> CheckinResult:
        """Check in a guest given the raw QR code payload (a URL string)."""
        ...

    @abstractmethod
    def get_event_name(self) -> str:
        """Return the display name of the event."""
        ...
