# Installation

PJLink Plus needs Home Assistant 2025.1 or newer.

## With HACS

1. Open **HACS**, choose the menu in the top right, then **Custom repositories**.
2. Add `https://github.com/vltmedia/PJLink-Plus-Home-Assistant-Integration` with the type **Integration**.
3. Search for **PJLink Plus** in HACS and download it.
4. Restart Home Assistant.

## Manually

1. Download the repository (the green **Code** button on GitHub, then
   **Download ZIP**) and unpack it.
2. Copy the folder `custom_components/pjlink_projector` into the
   `custom_components` folder of your Home Assistant configuration, so that you
   end up with:

    ```text
    config/
      configuration.yaml
      custom_components/
        pjlink_projector/
          __init__.py
          manifest.json
          ...
    ```

    Create `custom_components` if it does not exist yet.

3. Restart Home Assistant. A new custom integration is only picked up by a
   full restart, not by reloading the configuration.

!!! tip "Where is my configuration folder?"
    - Home Assistant OS / Supervised: the `config` share of the Samba add-on,
      or `/config` in the Studio Code Server or SSH add-ons.
    - Docker: the host folder mounted to `/config` in the container.
    - Python virtual environment: usually `~/.homeassistant`.

## After the restart

Refresh the browser (Ctrl+F5), then continue with
[Adding a projector](setup.md).

## Updating

With HACS, updates appear under **Settings → Updates**. For a manual install,
replace the `pjlink_projector` folder with the new one and restart.

## Removing

Delete the projector under **Settings → Devices & services → PJLink Plus**,
then remove the integration in HACS or delete the `pjlink_projector` folder,
and restart.
