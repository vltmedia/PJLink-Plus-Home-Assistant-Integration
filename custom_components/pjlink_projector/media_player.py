"""Media player: the projector itself."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_COMMAND,
    ATTR_PARAMETER,
    ATTR_PJLINK_CLASS,
    SERVICE_SEND_COMMAND,
)
from .coordinator import PJLinkConfigEntry, PJLinkCoordinator
from .entity import PJLinkEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: PJLinkConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the media player and the raw-command service."""
    async_add_entities([PJLinkMediaPlayer(entry.runtime_data)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {
            vol.Required(ATTR_COMMAND): vol.All(cv.string, vol.Length(min=4, max=4)),
            vol.Optional(ATTR_PARAMETER, default="?"): cv.string,
            vol.Optional(ATTR_PJLINK_CLASS, default=1): vol.All(vol.Coerce(int), vol.In([1, 2])),
        },
        "async_send_pjlink_command",
        supports_response=SupportsResponse.OPTIONAL,
    )


class PJLinkMediaPlayer(PJLinkEntity, MediaPlayerEntity):
    """Power, input and audio mute of a projector."""

    _attr_name = None
    # Only newer Home Assistant versions know a projector device class.
    _attr_device_class = getattr(MediaPlayerDeviceClass, "PROJECTOR", None)

    def __init__(self, coordinator: PJLinkCoordinator) -> None:
        super().__init__(coordinator, "media_player")
        features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.VOLUME_MUTE
        )
        if coordinator.info.pjlink_class >= 2:
            features |= MediaPlayerEntityFeature.VOLUME_STEP
        self._attr_supported_features = features

    @property
    def state(self) -> MediaPlayerState | None:
        """On while lit or warming up, off otherwise."""
        if self.status.power is None:
            return None
        return MediaPlayerState.ON if self.status.is_on else MediaPlayerState.OFF

    @property
    def source_list(self) -> list[str]:
        """Names of the inputs."""
        return list(self.coordinator.info.inputs.values())

    @property
    def source(self) -> str | None:
        """Name of the active input."""
        return self.coordinator.info.input_name(self.status.input)

    @property
    def is_volume_muted(self) -> bool | None:
        """True when the sound is muted."""
        return self.status.audio_mute

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra details."""
        return {
            "power_status": self.status.power,
            "input_code": self.status.input,
            "video_muted": self.status.video_mute,
            "frozen": self.status.freeze,
        }

    async def async_turn_on(self) -> None:
        """Power on."""
        await self.coordinator.async_execute(lambda c: c.set_power(True))

    async def async_turn_off(self) -> None:
        """Go to standby."""
        await self.coordinator.async_execute(lambda c: c.set_power(False))

    async def async_select_source(self, source: str) -> None:
        """Switch input by name or code."""
        code = self.coordinator.info.input_code(source)
        if code is None:
            raise ServiceValidationError(f"Unknown input: {source}")
        await self.coordinator.async_execute(lambda c: c.set_input(code))

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the sound."""
        await self.coordinator.async_execute(lambda c: c.set_av_mute(audio=mute))

    async def async_volume_up(self) -> None:
        """One step louder (Class 2)."""
        await self.coordinator.async_execute(lambda c: c.speaker_volume(True), refresh=False)

    async def async_volume_down(self) -> None:
        """One step quieter (Class 2)."""
        await self.coordinator.async_execute(lambda c: c.speaker_volume(False), refresh=False)

    async def async_send_pjlink_command(
        self, command: str, parameter: str = "?", pjlink_class: int = 1
    ) -> ServiceResponse:
        """Send any PJLink command and return the projector's answer."""
        response = await self.coordinator.async_execute(
            lambda c: c.command(command, parameter, pjlink_class),
            refresh=parameter.strip() != "?",
        )
        return {"command": command.upper(), "parameter": parameter, "response": response}
