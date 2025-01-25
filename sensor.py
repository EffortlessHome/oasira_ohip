from homeassistant.helpers.entity import Entity
from .const import DOMAIN, DEFAULT_NAME
import requests

class OracleHospitalitySensor(Entity):
    """Representation of the Oracle Hospitality FO Status sensor."""

    def __init__(self, hass, config):
        self._hass = hass
        self._config = config
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return DEFAULT_NAME

    @property
    def state(self):
        """Return the current state."""
        return self._state

    def update(self):
        """Fetch new data from the API."""
        api_url = self._config["api_url"]
        username = self._config["username"]
        password = self._config["password"]

        try:
            response = requests.get(
                f"{api_url}/property/v1/foStatus",
                auth=(username, password),
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            self._state = response.json().get("status", "unknown")
        except requests.RequestException as e:
            self._state = "error"
            print(f"Error fetching FO status: {e}")
