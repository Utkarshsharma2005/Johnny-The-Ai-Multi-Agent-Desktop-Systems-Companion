from enum import Enum
from typing import List, Set

class ScreenObservationStatus(str, Enum):
    OBSERVING = "OBSERVING"
    PAUSED = "PAUSED"

class ScreenPrivacyManager:
    """
    Manages global privacy controls, pause/resume mechanisms, and application exclusion rules
    to ensure Johnny never records or analyzes sensitive user data.
    """

    DEFAULT_EXCLUDED_KEYWORDS: Set[str] = {
        "password", "bitwarden", "1password", "keepass", "KeePassXC",
        "lastpass", "private browsing", "incognito", "bank", "vault"
    }

    def __init__(self):
        self._status: ScreenObservationStatus = ScreenObservationStatus.OBSERVING
        self._excluded_keywords: Set[str] = set(self.DEFAULT_EXCLUDED_KEYWORDS)

    @property
    def status(self) -> ScreenObservationStatus:
        return self._status

    @property
    def is_paused(self) -> bool:
        return self._status == ScreenObservationStatus.PAUSED

    def pause(self) -> str:
        """Pauses screen observation globally."""
        self._status = ScreenObservationStatus.PAUSED
        return "Screen intelligence observation is PAUSED"

    def resume(self) -> str:
        """Resumes screen observation."""
        self._status = ScreenObservationStatus.OBSERVING
        return "Screen intelligence observation is ACTIVE (OBSERVING)"

    def is_window_excluded(self, window_title: str) -> bool:
        """
        Checks if a window title contains any sensitive or excluded privacy keyword.
        """
        if not window_title:
            return False
        title_lower = window_title.lower()
        return any(kw in title_lower for kw in self._excluded_keywords)

    def add_exclusion_keyword(self, keyword: str) -> None:
        """Adds a custom keyword to the exclusion list."""
        if keyword:
            self._excluded_keywords.add(keyword.lower().strip())

    def remove_exclusion_keyword(self, keyword: str) -> None:
        """Removes a keyword from the exclusion list."""
        self._excluded_keywords.discard(keyword.lower().strip())

    def get_exclusion_keywords(self) -> List[str]:
        """Returns the sorted list of active exclusion keywords."""
        return sorted(list(self._excluded_keywords))

# Global singleton privacy instance
privacy_manager = ScreenPrivacyManager()
