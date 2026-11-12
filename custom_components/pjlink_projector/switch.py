"""Switches: picture mute, sound mute, freeze."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PJLinkConfigEntry, PJLinkCoordinator
from .entity import PJLinkEntity
from .pjlink import PJLinkClient, ProjectorStatus

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PJLinkSwitchDescription(SwitchEntityDescription):
    """Describe a PJLink switch."""

    value: Callable[[ProjectorStatus], bool | None]
    set_value: Callable[[PJLinkClient, bool], Awaitable[Any]]
    min_class: int = 1


SWITCHES: tuple[PJLinkSwitchDescription, ...] = (
    PJLinkSwitchDescription(
        key="video_mute",
        translation_key="video_mute",
        value=lambda s: s.video_mute,
        set_value=lambda c, on: c.set_av_mute(video=on),
    ),
    PJLinkSwitchDescription(
        key="audio_mute",
        translation_key="audio_mute",
        value=lambda s: s.audio_mute,
        set_value=lambda c, on: c.set_av_mute(audio=on),
    ),
    PJLinkSwitchDescription(
        key="freeze",
        translation_key="freeze",
        value=lambda s: s.freeze,
        set_value=lambda c, on: c.set_freeze(on),
        min_class=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PJLinkConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        PJLinkSwitch(coordinator, description)
        for description in SWITCHES
        if coordinator.info.pjlink_class >= description.min_class
    )


class PJLinkSwitch(PJLinkEntity, SwitchEntity):
    """A mute or freeze switch. Only usable while the projector is on."""

    entity_description: PJLinkSwitchDescription

    def __init__(
        self, coordinator: PJLinkCoordinator, description: PJLinkSwitchDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Mute and freeze only exist while the lamp is on."""
        return super().available and self.status.power == "on"

    @property
    def is_on(self) -> bool | None:
        """Current state."""
        return self.entity_description.value(self.status)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch on."""
        await self.coordinator.async_execute(
            lambda c: self.entity_description.set_value(c, True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch off."""
        await self.coordinator.async_execute(
            lambda c: self.entity_description.set_value(c, False)
        )
