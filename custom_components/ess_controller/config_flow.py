import voluptuous as vol
from homeassistant import config_entries
from datetime import datetime
import pytz
from homeassistant.core import callback
from .options_flow import PVcontrollerOptionsFlowHandler  # Ensure to import the class

from .const import DOMAIN, TITLE
from .const import create_step_one_schema, create_step_two_schema, create_step_three_schema

class PVcontrollerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pv_controller."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the first step of the user configuration flow."""
        errors = {}
        if user_input is not None:
            try:
                # Validate user input for the first step
                create_step_one_schema()(user_input)
                # Store the data from the first step and proceed to the second step
                self.context["step_one_data"] = user_input
                return await self.async_step_two()
            except vol.Invalid as err:
                # Capture the validation error and add it to the errors
                errors["base"] = str(err)

        return self.async_show_form(
            step_id="user",
            data_schema=create_step_one_schema(),
            errors=errors
        )

    async def async_step_two(self, user_input=None):
        """Handle the second step of the user configuration flow."""
        errors = {}
        if user_input is not None:
            try:
                # Validate user input for the second step
                create_step_two_schema()(user_input)
                # Store the data from the second step and proceed to the third step
                self.context["step_two_data"] = user_input
                return await self.async_step_three()
            except vol.Invalid as err:
                # Capture the validation error and add it to the errors
                errors["base"] = str(err)

        return self.async_show_form(
            step_id="two",
            data_schema=create_step_two_schema(),
            errors=errors
        )

    async def async_step_three(self, user_input=None):
        """Handle the third step of the user configuration flow."""
        errors = {}
        if user_input is not None:
            try:
                # Validate user input for the third step
                create_step_three_schema()(user_input)
                # Combine the data from all steps
                data = {**self.context["step_one_data"], **self.context["step_two_data"], **user_input}
                return self.async_create_entry(title=TITLE, data=data)
            except vol.Invalid as err:
                # Capture the validation error and add it to the errors
                errors["base"] = str(err)

        return self.async_show_form(
            step_id="three",
            data_schema=create_step_three_schema(),
            errors=errors
        )

    async def async_step_import(self, user_input=None):
        """Handle import from YAML."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return PVcontrollerOptionsFlowHandler(config_entry)