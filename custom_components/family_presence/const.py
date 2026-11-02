"""Configuration keys and defaults matching the current YAML package."""

DOMAIN = "family_presence"
CONF_HOUSEHOLD_NAME = "household_name"
CONF_PEOPLE = "people"
CONF_PERSON_NAME = "person_name"
CONF_PERSON_ID = "person_id"
CONF_IPHONE = "iphone_tracker"
CONF_WATCH = "watch_sensor"
CONF_BAG = "bag_sensor"
CONF_BAG_POLICY = "bag_policy"
CONF_REFERENCE = "legacy_presence_entity"
CONF_GATE_ENTITIES = "gate_entities"
CONF_DOOR = "door_contact"
CONF_LOCK = "door_lock"
CONF_ALARM = "alarm"
CONF_ADD_ANOTHER = "add_another"

DEFAULT_WINDOWS = {
    "exit_gate_seconds": 120,
    "exit_door_seconds": 90,
    "exit_lock_seconds": 90,
    "entry_gate_seconds": 120,
    "entry_door_seconds": 120,
    "entry_lock_seconds": 120,
}
