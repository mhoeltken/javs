# SPDX-License-Identifier: Apache-2.0
"""Pure JAVS logic: abbreviations, sorting, badge state. No GTK, no I/O."""

from dataclasses import dataclass

OFF = "off"
CONNECTING = "connecting"
ON = "on"
ERROR = "error"

BADGE_COLORS = {
    OFF: (0.45, 0.47, 0.50),
    CONNECTING: (0.80, 0.60, 0.05),
    ON: (0.10, 0.50, 0.22),
    ERROR: (0.70, 0.15, 0.15),
}

UNKNOWN_ABBREVIATION = "???"
ABBREVIATION_LENGTH = 3


@dataclass(frozen=True)
class Badge:
    text: str
    state: str


def abbreviate(name):
    """Last segment of the name (separator '-'), upper case, cut to 3 characters."""
    parts = [part.strip() for part in name.split("-")]
    parts = [part for part in parts if part]
    if not parts:
        return UNKNOWN_ABBREVIATION
    return parts[-1][:ABBREVIATION_LENGTH].upper()


def sort_vpns(names):
    return sorted(names, key=str.casefold)


def badge_for(active_name=None, activating=False, error=False, busy=False):
    if error:
        return Badge("ERR", ERROR)
    if active_name is not None and not activating:
        return Badge(abbreviate(active_name), ON)
    if active_name is not None or busy:
        return Badge("…", CONNECTING)
    return Badge("OFF", OFF)
