import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, TITLE
from .const import create_step_one_schema, create_step_two_schema, create_step_three_schema

class PVcontrollerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle pv_controller options flow."""

    def __init__(self, config_entry):
        """Initialize the options flow handler."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle the first step of the options flow."""
        errors = {}
        if user_input is not None:
            try:
                # Validate user input
                create_step_one_schema(self.config_entry)(user_input)
                
                # Store the data from the first step and proceed to the second step
                self.context["step_one_data"] = user_input
                return await self.async_step_two()
                                          
            except vol.Invalid as err:
                # Capture the validation error and add it to the errors
                errors["base"] = str(err)

        return self.async_show_form(
            step_id="init",
            data_schema=create_step_one_schema(self.config_entry),
            errors=errors
        )

    async def async_step_two(self, user_input=None):
        """Handle the second step of the options flow."""
        errors = {}
        if user_input is not None:
            try:
                # Validate user input for the second step
                create_step_two_schema(self.config_entry)(user_input)
                # Store the data from the second step and proceed to the third step
                self.context["step_two_data"] = user_input
                return await self.async_step_three()
            except vol.Invalid as err:
                # Capture the validation error and add it to the errors
                errors["base"] = str(err)

        return self.async_show_form(
            step_id="two",
            data_schema=create_step_two_schema(self.config_entry),
            errors=errors
        )

    async def async_step_three(self, user_input=None):
        """Handle the third step of the options flow."""
        errors = {}
        if user_input is not None:
            try:
                # Validate user input for the third step
                create_step_three_schema(self.config_entry)(user_input)
                # Combine the data from all steps
                data = {**self.context["step_one_data"], **self.context["step_two_data"], **user_input}
                
                # Save the changes to the config_entry
                self.hass.config_entries.async_update_entry(self.config_entry, options=data)

                # Force a reload immediately after confirming the options
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                # Create and return the options entry
                return self.async_create_entry(title="Opciones TFG " + TITLE, data=data)
                
            except vol.Invalid as err:
                # Capture the validation error and add it to the errors
                errors["base"] = str(err)

        return self.async_show_form(
            step_id="three",
            data_schema=create_step_three_schema(self.config_entry),
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return PVcontrollerOptionsFlowHandler(config_entry)