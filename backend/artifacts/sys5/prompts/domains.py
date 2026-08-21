"""Automotive-domain prompt add-ons, keyed by a normalized domain name.

`registry.py::resolve_system_prompt` appends the matching block to every agent's
system prompt when `Sys5Config.domain` names one of these - pure contextual
grounding (what this kind of system typically does, what its tests
typically hinge on). Deliberately never includes actual signal/command
names: those still only ever come from the project's own supporting-doc
context, per the "no hallucinated signal" rule the other prompts already
enforce - this only orients the model on what to look for.
"""
from __future__ import annotations

DOMAIN_PROMPTS: dict[str, str] = {
    "bcm": """\
Domain: Body Control Module (BCM). This system arbitrates and drives body \
electrical functions - lighting (interior/exterior/turn indicators), door \
locks, windows, wipers, keyless entry, alarm/immobilizer, and similar \
comfort/convenience actuators - usually from switch inputs and CAN/LIN \
commands. Typical things a BCM test case needs to get right: which input \
(switch, remote, CAN command) triggers the behavior, any debounce/timing \
or interlock condition (e.g. a door-open interlock on a window/lock \
action), and the specific output state or fault flag that proves the \
behavior occurred - not just that a command was sent.\
""",
    "adas": """\
Domain: Advanced Driver Assistance Systems (ADAS) - functions such as \
adaptive cruise control, lane keep/centering, forward collision warning/ \
AEB, blind spot monitoring, and parking assist, built on sensor fusion \
(camera/radar/lidar/ultrasonic) and vehicle dynamics actuation. Typical \
things an ADAS test case needs to get right: the sensor/perception \
precondition that must hold for the function to be available (e.g. lane \
markings detected, target vehicle in range, system enabled with no \
faults), the specific triggering scenario (closing distance, lane \
departure angle, obstacle proximity), and a verifiable actuation or \
warning output - never assume a perception result; only reference one if \
it's part of the given supporting context.\
""",
    "telematics": """\
Domain: Telematics - connectivity and remote-vehicle functions: cellular/ \
Bluetooth/Wi-Fi connectivity, remote commands (lock/unlock, remote start, \
find-my-car), eCall/bCall, OTA update handling, and data upload to a \
backend. Typical things a telematics test case needs to get right: the \
connectivity precondition (signal present/absent, paired/unpaired, \
ignition state), the round-trip nature of remote commands (a command sent \
from outside the vehicle and a state change/acknowledgment observed on the \
vehicle, or vice versa), and behavior under degraded/no connectivity - \
don't assume a network response the requirement or context doesn't cover.\
""",
    "range_polygon": """\
Domain: Range/Polygon estimation - EV (or fuel) driving-range prediction, \
including "range polygon"-style reachable-area estimation from current \
state of charge/fuel, terrain, and driving conditions. Typical things a \
test case in this domain needs to get right: the input state (SoC/fuel \
level, consumption rate, HVAC/auxiliary load, terrain or route data) the \
estimate is computed from, the specific recalculation trigger (distance \
driven, time elapsed, mode change), and a checkable expected result on the \
estimated range value or displayed reachable-area update - not just that a \
recalculation "happened".\
""",
    "chassis": """\
Domain: Chassis - braking, steering, suspension, and stability/traction \
control systems (ABS, ESC/ESP, EPS, active suspension). Typical things a \
chassis test case needs to get right: the vehicle-dynamics precondition \
(speed, wheel slip, steering angle, load) that puts the system into the \
relevant operating regime, the specific triggering condition (e.g. wheel \
lock-up, understeer/oversteer threshold, road input), and a checkable \
actuator or diagnostic output (modulated brake pressure, corrective \
torque, fault code) - never assume a road/tire condition beyond what's \
given.\
""",
    "powertrain": """\
Domain: Powertrain - engine/motor, transmission, and energy management \
(ICE, EV drive unit, hybrid control, battery management). Typical things a \
powertrain test case needs to get right: the operating-mode precondition \
(gear, drive mode, engine/motor state, SoC/temperature limits), the \
specific command or event under test (torque request, gear shift, charge/ \
discharge command, thermal event), and a checkable output on delivered \
torque/speed/state or a protective action taken (derate, shutdown, fault \
flag) - only reference limits/thresholds actually present in the supplied \
supporting context.\
""",
}

# Free-text `domain` values this project has actually seen/expects, mapped
# onto the normalized keys above. Extend this, not DOMAIN_PROMPTS' keys
# directly, when a new spelling/abbreviation shows up in a real config.
_DOMAIN_ALIASES: dict[str, str] = {
    "bcm": "bcm",
    "body control module": "bcm",
    "body control": "bcm",
    "adas": "adas",
    "advanced driver assistance": "adas",
    "advanced driver assistance systems": "adas",
    "telematics": "telematics",
    "range polygon": "range_polygon",
    "range_polygon": "range_polygon",
    "range-polygon": "range_polygon",
    "range": "range_polygon",
    "polygon": "range_polygon",
    "chassis": "chassis",
    "powertrain": "powertrain",
    "power train": "powertrain",
}


def resolve_domain_prompt(domain: str) -> str | None:
    """Normalizes a free-text `Sys5Config.domain` value and returns its
    prompt add-on, or None if it's blank or doesn't match a known
    automotive domain - unrecognized domains are silently a no-op, never an
    error, since `domain` is caller-supplied free text.
    """
    if not domain:
        return None
    key = _DOMAIN_ALIASES.get(domain.strip().lower())
    return DOMAIN_PROMPTS.get(key) if key else None
