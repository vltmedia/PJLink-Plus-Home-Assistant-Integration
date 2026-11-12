"""Data coordinator for one PJLink projector."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, TRANSITION_SCAN_INTERVAL
from .pjlink import (
    ERROR_CATEGORIES,
    ErrorLevel,
    PJLinkAuthError,
    PJLinkClient,
    PJLinkCommandError,
    PJLinkError,
    PJLinkParameterError,
    PJLinkUnavailableError,
    PJLinkUnsupportedError,
    PowerState,
    ProjectorInfo,
    ProjectorStatus,
)
from .pjlink.models import ERROR_LEVELS, POWER_STATES

_LOGGER = logging.getLogger(__name__)

type PJLinkConfigEntry = ConfigEntry[PJLinkCoordinator]


class PJLinkCoordinator(DataUpdateCoordinator[ProjectorStatus]):
    """Poll a projector, and apply the status notifications it pushes."""

    config_entry: PJLinkConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: PJLinkConfigEntry, client: PJLinkClient
    ) -> None:
        self._base_interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=self._base_interval,
        )
        self.client = client
        self.info = ProjectorInfo()
        self.unique_id: str = entry.unique_id or entry.entry_id

    async def _async_setup(self) -> None:
        """Read the static facts once, before the first poll."""
        try:
            self.info = await self.client.fetch_info()
        except PJLinkAuthError as err:
            await self.client.disconnect()
            raise ConfigEntryAuthFailed(str(err)) from err
        except PJLinkError as err:
            await self.client.disconnect()
            raise UpdateFailed(str(err)) from err

    async def _async_update_data(self) -> ProjectorStatus:
        try:
            status = await self.client.fetch_status()
            if not self.info.inputs and status.power is PowerState.ON:
                # Some projectors only list their inputs while running.
                self.info.inputs = await self.client.fetch_inputs()
        except PJLinkAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PJLinkError as err:
            raise UpdateFailed(str(err)) from err
        finally:
            # Don't sit on the session: many projectors accept only one
            # controller at a time.
            await self.client.disconnect()

        in_transition = status.power in (PowerState.WARMING, PowerState.COOLING)
        self.update_interval = (
            min(self._base_interval, timedelta(seconds=TRANSITION_SCAN_INTERVAL))
            if in_transition
            else self._base_interval
        )
        return status

    async def async_execute(
        self, action: Callable[[PJLinkClient], Awaitable[Any]], *, refresh: bool = True
    ) -> Any:
        """Run a command against the projector and surface errors to the user."""
        try:
            result = await action(self.client)
        except PJLinkAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"PJLink authentication failed: {err}") from err
        except PJLinkUnavailableError as err:
            raise HomeAssistantError(
                f"The projector cannot do that right now ({err.command}). "
                "It is probably in standby, warming up or cooling down."
            ) from err
        except PJLinkUnsupportedError as err:
            raise HomeAssistantError(
                f"This projector does not support the {err.command} command."
            ) from err
        except PJLinkParameterError as err:
            raise HomeAssistantError(
                f"The projector rejected the value sent with {err.command}."
            ) from err
        except PJLinkCommandError as err:
            raise HomeAssistantError(f"Projector error: {err}") from err
        except PJLinkError as err:
            raise HomeAssistantError(f"Cannot reach the projector: {err}") from err
        finally:
            await self.client.disconnect()
        if refresh:
            # Not async_request_refresh(): that one is debounced for 10 s, which
            # would leave the UI showing the old state after a second command.
            await self.async_refresh()
        return result

    @callback
    def async_handle_notification(self, command: str, value: str) -> None:
        """Apply a Class 2 status notification (UDP push)."""
        if self.data is None:
            return
        status = replace(self.data)
        if command == "POWR" and value in POWER_STATES:
            status.power = POWER_STATES[value]
        elif command == "INPT" and len(value) == 2:
            status.input = value.upper()
        elif command == "ERST" and len(value) >= len(ERROR_CATEGORIES):
            status.errors = {
                name: ERROR_LEVELS.get(digit, ErrorLevel.ERROR)
                for name, digit in zip(ERROR_CATEGORIES, value)
            }
        elif command != "LKUP":
            return
        _LOGGER.debug("%s: notification %s=%s", self.name, command, value)
        if command != "LKUP":
            self.async_set_updated_data(status)
        # Whatever changed, the rest (mute, freeze, resolution...) may have too.
        self.hass.async_create_task(self.async_request_refresh())
