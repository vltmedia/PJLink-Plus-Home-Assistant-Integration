# PJLink Plus

PJLink Plus is a Home Assistant integration that finds and controls projectors
over [PJLink](https://pjlink.jbmia.or.jp/english/), the network control standard
built into most projectors from Epson, Panasonic, Sony, NEC/Sharp, Optoma, BenQ,
Christie, Maxell/Hitachi, Casio and others.

It is set up entirely from the Home Assistant UI and needs no extra Python
packages.

## Features

- **Network search.** Finds projectors on your LAN: PJLink Class 2 projectors
  answer a UDP search, and Class 1 projectors are found by checking TCP port
  4352 across Home Assistant's local subnets.
- **Power, input and mute** through a media player, plus dedicated switch and
  select entities for dashboards and automations.
- **A remote entity** that accepts named commands (`power_on`, `toggle_mute`,
  `input_hdmi1`, ...) or raw PJLink commands.
- **Status sensors**: power state including warm-up and cool-down, lamp hours
  per lamp, filter hours, input resolution, and fan / lamp / temperature /
  cover / filter error status.
- **PJLink Class 2 extras**: freeze, speaker and microphone volume steps,
  projector-provided input names, serial number and firmware version, and
  instant updates pushed by the projector.
- **Password authentication**, with a re-authentication prompt if the password
  changes.
- **A raw command action** that returns the projector's answer, for anything
  not covered by an entity.
- **Tolerant of real projectors.** Commands a projector refuses or does not
  implement are skipped instead of making the device unavailable.

## How it differs from the built-in PJLink integration

Home Assistant ships an integration called *PJLink*. PJLink Plus is separate
and uses its own domain, `pjlink_projector`, so the two do not conflict. In
the *Add integration* list it appears as **PJLink Plus**.

| | Built-in PJLink | PJLink Plus |
| --- | --- | --- |
| Network search | No | Yes |
| Entities | Media player | Media player, remote, select, switches, buttons, sensors |
| Lamp hours, error status, power state sensors | No | Yes |
| PJLink Class 2 (freeze, volume, resolution, push updates) | No | Yes |
| Projector refuses the "current input" query | Entity becomes unavailable | Input shows as unknown, everything else keeps working |

## Next steps

1. [Install the integration](installation.md)
2. [Add your projector](setup.md)
3. Browse the [entities](entities.md) and [commands](commands.md)

!!! note "No menu or arrow keys"
    PJLink has no commands for the on-screen menu, navigation keys, keystone,
    focus or zoom. See [What PJLink cannot do](limitations.md).
