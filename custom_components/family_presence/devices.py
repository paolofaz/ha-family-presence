"""Stable virtual devices: one household and one device per person.

A Home Assistant device groups entities. It is not a physical actuator.
Identifiers remain independent of display names and source sensor mappings.
"""
from __future__ import annotations
from .const import DOMAIN


def member_device_info(entry_id: str, person_key: str, name: str) -> dict:
    return {
        "identifiers": {(DOMAIN, f"{entry_id}_person_{person_key}")},
        "name": name,
        "manufacturer": "Family Presence",
        "model": "FSM individuale",
    }


def household_device_info(entry_id: str) -> dict:
    return {
        "identifiers": {(DOMAIN, f"{entry_id}_household")},
        "name": "Famiglia",
        "manufacturer": "Family Presence",
        "model": "FSM aggregata",
    }
