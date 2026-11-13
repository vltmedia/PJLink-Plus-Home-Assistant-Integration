# PJLink Plus

A Home Assistant integration that finds and controls projectors over
[PJLink](https://pjlink.jbmia.or.jp/english/), the network control standard
built into most projectors from Epson, Panasonic, Sony, NEC/Sharp, Optoma,
BenQ, Christie, Maxell/Hitachi, Casio and others.

**Documentation: <https://vltmedia.github.io/PJLink-Plus-Home-Assistant-Integration/>**

## What it is

Home Assistant ships a basic *PJLink* integration that provides a media
player. PJLink Plus is a separate integration that covers the whole PJLink
standard (Class 1 and Class 2), is set up from the UI, can search the network
for projectors, and keeps working with projectors that refuse or do not
implement some commands. It uses its own domain, `pjlink_projector`, so it
does not conflict with the built-in one, and it needs no extra Python packages.

## Features

- **Network search**: PJLink Class 2 UDP search, plus a check of TCP port 4352
  on Home Assistant's local subnets so Class 1 projectors are found too
- **Media player**: power, input source, sound mute, volume steps
- **Remote**: named commands (`power_on`, `toggle_mute`, `input_hdmi1`, ...)
  or raw PJLink commands
- **Select and switches**: input, picture mute, sound mute, freeze
- **Sensors**: power status (standby / warming / on / cooling), lamp hours per
  lamp, filter hours, input resolution, and fan / lamp / temperature / cover /
  filter error status, with a combined *Problem* sensor
- **Class 2 extras**: freeze, speaker and microphone volume, projector-provided
  input names, serial number, firmware version, and instant updates pushed by
  the projector
- **Password authentication**, with a re-authentication prompt
- **Raw command action** (`pjlink_projector.send_command`) that returns the
  projector's answer
- **Reconfigure** address, port and password, and set the polling interval,
  from the UI

PJLink itself has no commands for the on-screen menu, arrow keys, keystone,
focus, zoom or absolute volume, so no PJLink integration can offer those. See
[What PJLink cannot do](https://vltmedia.github.io/PJLink-Plus-Home-Assistant-Integration/limitations/).

## Install

Needs Home Assistant 2025.1 or newer.

**With HACS**

1. HACS → menu → **Custom repositories** → add
   `https://github.com/vltmedia/PJLink-Plus-Home-Assistant-Integration` as an **Integration**.
2. Download **PJLink Plus** and restart Home Assistant.

**Manually**

1. Copy `custom_components/pjlink_projector` from this repository into the
   `custom_components` folder of your Home Assistant configuration.
2. Restart Home Assistant.

**Then**

1. On the projector, enable PJLink and network standby.
2. In Home Assistant go to **Settings → Devices & services → Add integration**
   and choose **PJLink Plus**.
3. Choose **Search the network**, or enter the projector's address.

More detail: [Installation](https://vltmedia.github.io/PJLink-Plus-Home-Assistant-Integration/installation/)
and [Adding a projector](https://vltmedia.github.io/PJLink-Plus-Home-Assistant-Integration/setup/).

## Documentation

| | |
| --- | --- |
| [Entities](https://vltmedia.github.io/PJLink-Plus-Home-Assistant-Integration/entities/) | Every entity and what it needs |
| [Remote and services](https://vltmedia.github.io/PJLink-Plus-Home-Assistant-Integration/commands/) | Command names, raw commands, PJLink reference |
| [Automation examples](https://vltmedia.github.io/PJLink-Plus-Home-Assistant-Integration/examples/) | Ready-to-adapt YAML |
| [Troubleshooting](https://vltmedia.github.io/PJLink-Plus-Home-Assistant-Integration/troubleshooting/) | Common problems and debug logging |
| [Development](https://vltmedia.github.io/PJLink-Plus-Home-Assistant-Integration/development/) | Layout, tests, simulated projector |

The documentation source is in [`docs/`](docs/) and is published by the
[Docs workflow](.github/workflows/docs.yml).
