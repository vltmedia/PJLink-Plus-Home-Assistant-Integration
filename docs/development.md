# Development

## Layout

```text
custom_components/pjlink_projector/
  pjlink/            PJLink protocol library, no Home Assistant imports
    client.py        TCP client: commands, authentication, reconnects
    udp.py           Class 2 UDP search and status notifications
    scan.py          Network search (UDP search + TCP sweep)
    models.py        Data classes and constants
    errors.py        Exceptions
  config_flow.py     Setup, search, reauthentication, reconfigure, options
  coordinator.py     Polling and push updates
  media_player.py, remote.py, select.py, switch.py, button.py,
  sensor.py, binary_sensor.py
tools/
  pjlink_cli.py      Command-line client for the protocol library
  fake_projector.py  Simulated projector (TCP + UDP)
tests/
docs/                This site
```

The `pjlink` package is self-contained and can be used on its own.

## Tests

The protocol tests need only the standard library:

```bash
python -m unittest tests.test_protocol
```

The Home Assistant tests run the config flow, entities and services against
the simulated projector:

```bash
pip install pytest-homeassistant-custom-component
```

```bash
pytest
```

## Simulated projector

```bash
python tools/fake_projector.py --class 2 --port 4352
```

It speaks PJLink over TCP, answers the UDP search and sends status
notifications. Add `--password secret` to test authentication and `--class 1`
for a Class 1 projector. Point the integration at the machine running it.

## Documentation

The site is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)
and published to GitHub Pages by the `Docs` workflow on every push to `main`
that touches `docs/` or `mkdocs.yml`.

```bash
pip install -r requirements-docs.txt
```

```bash
mkdocs serve
```

One-time repository setting: **Settings → Pages → Build and deployment →
Source: GitHub Actions**.
