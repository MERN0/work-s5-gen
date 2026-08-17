"""Automotive-domain prompt add-ons, keyed by a normalized domain name.

`registry.py::resolve_prompt` appends the matching block to every agent's
system prompt when `Swe6Config.domain` names one of these - pure contextual
grounding (what this kind of software typically does, what its tests
typically hinge on). Deliberately never includes actual function/API/error-
code names: those still only ever come from the project's own supporting-doc
context, per the "no hallucinated signal" rule the other prompts already
enforce - this only orients the model on what to look for.

Framed at the *software* level (function/API/return-code/error-code, module
state), not the system/vehicle level sys5's version of this file uses
(switch/CAN command, vehicle behavior) - the same six subsystem domains show
up at both levels, but what a good test case needs to get right differs: a
SYS5 BCM test cares about the CAN message a button press produces, a SWE6
BCM test cares about the return code the debounce function produces for the
same input.
"""
from __future__ import annotations

DOMAIN_PROMPTS: dict[str, str] = {
    "bcm": """\
Domain: Body Control Module (BCM) software - the embedded logic driving body \
electrical functions (lighting, door locks, windows, wipers, keyless entry, \
alarm/immobilizer) from switch, CAN, and LIN inputs. Typical things a BCM \
software test case needs to get right: which input flag, message handler, or \
API call triggers the function under test, any debounce/timing/interlock \
logic implemented in code (state-machine guards, timers, a door-open \
interlock on a window/lock function) that must be driven into the right \
state first, and the specific output variable, return code, or outbound \
message the function produces - not just that it was called.\
""",
    "adas": """\
Domain: Advanced Driver Assistance Systems (ADAS) software - the perception/ \
fusion/planning/actuation software behind functions such as adaptive cruise \
control, lane keep/centering, forward collision warning/AEB, blind spot \
monitoring, and parking assist. Typical things an ADAS software test case \
needs to get right: the input data or state the function under test consumes \
(a sensor-fusion output structure, a tracked-object list, an enable flag) \
that must be set as an explicit precondition - never assume a perception \
result the requirement or context doesn't define - the specific algorithm/ \
interface call under test, and a verifiable output value, actuation command, \
or warning flag it produces.\
""",
    "telematics": """\
Domain: Telematics software - connectivity and remote-vehicle command \
handling: cellular/Bluetooth/Wi-Fi connection management, remote command \
handlers (lock/unlock, remote start, find-my-car), eCall/bCall, OTA update \
handling, and backend data upload. Typical things a telematics software test \
case needs to get right: the connectivity/session-state precondition (a \
connection-state variable, a paired/unpaired flag) the function under test \
requires, the specific message handler or API call under test, and a \
verifiable response code, state transition, or outbound message it produces \
- including the degraded/no-connectivity path if the requirement defines one.\
""",
    "range_polygon": """\
Domain: Range/Polygon estimation software - the calculation logic behind EV \
(or fuel) driving-range prediction, including "range polygon"-style \
reachable-area estimation from state of charge/fuel, terrain, and driving \
conditions. Typical things a test case in this domain needs to get right: \
the input state struct or parameters (SoC/fuel level, consumption rate, \
HVAC/auxiliary load, terrain or route data) the calculation function under \
test consumes, the specific recalculation trigger (a function call, an event \
handler, a periodic task) under test, and a checkable return value or output \
field on the estimated range/reachable-area - not just that the function ran.\
""",
    "chassis": """\
Domain: Chassis control software - braking, steering, suspension, and \
stability/traction control logic (ABS, ESC/ESP, EPS, active suspension). \
Typical things a chassis software test case needs to get right: the input \
state (wheel-speed values, steering-angle input, a slip-ratio calculation) \
that puts the function under test into the relevant operating regime, the \
specific control/decision function under test (e.g. a lock-up detection or \
torque-correction routine), and a checkable output value or command \
(modulated brake-pressure command, corrective-torque value, fault code) it \
produces - never assume a road/tire condition beyond what's given.\
""",
    "powertrain": """\
Domain: Powertrain control software - engine/motor, transmission, and \
energy-management logic (ICE, EV drive unit, hybrid control, battery \
management). Typical things a powertrain software test case needs to get \
right: the input state (gear-request value, drive-mode flag, SoC/temperature \
reading) that puts the function under test in the right operating mode, the \
specific command-handling or protection function under test (torque-request \
arbitration, shift logic, a thermal-derate routine), and a checkable output \
value or protective action (a delivered-torque value, a derate/shutdown \
flag, a fault code) it produces - only reference limits/thresholds actually \
present in the supplied supporting context.\
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
    """Normalizes a free-text `Swe6Config.domain` value and returns its
    prompt add-on, or None if it's blank or doesn't match a known
    automotive domain - unrecognized domains are silently a no-op, never an
    error, since `domain` is caller-supplied free text.
    """
    if not domain:
        return None
    key = _DOMAIN_ALIASES.get(domain.strip().lower())
    return DOMAIN_PROMPTS.get(key) if key else None
