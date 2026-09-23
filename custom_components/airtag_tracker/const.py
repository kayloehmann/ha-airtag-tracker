"""Constants for the AirTag Tracker integration."""

from datetime import timedelta

DOMAIN = "airtag_tracker"
PLATFORMS = ["device_tracker", "sensor"]

CONF_ACCOUNT = "account"
CONF_ACCESSORY = "accessory"
CONF_EMAIL = "email"
CONF_NAME = "name"
CONF_INSIDE_POLL_INTERVAL = "inside_poll_interval"
CONF_OUTSIDE_POLL_INTERVAL = "outside_poll_interval"

DEFAULT_INSIDE_POLL_INTERVAL = 15
DEFAULT_OUTSIDE_POLL_INTERVAL = 5
MIN_POLL_INTERVAL = 2
MAX_POLL_INTERVAL = 60
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=DEFAULT_INSIDE_POLL_INTERVAL)

ANISETTE_LIBS_FILENAME = "airtag_tracker_anisette.bin"
