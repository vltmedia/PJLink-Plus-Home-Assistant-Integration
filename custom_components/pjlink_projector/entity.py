"""Base entity for PJLink projectors."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DOMAIN
from .coordinator import PJLinkCoordinator
from .pjlink import ProjectorStatus


class PJLinkEntity(CoordinatorEntity[PJLinkCoordinator]):
    """An entity that belongs to a projector."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PJLinkCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        info = coordinator.info
        self._attr_unique_id = f"{coordinator.unique_id}_{key}"
        mac = entry.data.get(CONF_MAC)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
            name=entry.title,
            manufacturer=info.manufacturer,
            model=info.model,
            serial_number=info.serial,
            sw_version=info.software_version,
            hw_version=f"PJLink Class {info.pjlink_class}",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def status(self) -> ProjectorStatus:
        """Latest polled status."""
        return self.coordinator.data
