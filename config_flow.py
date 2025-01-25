from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_API_URL

class OracleHospitalityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Oracle Hospitality."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(
                title="Oracle Hospitality",
                data={
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_API_URL: user_input[CONF_API_URL],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_URL): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_API_URL,
                        default=self.config_entry.options.get(CONF_API_URL, ""),
                    ): str,
                    vol.Optional(
                        CONF_USERNAME,
                        default=self.config_entry.options.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD,
                        default=self.config_entry.options.get(CONF_PASSWORD, ""),
                    ): str,
                }
            ),
        )
