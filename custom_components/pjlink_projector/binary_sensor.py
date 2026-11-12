"""Binary sensor: does the projector report any warning or error."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PJLinkConfigEntry, PJLinkCoordinator
from .entity import PJLinkEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: PJLinkConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the problem sensor."""
    if entry.runtime_data.data.errors:
        async_add_entities([PJLinkProblemSensor(entry.runtime_data)])


class PJLinkProblemSensor(PJLinkEntity, BinarySensorEntity):
    """On when any error category is at warning or error."""

    _attr_translation_key = "problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PJLinkCoordinator) -> None:
        super().__init__(coordinator, "problem")

    @property
    def is_on(self) -> bool | None:
        """True when something is wrong."""
        return self.status.has_problem if self.status.errors else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Level per category."""
        return {name: level.value for name, level in self.status.errors.items()}
