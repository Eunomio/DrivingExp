"""
Questionnaire items for the Range Anxiety & System Trust experience script.

Two validated / established scales are included:

1. **Likert-7 Probe Response** – used after every scenario to rate the
   probe question on a 7-point scale (1 = Not at all, 7 = Extremely).

2. **Trust in Automation Scale (Jian et al., 2000)** – administered once
   per system-trust block.  12 items, 7-point scale.

3. **Range Anxiety Scale (adapted from Rauh et al., 2015)** – 6 items
   administered once per range-anxiety block.  7-point scale.

4. **Open-ended debrief questions** – two free-text items collected at
   the end of the session.
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class LikertItem:
    id: str
    text: str
    scale_min: int = 1
    scale_max: int = 7
    anchor_low: str = "Not at all"
    anchor_high: str = "Extremely"


@dataclass(frozen=True)
class OpenItem:
    id: str
    text: str


# ---------------------------------------------------------------------------
# Per-scenario probe – reuses the probe text stored in the Scenario object.
# The questionnaire runner records the answer under  <scenario_id>_probe.
# ---------------------------------------------------------------------------
PROBE_SCALE = LikertItem(
    id="probe",
    text="<see scenario probe>",
    anchor_low="Not at all",
    anchor_high="Extremely",
)

# ---------------------------------------------------------------------------
# Trust in Automation Scale (Jian et al., 2000) – 12 items
# Subscales: Distrust (items 1–6) and Trust (items 7–12)
# ---------------------------------------------------------------------------
TRUST_IN_AUTOMATION_SCALE: List[LikertItem] = [
    LikertItem(
        id="TIA_01",
        text="The system is deceptive.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
    LikertItem(
        id="TIA_02",
        text="The system behaves in an underhanded manner.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
    LikertItem(
        id="TIA_03",
        text="I am suspicious of the system's intent, action, or outputs.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
    LikertItem(
        id="TIA_04",
        text="I am wary of the system.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
    LikertItem(
        id="TIA_05",
        text="The system's actions will have a harmful or injurious outcome.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
    LikertItem(
        id="TIA_06",
        text="I am confident in the system.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
    LikertItem(
        id="TIA_07",
        text="The system provides security.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
    LikertItem(
        id="TIA_08",
        text="The system has integrity.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
    LikertItem(
        id="TIA_09",
        text="The system is dependable.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
    LikertItem(
        id="TIA_10",
        text="The system is reliable.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
    LikertItem(
        id="TIA_11",
        text="I can trust the system.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
    LikertItem(
        id="TIA_12",
        text="I am familiar with the system.",
        anchor_low="Not at all",
        anchor_high="Extremely",
    ),
]

# ---------------------------------------------------------------------------
# Range Anxiety Scale (adapted from Rauh et al., 2015) – 6 items
# ---------------------------------------------------------------------------
RANGE_ANXIETY_SCALE: List[LikertItem] = [
    LikertItem(
        id="RAS_01",
        text=(
            "I worry about running out of battery before reaching my "
            "destination."
        ),
        anchor_low="Strongly disagree",
        anchor_high="Strongly agree",
    ),
    LikertItem(
        id="RAS_02",
        text="I feel stressed when the battery level drops below 20 %.",
        anchor_low="Strongly disagree",
        anchor_high="Strongly agree",
    ),
    LikertItem(
        id="RAS_03",
        text=(
            "I plan my routes primarily around charging-station locations "
            "rather than time or distance."
        ),
        anchor_low="Strongly disagree",
        anchor_high="Strongly agree",
    ),
    LikertItem(
        id="RAS_04",
        text=(
            "Uncertainty about the accuracy of the range estimate increases "
            "my anxiety."
        ),
        anchor_low="Strongly disagree",
        anchor_high="Strongly agree",
    ),
    LikertItem(
        id="RAS_05",
        text="I avoid long trips in my EV because of charging concerns.",
        anchor_low="Strongly disagree",
        anchor_high="Strongly agree",
    ),
    LikertItem(
        id="RAS_06",
        text=(
            "I feel more relaxed when I know a fast charger is available "
            "nearby."
        ),
        anchor_low="Strongly disagree",
        anchor_high="Strongly agree",
    ),
]

# ---------------------------------------------------------------------------
# Post-session open-ended debrief
# ---------------------------------------------------------------------------
DEBRIEF_ITEMS: List[OpenItem] = [
    OpenItem(
        id="DEBRIEF_01",
        text=(
            "Thinking about all the scenarios you experienced today, what "
            "strategies would help reduce range anxiety for EV drivers?"
        ),
    ),
    OpenItem(
        id="DEBRIEF_02",
        text=(
            "What changes to driver-assistance systems would most increase "
            "your trust in them while driving?"
        ),
    ),
]
