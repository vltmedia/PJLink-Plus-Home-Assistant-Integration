# Adding a projector

## Prepare the projector

In the projector's network menu:

- **Enable PJLink** (sometimes "network control" or "projector control").
- **Enable network standby** (also called "standby mode: normal", "LAN
  standby" or "network standby: on"). Without it the projector switches its
  network port off in standby, so it cannot be reached or powered on.
- Give the projector a **fixed IP address** or a DHCP reservation in your
  router.
- Note the **PJLink password** if authentication is enabled. Many projectors
  ship with authentication off.

## Add it in Home Assistant

Go to **Settings → Devices & services → Add integration** and choose
**PJLink Plus**. You are asked how to find the projector.

### Search the network

Home Assistant looks for projectors for a few seconds in two ways:

- It broadcasts the PJLink Class 2 search. Class 2 projectors answer with
  their MAC address.
- It tries TCP port 4352 on every address of Home Assistant's own subnets and
  keeps the ones that answer with a PJLink greeting. This is what finds
  Class 1 projectors, which cannot answer the search.

Pick a projector from the list. If it requires a password you are asked for it.
Projectors that are already set up are left out of the list; if nothing new is
found you are taken to the manual form.

!!! info "When the search finds nothing"
    - Subnets larger than /22 (more than 1022 addresses) are not swept.
    - Only subnets Home Assistant itself is connected to are swept. A projector
      on another VLAN has to be added by address.
    - The projector must be reachable while you search: powered on, or in
      standby with network standby enabled.

### Enter an address

Enter the host name or IP address, the port (4352 unless you changed it) and
the password if authentication is on.

## Changing settings later

On the integration's entry under **Settings → Devices & services**:

- **Reconfigure** changes the address, port or password.
- **Configure** changes the polling interval (default 15 seconds, 5 to 600).
  While the projector warms up or cools down it is polled every 3 seconds
  regardless.

If the projector starts rejecting the stored password, Home Assistant asks
for the new one.

## How updates arrive

Every projector is polled at the interval above. PJLink Class 2 projectors
additionally send a UDP notification when power, input or error status
changes, and those are applied immediately. Home Assistant must be able to
receive UDP on port 4352 for that. If it cannot (for example a Docker
container without host networking), everything still works by polling.
