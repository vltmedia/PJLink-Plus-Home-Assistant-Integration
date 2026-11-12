"""Config flow: find projectors on the LAN or add one by address."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import network
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import selector

from . import async_get_udp
from .const import (
    CONF_MAC,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .pjlink import (
    DEFAULT_PORT,
    DiscoveredProjector,
    PJLinkAuthError,
    PJLinkClient,
    PJLinkConnectionError,
    PJLinkError,
    ProjectorInfo,
    discover,
)

_LOGGER = logging.getLogger(__name__)

_MANUAL = "__manual__"
_PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)
_PORT_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(min=1, max=65535, mode=selector.NumberSelectorMode.BOX)
)


def _connection_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)): selector.TextSelector(),
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): _PORT_SELECTOR,
            vol.Optional(CONF_PASSWORD): _PASSWORD_SELECTOR,
        }
    )


class PJLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle adding a projector."""

    VERSION = 1

    def __init__(self) -> None:
        self._scan_task: asyncio.Task[list[DiscoveredProjector]] | None = None
        self._discovered: dict[str, DiscoveredProjector] = {}
        self._selected: DiscoveredProjector | None = None
        self._nothing_found = False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Return the options flow."""
        return PJLinkOptionsFlow()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def _async_probe(
        self, host: str, port: int, password: str | None, mac: str | None = None
    ) -> tuple[ProjectorInfo, str | None]:
        """Connect, read the projector's identity and (if possible) its MAC."""
        client = PJLinkClient(host, port, password, timeout=DEFAULT_TIMEOUT)
        try:
            info = await client.fetch_info()
            # CLSS/NAME could in theory all be refused; POWR is mandatory and
            # makes sure a wrong password is noticed here rather than later.
            await client.get_power()
            address = client.peer_ip or host
        finally:
            await client.disconnect()
        if mac is None and info.pjlink_class >= 2:
            try:
                udp = await async_get_udp(self.hass)
                mac = (await udp.search([address], timeout=1.5)).get(address)
            except OSError as err:
                _LOGGER.debug("MAC lookup for %s failed: %s", host, err)
        return info, mac

    async def _async_try(
        self, data: dict[str, Any], mac: str | None = None
    ) -> tuple[dict[str, str], ProjectorInfo | None, str | None]:
        """Probe and translate failures into form errors."""
        try:
            info, mac = await self._async_probe(
                data[CONF_HOST], data[CONF_PORT], data.get(CONF_PASSWORD), mac
            )
        except PJLinkAuthError as err:
            return {"base": "password_required" if err.password_missing else "invalid_auth"}, None, mac
        except PJLinkConnectionError:
            return {"base": "cannot_connect"}, None, mac
        except PJLinkError:
            return {"base": "not_pjlink"}, None, mac
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error talking to %s", data[CONF_HOST])
            return {"base": "unknown"}, None, mac
        return {}, info, mac

    async def _async_create(
        self, data: dict[str, Any], info: ProjectorInfo, mac: str | None
    ) -> ConfigFlowResult:
        unique_id = mac or info.serial or f"{data[CONF_HOST]}:{data[CONF_PORT]}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: data[CONF_HOST]})
        entry_data = {
            CONF_HOST: data[CONF_HOST],
            CONF_PORT: data[CONF_PORT],
            CONF_PASSWORD: data.get(CONF_PASSWORD),
            CONF_MAC: mac,
        }
        return self.async_create_entry(title=info.display_name, data=entry_data)

    @staticmethod
    def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
        return {
            CONF_HOST: str(user_input[CONF_HOST]).strip(),
            CONF_PORT: int(user_input.get(CONF_PORT, DEFAULT_PORT)),
            CONF_PASSWORD: user_input.get(CONF_PASSWORD) or None,
        }

    # ------------------------------------------------------------------ #
    # Adding
    # ------------------------------------------------------------------ #

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask how to find the projector."""
        return self.async_show_menu(step_id="user", menu_options=["scan", "manual"])

    async def _async_scan(self) -> list[DiscoveredProjector]:
        adapters = await network.async_get_adapters(self.hass)
        networks = [
            f"{ip['address']}/{ip['network_prefix']}"
            for adapter in adapters
            if adapter["enabled"]
            for ip in adapter["ipv4"]
        ]
        broadcasts = {
            str(addr) for addr in await network.async_get_ipv4_broadcast_addresses(self.hass)
        } | {"255.255.255.255"}
        try:
            udp = await async_get_udp(self.hass)
        except OSError:
            udp = None
        return await discover(udp, broadcasts, networks)

    async def async_step_scan(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Search the network, showing a spinner meanwhile."""
        if self._scan_task is None:
            self._scan_task = self.hass.async_create_task(self._async_scan())
        if not self._scan_task.done():
            return self.async_show_progress(
                step_id="scan", progress_action="scan", progress_task=self._scan_task
            )
        try:
            found = self._scan_task.result()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("PJLink network scan failed")
            found = []
        finally:
            self._scan_task = None

        configured_hosts = {e.data.get(CONF_HOST) for e in self._async_current_entries()}
        configured_ids = {e.unique_id for e in self._async_current_entries()}
        self._discovered = {
            p.host: p
            for p in found
            if p.host not in configured_hosts
            and not ({p.mac, p.serial} - {None}) & configured_ids
        }
        self._nothing_found = not self._discovered
        return self.async_show_progress_done(
            next_step_id="manual" if self._nothing_found else "pick"
        )

    async def async_step_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose one of the projectors that were found."""
        if user_input is not None:
            choice = user_input["device"]
            if choice == _MANUAL:
                return await self.async_step_manual()
            self._selected = found = self._discovered[choice]
            data = {CONF_HOST: found.host, CONF_PORT: found.port, CONF_PASSWORD: None}
            if found.auth_required:
                return await self.async_step_auth()
            errors, info, mac = await self._async_try(data, found.mac)
            if info is not None:
                return await self._async_create(data, info, mac)
            if errors["base"] == "password_required":
                return await self.async_step_auth()
            return await self.async_step_manual(None, errors=errors, defaults=data)

        options = [
            selector.SelectOptionDict(value=host, label=found.label)
            for host, found in self._discovered.items()
        ]
        options.append(selector.SelectOptionDict(value=_MANUAL, label="Enter an address manually"))
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    vol.Required("device", default=options[0]["value"]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, mode=selector.SelectSelectorMode.LIST
                        )
                    )
                }
            ),
        )

    async def async_step_auth(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the password of a discovered projector."""
        assert self._selected is not None
        found = self._selected
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_HOST: found.host,
                CONF_PORT: found.port,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            errors, info, mac = await self._async_try(data, found.mac)
            if info is not None:
                return await self._async_create(data, info, mac)
        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR}),
            errors=errors,
            description_placeholders={"host": found.host},
        )

    async def async_step_manual(
        self,
        user_input: dict[str, Any] | None = None,
        *,
        errors: dict[str, str] | None = None,
        defaults: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Add a projector by host name or IP address."""
        errors = dict(errors or {})
        if user_input is not None:
            data = self._clean(user_input)
            self._async_abort_entries_match({CONF_HOST: data[CONF_HOST], CONF_PORT: data[CONF_PORT]})
            errors, info, mac = await self._async_try(data)
            if info is not None:
                return await self._async_create(data, info, mac)
            defaults = data
        elif self._nothing_found and not errors:
            errors["base"] = "no_devices_found"
            self._nothing_found = False
        return self.async_show_form(
            step_id="manual", data_schema=_connection_schema(defaults), errors=errors
        )

    # ------------------------------------------------------------------ #
    # Re-authentication and reconfiguration
    # ------------------------------------------------------------------ #

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The projector started refusing our password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            errors, info, _ = await self._async_try(data, entry.data.get(CONF_MAC))
            if info is not None:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR}),
            errors=errors,
            description_placeholders={"name": entry.title, "host": entry.data[CONF_HOST]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change address, port or password of an existing projector."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        defaults: Mapping[str, Any] = entry.data
        if user_input is not None:
            data = self._clean(user_input)
            if CONF_PASSWORD not in user_input:
                data[CONF_PASSWORD] = None
            errors, info, mac = await self._async_try(data, entry.data.get(CONF_MAC))
            if info is not None:
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, **data, CONF_MAC: mac}
                )
            defaults = data
        return self.async_show_form(
            step_id="reconfigure", data_schema=_connection_schema(defaults), errors=errors
        )


class PJLinkOptionsFlow(OptionsFlow):
    """Options: how often to poll."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )
