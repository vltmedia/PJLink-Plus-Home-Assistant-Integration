"""Sensors: power status, lamp and filter hours, resolution, error status."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import PJLinkConfigEntry, PJLinkCoordinator
from .entity import PJLinkEntity
from .pjlink import ERROR_CATEGORIES, ErrorLevel, PowerState

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PJLinkSensorDescription(SensorEntityDescription):
    """Describe a PJLink sensor."""

    value: Callable[[PJLinkCoordinator], StateType]


def _lamp_hours(index: int) -> Callable[[PJLinkCoordinator], StateType]:
    def _value(coordinator: PJLinkCoordinator) -> StateType:
        lamps = coordinator.data.lamps
        return lamps[index].hours if index < len(lamps) else None

    return _value


def _error_level(category: str) -> Callable[[PJLinkCoordinator], StateType]:
    return lambda coordinator: coordinator.data.errors.get(category)


async def async_setup_entry(
    hass: HomeAssistant, entry: PJLinkConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors this projector can actually fill."""
    coordinator = entry.runtime_data
    status, info = coordinator.data, coordinator.info

    descriptions: list[PJLinkSensorDescription] = [
        PJLinkSensorDescription(
            key="power_status",
            translation_key="power_status",
            device_class=SensorDeviceClass.ENUM,
            options=[state.value for state in PowerState],
            value=lambda c: c.data.power,
        )
    ]
    for index in range(len(status.lamps)):
        single = len(status.lamps) == 1
        descriptions.append(
            PJLinkSensorDescription(
                key=f"lamp_{index + 1}_hours",
                translation_key="lamp_hours" if single else "lamp_n_hours",
                translation_placeholders=None if single else {"number": str(index + 1)},
                device_class=SensorDeviceClass.DURATION,
                native_unit_of_measurement=UnitOfTime.HOURS,
                state_class=SensorStateClass.TOTAL_INCREASING,
                entity_category=EntityCategory.DIAGNOSTIC,
                value=_lamp_hours(index),
            )
        )
    if status.errors:
        descriptions.extend(
            PJLinkSensorDescription(
                key=f"{category}_status",
                translation_key=f"{category}_status",
                device_class=SensorDeviceClass.ENUM,
                options=[level.value for level in ErrorLevel],
                entity_category=EntityCategory.DIAGNOSTIC,
                value=_error_level(category),
            )
            for category in ERROR_CATEGORIES
        )
    if info.pjlink_class >= 2:
        descriptions.append(
            PJLinkSensorDescription(
                key="input_resolution",
                translation_key="input_resolution",
                value=lambda c: c.data.input_resolution,
            )
        )
        if info.recommended_resolution:
            descriptions.append(
                PJLinkSensorDescription(
                    key="recommended_resolution",
                    translation_key="recommended_resolution",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    value=lambda c: c.info.recommended_resolution,
                )
            )
        if status.filter_hours is not None:
            descriptions.append(
                PJLinkSensorDescription(
                    key="filter_hours",
                    translation_key="filter_hours",
                    device_class=SensorDeviceClass.DURATION,
                    native_unit_of_measurement=UnitOfTime.HOURS,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    value=lambda c: c.data.filter_hours,
                )
            )

    async_add_entities(PJLinkSensor(coordinator, d) for d in descriptions)


class PJLinkSensor(PJLinkEntity, SensorEntity):
    """A projector reading."""

    entity_description: PJLinkSensorDescription

    def __init__(
        self, coordinator: PJLinkCoordinator, description: PJLinkSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Current value."""
        return self.entity_description.value(self.coordinator)
