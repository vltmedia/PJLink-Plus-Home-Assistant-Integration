"""Select: input source."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PJLinkConfigEntry, PJLinkCoordinator
from .entity import PJLinkEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: PJLinkConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the input select."""
    async_add_entities([PJLinkInputSelect(entry.runtime_data)])


class PJLinkInputSelect(PJLinkEntity, SelectEntity):
    """Choose the projector input."""

    _attr_translation_key = "input"

    def __init__(self, coordinator: PJLinkCoordinator) -> None:
        super().__init__(coordinator, "input")

    @property
    def options(self) -> list[str]:
        """Names of the inputs."""
        return list(self.coordinator.info.inputs.values())

    @property
    def current_option(self) -> str | None:
        """Name of the active input."""
        code = self.status.input
        return self.coordinator.info.inputs.get(code) if code else None

    async def async_select_option(self, option: str) -> None:
        """Switch input."""
        code = self.coordinator.info.input_code(option)
        if code is None:
            raise ServiceValidationError(f"Unknown input: {option}")
        await self.coordinator.async_execute(lambda c: c.set_input(code))
