"""End-to-end tests: config flow, entities and services against a fake projector."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from custom_components.pjlink_projector import async_get_udp
from custom_components.pjlink_projector.const import DOMAIN
from custom_components.pjlink_projector.pjlink import DiscoveredProjector, PJLinkUDP

HOST = "127.0.0.1"
PLAYER = "media_player.test_projector"


@pytest.fixture(autouse=True)
async def _local_udp(hass: HomeAssistant):
    """Keep the shared UDP socket off the real network."""
    from custom_components.pjlink_projector import UDP_KEY

    udp = hass.data[UDP_KEY] = PJLinkUDP(port=0, bind_host=HOST)
    yield udp
    udp.stop()


async def _setup(hass: HomeAssistant, projector, password=None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Projector",
        unique_id="SN12345678",
        data={"host": HOST, "port": projector.port, "password": password, "mac": None},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _call(hass: HomeAssistant, domain: str, service: str, entity_id: str, **data):
    result = await hass.services.async_call(
        domain,
        service,
        {"entity_id": entity_id, **data},
        blocking=True,
        return_response=domain == DOMAIN,
    )
    await hass.async_block_till_done()
    return result


async def test_manual_flow(hass: HomeAssistant, projector) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] is FlowResultType.FORM

    # Nothing listens on port 1.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": 1}
    )
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": projector.port}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Projector"
    assert result["result"].unique_id == "SN12345678"
    await hass.async_block_till_done()

    # The same projector cannot be added twice.
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": projector.port}
    )
    assert result["type"] is FlowResultType.ABORT


async def test_password_flow(hass: HomeAssistant, projector) -> None:
    projector.password = "secret"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": projector.port}
    )
    assert result["errors"] == {"base": "password_required"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": projector.port, "password": "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "port": projector.port, "password": "secret"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["password"] == "secret"


async def test_scan_flow(hass: HomeAssistant, projector) -> None:
    found = [
        DiscoveredProjector(
            HOST, projector.port, mac="02:00:00:aa:bb:cc", auth_required=False, name="Test Projector"
        )
    ]
    with (
        patch("custom_components.pjlink_projector.config_flow.discover", return_value=found),
        patch(
            "custom_components.pjlink_projector.config_flow.network.async_get_adapters",
            return_value=[],
        ),
        patch(
            "custom_components.pjlink_projector.config_flow.network.async_get_ipv4_broadcast_addresses",
            return_value=set(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "scan"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pick"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": HOST}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "02:00:00:aa:bb:cc"
    assert result["data"]["mac"] == "02:00:00:aa:bb:cc"


async def test_entities_and_services(hass: HomeAssistant, projector) -> None:
    entry = await _setup(hass, projector)
    assert entry.state is ConfigEntryState.LOADED

    assert hass.states.get(PLAYER).state == "off"
    assert hass.states.get("sensor.test_projector_power_status").state == "standby"
    assert hass.states.get("sensor.test_projector_lamp_hours").state == "1234"
    assert hass.states.get("sensor.test_projector_filter_hours").state == "321"
    assert hass.states.get("binary_sensor.test_projector_problem").state == "off"
    assert hass.states.get("switch.test_projector_picture_mute").state == "unavailable"
    assert hass.states.get("select.test_projector_input").attributes["options"] == [
        "COMPUTER", "HDMI1", "HDMI2", "LAN",
    ]

    # Switching input in standby is refused by the projector, and says so.
    with pytest.raises(HomeAssistantError, match="standby"):
        await _call(hass, "select", "select_option", "select.test_projector_input", option="HDMI2")

    await _call(hass, "media_player", "turn_on", PLAYER)
    assert projector.power == "1"
    assert hass.states.get(PLAYER).state == "on"
    assert hass.states.get(PLAYER).attributes["source"] == "HDMI1"
    assert hass.states.get("sensor.test_projector_input_resolution").state == "1920x1080"

    await _call(hass, "media_player", "select_source", PLAYER, source="HDMI2")
    assert projector.input == "32"
    assert hass.states.get("select.test_projector_input").state == "HDMI2"

    await _call(hass, "switch", "turn_on", "switch.test_projector_picture_mute")
    assert projector.avmt == "11"
    await _call(hass, "media_player", "volume_mute", PLAYER, is_volume_muted=True)
    assert projector.avmt == "31"
    assert hass.states.get(PLAYER).attributes["is_volume_muted"] is True
    await _call(hass, "switch", "turn_on", "switch.test_projector_freeze")
    assert hass.states.get("switch.test_projector_freeze").state == "on"

    await _call(hass, "button", "press", "button.test_projector_volume_up")
    await _call(hass, "media_player", "volume_down", PLAYER)
    assert projector.received.count("%2SVOL 1") == 1
    assert projector.received.count("%2SVOL 0") == 1

    remote = "remote.test_projector_remote"
    assert hass.states.get(remote).attributes["current_activity"] == "HDMI2"
    await _call(
        hass, "remote", "send_command", remote,
        command=["mute_off", "toggle_freeze", "input_31", "%1AVMT 21"], delay_secs=0,
    )
    assert (projector.avmt, projector.freeze, projector.input) == ("21", "0", "31")
    with pytest.raises(HomeAssistantError):
        await _call(hass, "remote", "send_command", remote, command=["menu"])

    response = await _call(hass, DOMAIN, "send_command", PLAYER, command="lamp")
    assert response[PLAYER]["response"] == "1234 0"
    with pytest.raises(HomeAssistantError, match="does not support"):
        await _call(hass, DOMAIN, "send_command", PLAYER, command="ZZZZ")

    await _call(hass, "remote", "turn_off", remote)
    assert projector.power == "0"
    assert hass.states.get(PLAYER).state == "off"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_push_notification(hass: HomeAssistant, projector) -> None:
    entry = await _setup(hass, projector)
    udp = await async_get_udp(hass)
    # A status notification arriving from the projector's address.
    projector.power = "1"
    udp._handle(b"%2POWR=1\r", HOST)  # noqa: SLF001
    await hass.async_block_till_done()
    assert hass.states.get(PLAYER).state == "on"
    # ... and one from somebody else is ignored.
    udp._handle(b"%2POWR=0\r", "192.0.2.9")  # noqa: SLF001
    await hass.async_block_till_done()
    assert hass.states.get(PLAYER).state == "on"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_reauth_and_offline(hass: HomeAssistant, projector) -> None:
    entry = await _setup(hass, projector)
    projector.password = "changed"
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {"password": "changed"}
    )
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert entry.data["password"] == "changed"
    assert hass.states.get(PLAYER).state == "off"

    await projector.stop()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(PLAYER).state == "unavailable"


async def test_setup_retries_when_offline(hass: HomeAssistant, projector) -> None:
    await projector.stop()
    entry = await _setup(hass, projector)
    assert entry.state is ConfigEntryState.SETUP_RETRY
