"""PJLink Plus: discover and control PJLink Class 1/2 projectors."""

from __future__ import annotations

import ipaddress
import logging

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey

from .const import CONF_MAC, DEFAULT_TIMEOUT, DOMAIN, PLATFORMS
from .coordinator import PJLinkConfigEntry, PJLinkCoordinator
from .pjlink import DEFAULT_PORT, PJLinkClient, PJLinkUDP, normalize_mac

_LOGGER = logging.getLogger(__name__)

UDP_KEY: HassKey[PJLinkUDP] = HassKey(f"{DOMAIN}_udp")


async def async_get_udp(hass: HomeAssistant) -> PJLinkUDP:
    """Return the shared UDP socket (search + notifications), opening it once."""
    if (udp := hass.data.get(UDP_KEY)) is None:
        udp = hass.data[UDP_KEY] = PJLinkUDP()

        @callback
        def _stop(_: Event) -> None:
            udp.stop()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop)
    await udp.start()
    return udp


async def async_setup_entry(hass: HomeAssistant, entry: PJLinkConfigEntry) -> bool:
    """Set up one projector."""
    client = PJLinkClient(
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        entry.data.get(CONF_PASSWORD),
        timeout=DEFAULT_TIMEOUT,
    )
    coordinator = PJLinkCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    try:
        udp = await async_get_udp(hass)
    except OSError as err:
        _LOGGER.debug("PJLink UDP unavailable, polling only: %s", err)
    else:
        entry.async_on_unload(
            udp.add_listener(_notification_handler(hass, entry, coordinator))
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


def _notification_handler(
    hass: HomeAssistant, entry: PJLinkConfigEntry, coordinator: PJLinkCoordinator
):
    """Build the UDP listener for one projector."""
    mac = entry.data.get(CONF_MAC)

    @callback
    def _handle(source: str, command: str, value: str) -> None:
        own_ip = coordinator.client.peer_ip or entry.data[CONF_HOST]
        if source == own_ip:
            coordinator.async_handle_notification(command, value)
            return
        # "Link up" from our projector at a new address: follow it, but only
        # if we were configured by IP (a hostname takes care of itself).
        if command != "LKUP" or not mac or normalize_mac(value) != mac:
            return
        try:
            ipaddress.ip_address(entry.data[CONF_HOST])
        except ValueError:
            return
        _LOGGER.info("%s moved from %s to %s", entry.title, entry.data[CONF_HOST], source)
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_HOST: source}
        )

    return _handle


async def _async_reload_entry(hass: HomeAssistant, entry: PJLinkConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PJLinkConfigEntry) -> bool:
    """Unload one projector."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.disconnect()
    return unloaded
