import requests
import logging
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import json
import aiohttp
import async_timeout
import base64
import asyncio
from datetime import timedelta
from pathlib import Path
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.event import async_track_time_interval
from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_OHIP_HOST_URL,
    CONF_APPKEY,
    CONF_HOTELID,
    CONF_CLIENTID,
    CONF_CLIENTSECRET,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=15)


class HASSComponent:
    """Hasscomponent."""

    # Class-level property to hold the hass instance
    hass_instance = None

    @classmethod
    def set_hass(cls, hass: HomeAssistant) -> None:
        """Set Hass."""
        cls.hass_instance = hass

    @classmethod
    def get_hass(cls):  # noqa: ANN206
        """Get Hass."""
        return cls.hass_instance


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the integration via YAML (if needed)."""
    HASSComponent.set_hass(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Oracle Hospitality from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["config"] = entry
    hass.data[DOMAIN][entry.entry_id] = entry.data

    HASSComponent.set_hass(hass)

    # Start a timer to update the sensor every 15 minutes
    async_track_time_interval(hass, async_update, UPDATE_INTERVAL)

    return await loaddata()


async def loaddata():
    """Load data from OHIP and create sensors."""

    hass = HASSComponent.get_hass()
    entry = hass.data[DOMAIN]["config"]

    try:
        ohip_host = entry.data.get(CONF_OHIP_HOST_URL)
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)

        appkey = entry.data.get(CONF_APPKEY)
        hotelid = entry.data.get(CONF_HOTELID)
        client_id = entry.data.get(CONF_CLIENTID)
        client_secret = entry.data.get(CONF_CLIENTSECRET)

        # authenticate
        token = await authenticate(
            client_id, client_secret, ohip_host, appkey, username, password
        )

        print(token)

        for i in range(
            1, 4
        ):  # The range function goes up to but does not include the last number
            url = (
                ohip_host
                + "/hsk/v1/hotels/"
                + hotelid
                + "/housekeepingOverview?limit=100&floor="
                + str(i)
            )
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
                "x-hotelid": hotelid,
                "x-app-key": appkey,
            }

            _LOGGER.info("Calling get plan status API")

            print(url)

            async with aiohttp.ClientSession() as session:  # noqa: SIM117
                async with session.get(url, headers=headers) as response:
                    _LOGGER.debug("API response status: %s", response.status)
                    _LOGGER.debug("API response headers: %s", response.headers)
                    content = await response.text()
                    _LOGGER.debug("API response content: %s", content)

                    print(response.status)

                    if content is not None:
                        data = json.loads(content)

            # Extract housekeeping statuses
            rooms = (
                data.get("housekeepingRoomInfo", {})
                .get("housekeepingRooms", {})
                .get("room", [])
            )
            statuses = {}

            for room in rooms:
                room_id = room.get("roomId", "Unknown")
                status = (
                    room.get("housekeeping", {})
                    .get("housekeepingRoomStatus", {})
                    .get("housekeepingStatus", "Not found")
                )
                statuses[room_id] = status

            # Print results
            for room, status in statuses.items():
                print(f"Room {room}: {status}")

            # Retrieve existing sensor and binary sensor entities
            existing_sensors = hass.data.get("sensor")
            existing_sensors = existing_sensors.entities if existing_sensors else {}

            # Create a dictionary of existing sensors using their unique_id
            existing_sensor_dict = {
                sensor.unique_id: sensor for sensor in existing_sensors
            }

            existing_binary_sensors = hass.data.get("binary_sensor")
            existing_binary_sensors = (
                existing_binary_sensors.entities if existing_binary_sensors else {}
            )

            existing_binary_sensor_dict = {
                sensor.unique_id: sensor for sensor in existing_binary_sensors
            }

            platform = async_get_platforms(hass, "sensor")

            # Update existing sensors or create new ones if they don't exist
            sensors = []
            for room, status in statuses.items():
                if room in existing_sensor_dict:
                    existing_sensor_dict[room].update_status(
                        status
                    )  # Ensure your class has an update method
                else:
                    sensors.append(HotelRoomSensor(room, status))

            # Add new sensors if there are any
            if sensors:
                platform = async_get_platforms(hass, "sensor")
                if platform:
                    await platform[0].async_add_entities(sensors, True)

            platform2 = async_get_platforms(hass, "binary_sensor")

            # Create or update binary sensors
            binary_sensors = []
            for room, status in statuses.items():
                if room in existing_binary_sensor_dict:
                    existing_binary_sensor_dict[room].update_status(
                        status
                    )  # Ensure your class has an update method
                else:
                    binary_sensors.append(HotelRoomStatusBinarySensor(room, status))

            if binary_sensors:
                platform2 = async_get_platforms(hass, "binary_sensor")
                if platform2:
                    await platform2[0].async_add_entities(binary_sensors, True)

    except (OSError, json.JSONDecodeError) as error:
        _LOGGER.error("Error loading response.json: %s", error)
        return False

    return True


async def async_update(event_time):
    """Fetch new data and update the state."""
    _LOGGER.info("Fetching new data for OHIP")
    await loaddata()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "bniary_sensor"]
    )


async def authenticate(clientid, clientsecret, host, appkey, username, password):
    """Authenticates using Basic Auth and retrieves a Bearer token."""

    host_url = host + "/oauth/v1/tokens"

    print(host_url)

    auth_header = base64.b64encode(f"{clientid}:{clientsecret}".encode()).decode()

    data = {"username": username, "password": password, "grant_type": "password"}

    headers = {
        "Authorization": f"Basic {auth_header}",
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "x-app-key": appkey,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(host_url, headers=headers, data=data) as response:
                if response.status == 200:
                    data = await response.json()
                    token = data.get("access_token")

                    if token:
                        _LOGGER.info(
                            "Successfully authenticated and retrieved Bearer token"
                        )
                        return token
                    else:
                        _LOGGER.error("Authentication succeeded but no token received")
                        return ""
                else:
                    _LOGGER.error(f"Authentication failed: {response.status}")
                    return ""
    except aiohttp.ClientError as e:
        _LOGGER.error(f"Authentication request failed: {e}")
        return ""


class HotelRoomSensor(Entity):
    """Representation of a Hotel Room sensor."""

    def __init__(self, name, status):
        """Initialize the sensor."""
        self._name = name
        self._room_id = name
        self._state = status

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        return {"room_id": self._room_id}


class HotelRoomStatusBinarySensor(BinarySensorEntity):
    """Representation of a Hotel Room status binary sensor."""

    def __init__(self, name, status):
        """Initialize the binary sensor."""
        self._name = f"{name} Occupied"
        self._room_id = name
        self._state = status != "Vacant"

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return True if the room is occupied, otherwise False."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        return {"room_id": self._room_id}
