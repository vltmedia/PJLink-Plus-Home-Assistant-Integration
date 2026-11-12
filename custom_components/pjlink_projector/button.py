"""Buttons: volume steps (PJLink Class 2 only has up/down, no absolute level)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PJLinkConfigEntry, PJLinkCoordinator
from .entity import PJLinkEntity
from .pjlink import PJLinkClient

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PJLinkButtonDescription(ButtonEntityDescription):
    """Describe a PJLink button."""

    press: Callable[[PJLinkClient], Awaitable[Any]]


BUTTONS: tuple[PJLinkButtonDescription, ...] = (
    PJLinkButtonDescription(
        key="volume_up", translation_key="volume_up", press=lambda c: c.speaker_volume(True)
    ),
    PJLinkButtonDescription(
        key="volume_down", translation_key="volume_down", press=lambda c: c.speaker_volume(False)
    ),
    PJLinkButtonDescription(
        key="mic_volume_up",
        translation_key="mic_volume_up",
        press=lambda c: c.microphone_volume(True),
        entity_registry_enabled_default=False,
    ),
    PJLinkButtonDescription(
        key="mic_volume_down",
        translation_key="mic_volume_down",
        press=lambda c: c.microphone_volume(False),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PJLinkConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the buttons (Class 2 projectors only)."""
    coordinator = entry.runtime_data
    if coordinator.info.pjlink_class >= 2:
        async_add_entities(PJLinkButton(coordinator, d) for d in BUTTONS)


class PJLinkButton(PJLinkEntity, ButtonEntity):
    """A volume step button."""

    entity_description: PJLinkButtonDescription

    def __init__(
        self, coordinator: PJLinkCoordinator, description: PJLinkButtonDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Send the step."""
        await self.coordinator.async_execute(self.entity_description.press, refresh=False)
