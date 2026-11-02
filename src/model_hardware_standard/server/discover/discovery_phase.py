"""Phases of the connectivity discovery process."""

from enum import StrEnum


class DiscoveryPhase(StrEnum):
    ENUMERATE = "enumerate"
    ENDPOINT = "endpoint"
    OPEN = "open"
    CLOSE = "close"


__all__ = ["DiscoveryPhase"]
