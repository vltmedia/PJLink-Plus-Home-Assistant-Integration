# Remote and services

## Remote commands

The remote entity accepts one or more commands through `remote.send_command`.

```yaml
action: remote.send_command
target:
  entity_id: remote.living_room_projector_remote
data:
  command:
    - power_on
```

| Command | Effect |
| --- | --- |
| `power_on`, `power_off`, `toggle_power` | Power (`on` and `off` also work) |
| `mute_on`, `mute_off`, `toggle_mute` | Picture and sound together |
| `video_mute_on`, `video_mute_off`, `toggle_video_mute` | Picture only (`blank_on` / `blank_off` and `shutter_close` / `shutter_open` also work) |
| `audio_mute_on`, `audio_mute_off`, `toggle_audio_mute` | Sound only |
| `freeze_on`, `freeze_off`, `toggle_freeze` | Freeze the picture (Class 2) |
| `volume_up`, `volume_down` | One speaker volume step (Class 2) |
| `mic_volume_up`, `mic_volume_down` | One microphone volume step (Class 2) |
| `input_<code>` or `input_<name>` | Switch input, e.g. `input_31`, `input_hdmi1`, `input_digital_1` |
| `%1AVMT 31`, `%2FREZ 1`, `LAMP ?` | Any raw PJLink command; a command without `%1` / `%2` is sent as Class 1 |

The full list for a projector, including its input codes, is in the remote
entity's `commands` attribute.

`num_repeats` and `delay_secs` work as usual, which is handy for volume:

```yaml
action: remote.send_command
target:
  entity_id: remote.living_room_projector_remote
data:
  command: volume_up
  num_repeats: 5
  delay_secs: 0.2
```

`remote.turn_on` powers the projector on. Inputs are exposed as activities, so
`remote.turn_on` with an `activity` switches to that input when the projector
is already on.

## Raw commands with an answer

`pjlink_projector.send_command` sends one PJLink command to a media player and
returns what the projector said.

```yaml
action: pjlink_projector.send_command
target:
  entity_id: media_player.living_room_projector
data:
  command: LAMP
response_variable: answer
```

`answer["media_player.living_room_projector"].response` then holds, for
example, `4175 1`.

| Field | Meaning | Default |
| --- | --- | --- |
| `command` | Four-letter PJLink command | required |
| `parameter` | Value to set, or `?` to query | `?` |
| `pjlink_class` | `1` or `2` | `1` |

### PJLink command reference

| Command | Class | Query answer | Set parameter |
| --- | --- | --- | --- |
| `POWR` | 1 | `0` standby, `1` on, `2` cooling, `3` warming | `0` off, `1` on |
| `INPT` | 1 | Input code, e.g. `31` | Input code |
| `AVMT` | 1 | `11` picture muted, `21` sound muted, `31` both, `30` none | `10`/`11` picture, `20`/`21` sound, `30`/`31` both |
| `ERST` | 1 | Six digits: fan, lamp, temperature, cover, filter, other (`0` ok, `1` warning, `2` error) | |
| `LAMP` | 1 | Hours and on/off for each lamp, e.g. `4175 1` | |
| `INST` | 1 | Available input codes | |
| `NAME`, `INF1`, `INF2`, `INFO` | 1 | Projector name, manufacturer, model, other information | |
| `CLSS` | 1 | `1` or `2` | |
| `SNUM`, `SVER` | 2 | Serial number, firmware version | |
| `INNM` | 2 | Name of an input; parameter `?31` | |
| `IRES`, `RRES` | 2 | Input resolution, recommended resolution | |
| `FILT` | 2 | Filter hours | |
| `RLMP`, `RFIL` | 2 | Replacement lamp and filter model numbers | |
| `SVOL`, `MVOL` | 2 | | `1` up, `0` down |
| `FREZ` | 2 | `0` or `1` | `0` release, `1` freeze |

## Errors you may see

| Message | Meaning |
| --- | --- |
| The projector cannot do that right now | The projector is in standby, warming up or cooling down. Input, mute and freeze only work while it is on. |
| This projector does not support the … command | The projector does not implement it, often a Class 2 command on a Class 1 projector. |
| The projector rejected the value sent with … | The value is out of range, for example an input the projector does not have. |
| Cannot reach the projector | Network problem, or the projector is fully powered off. |
