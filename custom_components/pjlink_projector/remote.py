"""Remote: send named PJLink commands, pick inputs as activities."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
import re
from typing import Any

from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PJLinkConfigEntry, PJLinkCoordinator
from .entity import PJLinkEntity
from .pjlink import PJLinkClient

PARALLEL_UPDATES = 1

type Action = Callable[[PJLinkClient], Awaitable[Any]]

# Named commands accepted by remote.send_command.
COMMANDS: dict[str, Action] = {
    "power_on": lambda c: c.set_power(True),
    "power_off": lambda c: c.set_power(False),
    "mute_on": lambda c: c.set_av_mute(video=True, audio=True),
    "mute_off": lambda c: c.set_av_mute(video=False, audio=False),
    "video_mute_on": lambda c: c.set_av_mute(video=True),
    "video_mute_off": lambda c: c.set_av_mute(video=False),
    "audio_mute_on": lambda c: c.set_av_mute(audio=True),
    "audio_mute_off": lambda c: c.set_av_mute(audio=False),
    "freeze_on": lambda c: c.set_freeze(True),
    "freeze_off": lambda c: c.set_freeze(False),
    "volume_up": lambda c: c.speaker_volume(True),
    "volume_down": lambda c: c.speaker_volume(False),
    "mic_volume_up": lambda c: c.microphone_volume(True),
    "mic_volume_down": lambda c: c.microphone_volume(False),
}
ALIASES = {
    "on": "power_on",
    "off": "power_off",
    "blank_on": "video_mute_on",
    "blank_off": "video_mute_off",
    "shutter_close": "video_mute_on",
    "shutter_open": "video_mute_off",
}
# "%1POWR 1", "%2FREZ 1" or "INPT 31": passed through untouched.
_RAW_RE = re.compile(r"^(?:%(?P<cls>[12]))?(?P<body>[A-Za-z0-9]{4})(?:\s+(?P<param>\S.*))?$")


async def async_setup_entry(
    hass: HomeAssistant, entry: PJLinkConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the remote."""
    async_add_entities([PJLinkRemote(entry.runtime_data)])


class PJLinkRemote(PJLinkEntity, RemoteEntity):
    """Remote control for a projector."""

    _attr_translation_key = "remote"
    _attr_supported_features = RemoteEntityFeature.ACTIVITY

    def __init__(self, coordinator: PJLinkCoordinator) -> None:
        super().__init__(coordinator, "remote")

    @property
    def is_on(self) -> bool | None:
        """True while lit or warming up."""
        return None if self.status.power is None else self.status.is_on

    @property
    def activity_list(self) -> list[str]:
        """Inputs double as activities."""
        return list(self.coordinator.info.inputs.values())

    @property
    def current_activity(self) -> str | None:
        """The active input."""
        return self.coordinator.info.input_name(self.status.input)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """List what send_command understands."""
        return {
            "commands": sorted(COMMANDS)
            + ["toggle_mute", "toggle_video_mute", "toggle_audio_mute", "toggle_freeze"]
            + [f"input_{code}" for code in self.coordinator.info.inputs]
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Power on; with an activity, switch to that input if already on."""
        activity = kwargs.get(ATTR_ACTIVITY)
        if not self.status.is_on:
            await self.coordinator.async_execute(lambda c: c.set_power(True))
        if activity and self.status.power == "on":
            await self.coordinator.async_execute(self._resolve(f"input_{activity}"))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Go to standby."""
        await self.coordinator.async_execute(lambda c: c.set_power(False))

    def _resolve(self, command: str) -> Action:
        """Turn a command string into something to run against the client."""
        key = command.strip().lower().replace(" ", "_").replace("-", "_")
        key = ALIASES.get(key, key)
        if key in COMMANDS:
            return COMMANDS[key]

        status = self.status
        toggles: dict[str, Action] = {
            "toggle_mute": lambda c: c.set_av_mute(
                video=not (status.video_mute and status.audio_mute),
                audio=not (status.video_mute and status.audio_mute),
            ),
            "toggle_video_mute": lambda c: c.set_av_mute(video=not status.video_mute),
            "toggle_audio_mute": lambda c: c.set_av_mute(audio=not status.audio_mute),
            "toggle_freeze": lambda c: c.set_freeze(not status.freeze),
            "toggle_power": lambda c: c.set_power(not status.is_on),
        }
        if key in toggles:
            return toggles[key]

        if key.startswith(("input_", "source_")):
            wanted = key.split("_", 1)[1]
            code = self.coordinator.info.input_code(wanted) or self.coordinator.info.input_code(
                wanted.replace("_", " ")
            )
            if code is None and re.fullmatch(r"[1-6][0-9A-Za-z]", wanted):
                code = wanted.upper()
            if code is None:
                raise ServiceValidationError(f"Unknown input: {wanted}")
            return lambda c: c.set_input(code)

        if match := _RAW_RE.match(command.strip()):
            body, param = match["body"], match["param"] or "?"
            cls = int(match["cls"] or 1)
            return lambda c: c.command(body, param, cls)

        raise ServiceValidationError(
            f"Unknown PJLink command '{command}'. See the 'commands' attribute "
            "of this entity, or send a raw command such as '%1AVMT 31'."
        )

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send one or more commands, optionally repeated."""
        repeats = kwargs.get(ATTR_NUM_REPEATS, 1)
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        actions = [self._resolve(item) for item in command]
        first = True
        try:
            for _ in range(repeats):
                for action in actions:
                    if not first:
                        await asyncio.sleep(delay)
                    first = False
                    await self.coordinator.async_execute(action, refresh=False)
        finally:
            await self.coordinator.async_refresh()
