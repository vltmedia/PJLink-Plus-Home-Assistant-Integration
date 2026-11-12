# Automation examples

Replace `living_room_projector` with your projector's entity name.

## Movie scene: power on, wait until ready, pick the input

Input commands are refused while the projector warms up, so wait for the power
status first.

```yaml
script:
  movie_time:
    sequence:
      - action: media_player.turn_on
        target:
          entity_id: media_player.living_room_projector
      - wait_for_trigger:
          - trigger: state
            entity_id: sensor.living_room_projector_power_status
            to: "on"
        timeout: "00:02:00"
      - action: select.select_option
        target:
          entity_id: select.living_room_projector_input
        data:
          option: "Digital 1"
```

## Blank the picture while the doorbell rings

```yaml
automation:
  - alias: Blank projector on doorbell
    triggers:
      - trigger: state
        entity_id: binary_sensor.doorbell
        to: "on"
    conditions:
      - condition: state
        entity_id: sensor.living_room_projector_power_status
        state: "on"
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.living_room_projector_picture_mute
      - delay: "00:00:30"
      - action: switch.turn_off
        target:
          entity_id: switch.living_room_projector_picture_mute
```

## Turn the projector off when nothing is connected

Needs a Class 2 projector for the input resolution sensor.

```yaml
automation:
  - alias: Projector off without signal
    triggers:
      - trigger: state
        entity_id: sensor.living_room_projector_input_resolution
        to: "No signal"
        for: "00:10:00"
    actions:
      - action: media_player.turn_off
        target:
          entity_id: media_player.living_room_projector
```

## Lamp replacement reminder

```yaml
automation:
  - alias: Projector lamp nearly worn
    triggers:
      - trigger: numeric_state
        entity_id: sensor.living_room_projector_lamp_hours
        above: 3500
    actions:
      - action: persistent_notification.create
        data:
          title: Projector lamp
          message: >-
            The lamp has run
            {{ states('sensor.living_room_projector_lamp_hours') }} hours.
```

## Notify on projector problems

```yaml
automation:
  - alias: Projector reports a problem
    triggers:
      - trigger: state
        entity_id: binary_sensor.living_room_projector_problem
        to: "on"
    actions:
      - action: persistent_notification.create
        data:
          title: Projector problem
          message: >-
            {% set s = state_attr('binary_sensor.living_room_projector_problem', 'temperature') %}
            Temperature status: {{ s }}. Check the other status sensors on the device page.
```
