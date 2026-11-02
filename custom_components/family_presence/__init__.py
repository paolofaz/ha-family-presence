"""HACS discovery bootstrap for Family Presence.

The development/testing implementation lives in the v0.1.0a1 prerelease.
This module never registers entities and never changes household presence.
"""
from __future__ import annotations


async def async_setup(hass, config) -> bool:
    """Deliberately inert main-branch placeholder."""
    return True
