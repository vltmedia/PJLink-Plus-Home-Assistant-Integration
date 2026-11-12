# Entities

Each projector becomes one device. Entity IDs start with the projector's name,
shown here as `living_room_projector`.

"Class 2" marks entities that only exist on projectors that implement PJLink
Class 2. The projector's class is shown as the device's hardware version.

## Controls

| Entity | What it does | Notes |
| --- | --- | --- |
| `media_player.living_room_projector` | Power on / standby, input source, sound mute, volume up / down | Volume steps are Class 2. There is no absolute volume in PJLink. |
| `remote.living_room_projector_remote` | Sends named or raw commands; inputs are offered as activities | See [Remote and services](commands.md) |
| `select.living_room_projector_input` | Chooses the input | |
| `switch.living_room_projector_picture_mute` | Blanks the picture (AV mute / shutter) | Only available while the projector is on |
| `switch.living_room_projector_sound_mute` | Mutes the sound | Only available while the projector is on |
| `switch.living_room_projector_freeze` | Freezes the picture | Class 2 |
| `button.living_room_projector_volume_up` / `_down` | One speaker volume step | Class 2 |
| `button.living_room_projector_microphone_volume_up` / `_down` | One microphone volume step | Class 2, disabled by default |

The media player is **on** while the projector is lit or warming up and
**off** in standby or while cooling down. The exact state is in the
*Power status* sensor.

## Sensors

| Entity | Values | Notes |
| --- | --- | --- |
| `sensor.…_power_status` | Standby, Warming up, On, Cooling down | |
| `sensor.…_lamp_hours` | Hours | One per light source; named *Lamp 1 hours*, *Lamp 2 hours* on multi-lamp projectors |
| `sensor.…_filter_hours` | Hours | Class 2 |
| `sensor.…_input_resolution` | e.g. `1920x1080`, or *No signal* | Class 2 |
| `sensor.…_recommended_resolution` | e.g. `1920x1200` | Class 2, disabled by default |
| `sensor.…_fan_status`, `_lamp_status`, `_temperature_status`, `_cover_status`, `_filter_status`, `_other_status` | OK, Warning, Error | Diagnostic |
| `binary_sensor.…_problem` | On when any status above is not OK | The level of each category is in its attributes |

## Input names

Class 2 projectors report their own input names (for example `HDMI1`). Class 1
projectors only report a type and a number, which are shown as:

| Code | Name |
| --- | --- |
| `11`, `12`, … | RGB 1, RGB 2, … |
| `21`, `22`, … | Video 1, Video 2, … |
| `31`, `32`, … | Digital 1, Digital 2, … (HDMI, DVI, DisplayPort) |
| `41`, `42`, … | Storage 1, … (USB, card reader) |
| `51`, `52`, … | Network 1, … |
| `61`, `62`, … | Internal 1, … (Class 2) |

## Behaviour on particular projectors

- **Inputs unknown while off.** Many projectors only answer input questions
  while they are on, so the input select shows *unknown* in standby.
- **No "current input" answer.** Some projectors (seen on Optoma) refuse to say
  which input is active even when on. The input then stays *unknown*, but
  switching inputs still works.
- **No picture-only mute.** Some projectors (seen on Optoma) only have a
  combined picture-and-sound mute. On those, turning *Picture mute* on also
  turns *Sound mute* on.
- **Lamp sensors on laser projectors** report the light source's hours if the
  projector provides them, and are absent if it does not.
