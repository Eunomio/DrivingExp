"""
Scenario definitions for the Range Anxiety & System Trust experience script.

Each Scenario holds:
  - id            : unique identifier used in data logs
  - topic         : "range_anxiety" | "system_trust"
  - title         : short label shown to the participant
  - description   : the vignette / situation presented to the driver
  - probe         : the specific question asked after reading the vignette

Scenarios are grouped into two blocks:
  RANGE_ANXIETY_SCENARIOS  – focus on EV battery depletion concern
  SYSTEM_TRUST_SCENARIOS   – focus on reliance on / scepticism of driver-
                             assistance and autonomous features
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    topic: str
    title: str
    description: str
    probe: str


# ---------------------------------------------------------------------------
# Block 1 – Range Anxiety
# ---------------------------------------------------------------------------
RANGE_ANXIETY_SCENARIOS: list[Scenario] = [
    Scenario(
        id="RA_01",
        topic="range_anxiety",
        title="Highway Low-Battery Warning",
        description=(
            "You are driving your electric vehicle (EV) on a motorway, "
            "120 km from home.  The battery indicator drops to 15 % and a "
            "warning chime sounds.  Your navigation app shows that the nearest "
            "fast charger is 45 km away, but also estimates it will be "
            "occupied.  The outside temperature is −5 °C, which reduces "
            "battery efficiency by roughly 20 %."
        ),
        probe=(
            "How anxious do you feel about reaching the charging station "
            "before the battery runs out?"
        ),
    ),
    Scenario(
        id="RA_02",
        topic="range_anxiety",
        title="Unfamiliar Route with Closed Charger",
        description=(
            "You are on a business trip in an unfamiliar city.  Your EV has "
            "30 % battery remaining (estimated 80 km range).  You planned to "
            "charge at a hotel station, but on arrival you discover it is out "
            "of service.  The next available public charger is a 15-minute "
            "drive away, and you are uncertain of the exact route."
        ),
        probe=(
            "How confident are you that you can manage your battery range in "
            "this situation?"
        ),
    ),
    Scenario(
        id="RA_03",
        topic="range_anxiety",
        title="Unexpected Detour Affecting Range",
        description=(
            "Heavy traffic ahead forces your navigation system to suggest a "
            "detour that adds 35 km to your journey.  Your current range "
            "estimate is 120 km and your planned destination is 100 km away.  "
            "Accepting the detour would leave you with only a 10–15 km margin.  "
            "No public chargers are shown along the detour route."
        ),
        probe=(
            "How much concern does this detour cause you about reaching your "
            "destination safely?"
        ),
    ),
    Scenario(
        id="RA_04",
        topic="range_anxiety",
        title="Charging Queue on Long Trip",
        description=(
            "During a 400 km road trip you arrive at a motorway service-area "
            "charging hub with 8 % battery.  Six cars are already queuing and "
            "the estimated wait is 45 minutes.  Each charger provides ~120 km "
            "of range per 20 minutes.  Your next planned stop is 180 km away."
        ),
        probe=(
            "How stressful do you find this charging-queue situation compared "
            "with refuelling a conventional car?"
        ),
    ),
    Scenario(
        id="RA_05",
        topic="range_anxiety",
        title="Range Estimate Fluctuation",
        description=(
            "While cruising on the motorway at 110 km/h your EV's remaining-"
            "range estimate fluctuates between 75 km and 55 km over five "
            "minutes due to headwind and hills.  Your destination is 65 km "
            "away and there are no chargers on the direct route."
        ),
        probe=(
            "How much do you trust the range estimate displayed by the vehicle "
            "in this scenario?"
        ),
    ),
]

# ---------------------------------------------------------------------------
# Block 2 – System Trust
# ---------------------------------------------------------------------------
SYSTEM_TRUST_SCENARIOS: list[Scenario] = [
    Scenario(
        id="ST_01",
        topic="system_trust",
        title="Autonomous Emergency Braking (AEB) Activation",
        description=(
            "You are driving at 80 km/h on a suburban road.  A child runs "
            "unexpectedly from between parked cars.  Your vehicle's Autonomous "
            "Emergency Braking system activates and brings the car to a full "
            "stop 2 metres from the child before you have time to react.  "
            "This is the first time the system has intervened."
        ),
        probe=(
            "After this intervention, how much do you trust the AEB system to "
            "act correctly in future emergency situations?"
        ),
    ),
    Scenario(
        id="ST_02",
        topic="system_trust",
        title="Lane-Keeping Assist Override in Roadworks",
        description=(
            "You are travelling through a roadworks zone where temporary lane "
            "markings conflict with the original road markings.  Your vehicle's "
            "Lane-Keeping Assist (LKA) repeatedly nudges the steering wheel "
            "towards what appears to be the wrong lane.  You correct the "
            "steering each time, but the system continues to intervene."
        ),
        probe=(
            "How confident are you in the Lane-Keeping Assist system's ability "
            "to handle non-standard road conditions such as roadworks?"
        ),
    ),
    Scenario(
        id="ST_03",
        topic="system_trust",
        title="Adaptive Cruise Control in Heavy Rain",
        description=(
            "You are motorway driving in heavy rain with reduced visibility.  "
            "Your Adaptive Cruise Control (ACC) is engaged at 110 km/h.  The "
            "system suddenly decelerates to 70 km/h without any visible "
            "obstacle ahead.  Other vehicles around you maintain normal speed.  "
            "The system provides no explanation for the reduction."
        ),
        probe=(
            "How comfortable are you allowing the ACC to manage your speed in "
            "poor weather conditions after this experience?"
        ),
    ),
    Scenario(
        id="ST_04",
        topic="system_trust",
        title="Navigation-Recommended Longer Route",
        description=(
            "Your vehicle's integrated navigation suggests a route that is "
            "20 minutes longer than the one you know from experience.  The "
            "system claims the alternative avoids a traffic delay, but a quick "
            "check on your smartphone shows no current congestion on the "
            "shorter route."
        ),
        probe=(
            "How much do you trust the vehicle's navigation recommendation "
            "over your own knowledge in this case?"
        ),
    ),
    Scenario(
        id="ST_05",
        topic="system_trust",
        title="False Blind-Spot Warning",
        description=(
            "While changing lanes on a clear motorway, your vehicle's Blind-"
            "Spot Monitoring (BSM) system sounds an alert and illuminates a "
            "warning light.  You check your mirrors and physically turn to look "
            "— there is no vehicle in the blind spot.  This is the third "
            "similar false alarm in the past month."
        ),
        probe=(
            "How does this repeated false alarm affect your overall trust in "
            "the vehicle's safety-assistance systems?"
        ),
    ),
]

# ---------------------------------------------------------------------------
# Combined lookup
# ---------------------------------------------------------------------------
ALL_SCENARIOS: dict[str, Scenario] = {
    s.id: s for s in RANGE_ANXIETY_SCENARIOS + SYSTEM_TRUST_SCENARIOS
}

SCENARIOS_BY_TOPIC: dict[str, list[Scenario]] = {
    "range_anxiety": RANGE_ANXIETY_SCENARIOS,
    "system_trust": SYSTEM_TRUST_SCENARIOS,
}
