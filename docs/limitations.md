# What PJLink cannot do

PJLink is a status-and-control standard shared by all manufacturers. It is not
a replacement for the infrared remote, and it deliberately covers only what
every projector has in common.

PJLink has **no commands** for:

- the on-screen menu, or the arrow, enter and back keys
- keystone, focus, zoom or lens shift
- picture mode, brightness, contrast, colour or aspect ratio
- absolute volume (Class 2 only has "one step up" and "one step down")
- lamp or laser power modes such as eco

Because the commands do not exist in the protocol, PJLink Plus cannot offer
them, and neither can any other PJLink integration. They are only reachable
through each manufacturer's own control protocol (for example Epson ESC/VP21,
Optoma's RS-232/Telnet commands, Sony ADCP or Panasonic NTControl) or through
an infrared blaster.

## Everything PJLink can do

| Capability | Class 1 | Class 2 |
| --- | --- | --- |
| Power on / standby, power status | Yes | Yes |
| Input switching and input list | Yes | Yes, with more input numbers |
| Picture mute, sound mute | Yes | Yes |
| Error status (fan, lamp, temperature, cover, filter, other) | Yes | Yes |
| Lamp hours | Yes | Yes |
| Name, manufacturer, model | Yes | Yes |
| Serial number, firmware version | | Yes |
| Input names from the projector | | Yes |
| Input and recommended resolution | | Yes |
| Filter hours, replacement part numbers | | Yes |
| Freeze | | Yes |
| Speaker and microphone volume steps | | Yes |
| Network search | | Yes |
| Status pushed by the projector | | Yes |

All of it is available in PJLink Plus, either as an entity or through the
[raw command action](commands.md#raw-commands-with-an-answer).
