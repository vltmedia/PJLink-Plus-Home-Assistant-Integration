# Troubleshooting

## PJLink Plus is not in the Add integration list

- The folder must be `config/custom_components/pjlink_projector` and contain
  `manifest.json` directly (not nested one level deeper).
- Home Assistant must be fully restarted after copying the folder.
- Refresh the browser with Ctrl+F5.
- The entry is called **PJLink Plus**. The entry called *PJLink* is Home
  Assistant's built-in integration.
- After the restart, the log should contain a line mentioning
  `custom integration pjlink_projector`. If it does not, the folder is in the
  wrong place.

## Could not connect

- PJLink is disabled on the projector, or its network port is off in standby
  (enable network standby).
- A firewall or VLAN blocks TCP port 4352 between Home Assistant and the
  projector.
- The projector is fully powered off at the mains.

## The search finds nothing

See [When the search finds nothing](setup.md#search-the-network). Adding the
projector by address always works if it is reachable.

## The projector becomes unavailable when powered on or off

Many projectors restart their network interface when they change power state
and are unreachable for some seconds. The entities return on the next
successful poll.

If you also have Home Assistant's built-in *PJLink* integration set up for the
same projector, remove it. Some projectors accept only one controller at a
time, and the built-in integration marks the projector unavailable when it
refuses the "current input" query.

## Input shows "unknown"

The projector does not answer the input query, either because it is in standby
or because the model never does. Switching inputs still works. See
[Behaviour on particular projectors](entities.md#behaviour-on-particular-projectors).

## Picture mute also mutes the sound

The projector has no picture-only mute, so the combined mute is used instead.

## "The projector cannot do that right now"

The projector is in standby, warming up or cooling down. Wait for the
*Power status* sensor to read *On*; the
[movie scene example](examples.md#movie-scene-power-on-wait-until-ready-pick-the-input)
shows how.

## Debug logging

Open the integration's entry and choose **Enable debug logging**, reproduce
the problem, then choose **Disable debug logging** to download the log. Or add
to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.pjlink_projector: debug
```

**Download diagnostics** on the same page gives a snapshot of what the
projector reported, with the password, MAC address and serial number removed.

## Test without Home Assistant

The repository contains a small command-line tool that uses the same PJLink
code as the integration:

```bash
python tools/pjlink_cli.py discover
```

```bash
python tools/pjlink_cli.py status 192.168.1.50
```

```bash
python tools/pjlink_cli.py raw 192.168.1.50 POWR ?
```

If these work but Home Assistant cannot reach the projector, the problem is
the network path from the Home Assistant host.
