"""Data models and constants for the PJLink protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

DEFAULT_PORT = 4352

# Order of the six digits in an ERST response.
ERROR_CATEGORIES: tuple[str, ...] = (
    "fan",
    "lamp",
    "temperature",
    "cover",
    "filter",
    "other",
)

# First character of an input code -> terminal type.
INPUT_TYPES: dict[str, str] = {
    "1": "RGB",
    "2": "Video",
    "3": "Digital",
    "4": "Storage",
    "5": "Network",
    "6": "Internal",
}

NO_SIGNAL = "No signal"


class PowerState(StrEnum):
    """Power status as reported by POWR."""

    STANDBY = "standby"
    ON = "on"
    COOLING = "cooling"
    WARMING = "warming"


POWER_STATES: dict[str, PowerState] = {
    "0": PowerState.STANDBY,
    "1": PowerState.ON,
    "2": PowerState.COOLING,
    "3": PowerState.WARMING,
}


class ErrorLevel(StrEnum):
    """Severity of one ERST category."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


ERROR_LEVELS: dict[str, ErrorLevel] = {
    "0": ErrorLevel.OK,
    "1": ErrorLevel.WARNING,
    "2": ErrorLevel.ERROR,
}


@dataclass(slots=True)
class Lamp:
    """One light source."""

    hours: int
    is_on: bool | None = None


def default_input_name(code: str) -> str:
    """Return a readable name for an input code such as '31' -> 'Digital 1'."""
    if len(code) != 2:
        return code
    kind = INPUT_TYPES.get(code[0])
    return f"{kind} {code[1]}" if kind else code


def model_name(manufacturer: str | None, product: str | None) -> str | None:
    """Join manufacturer and product without saying the brand twice."""
    if manufacturer and product and product.casefold().startswith(manufacturer.casefold()):
        return product
    return " ".join(p for p in (manufacturer, product) if p) or None


def friendly_name(name: str | None, manufacturer: str | None, product: str | None) -> str:
    """Pick a title: the projector's own name unless it is an unset placeholder."""
    if name and name.strip("0 -_"):
        return name
    return model_name(manufacturer, product) or "PJLink projector"


@dataclass(slots=True)
class ProjectorInfo:
    """Things that do not change while the projector runs."""

    pjlink_class: int = 1
    name: str | None = None
    manufacturer: str | None = None
    product: str | None = None
    other_info: str | None = None
    serial: str | None = None
    software_version: str | None = None
    recommended_resolution: str | None = None
    lamp_model: str | None = None
    filter_model: str | None = None
    # input code -> display name, in the order the projector lists them
    inputs: dict[str, str] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        """Title to show for this projector."""
        return friendly_name(self.name, self.manufacturer, self.product)

    @property
    def model(self) -> str | None:
        """Model string without a duplicated brand."""
        return self.product or self.other_info

    def input_name(self, code: str | None) -> str | None:
        """Display name for an input code."""
        if code is None:
            return None
        return self.inputs.get(code) or default_input_name(code)

    def input_code(self, name: str) -> str | None:
        """Input code for a display name (or for a literal code)."""
        wanted = name.strip().casefold()
        for code, label in self.inputs.items():
            if label.casefold() == wanted or code.casefold() == wanted:
                return code
        return None


@dataclass(slots=True)
class ProjectorStatus:
    """Things that change while the projector runs."""

    power: PowerState | None = None
    input: str | None = None
    video_mute: bool | None = None
    audio_mute: bool | None = None
    freeze: bool | None = None
    errors: dict[str, ErrorLevel] = field(default_factory=dict)
    lamps: list[Lamp] = field(default_factory=list)
    filter_hours: int | None = None
    input_resolution: str | None = None

    @property
    def is_on(self) -> bool:
        """True when the projector is lit or about to be."""
        return self.power in (PowerState.ON, PowerState.WARMING)

    @property
    def has_problem(self) -> bool:
        """True when any ERST category is not OK."""
        return any(level is not ErrorLevel.OK for level in self.errors.values())


@dataclass(slots=True)
class DiscoveredProjector:
    """A projector found on the network."""

    host: str
    port: int = DEFAULT_PORT
    mac: str | None = None
    auth_required: bool | None = None
    name: str | None = None
    manufacturer: str | None = None
    product: str | None = None
    pjlink_class: int | None = None
    serial: str | None = None

    @property
    def label(self) -> str:
        """One-line description for pickers."""
        model = model_name(self.manufacturer, self.product)
        title = friendly_name(self.name, self.manufacturer, self.product)
        if model and model != title:
            title = f"{title} - {model}"
        suffix = ", password required" if self.auth_required else ""
        return f"{title} ({self.host}{suffix})"
