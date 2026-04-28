"""
Experiment configuration for the Range Anxiety & System Trust experience script.

Edit the values in ExperimentConfig to customise the study before running.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ExperimentConfig:
    # ------------------------------------------------------------------ study
    study_name: str = "Range Anxiety & System Trust Driving Experience"
    study_version: str = "1.0.0"

    # ------------------------------------------------------------------ output
    data_dir: str = "data"          # directory where CSV logs are written

    # ---------------------------------------------------------------- scenario
    # Topic blocks presented to each participant (order can be randomised).
    topic_blocks: List[str] = field(
        default_factory=lambda: ["range_anxiety", "system_trust"]
    )
    randomise_block_order: bool = True
    randomise_scenarios_within_block: bool = True

    # ----------------------------------------------------------------- timing
    # Seconds participants have to read each scenario before responding.
    scenario_read_time: int = 10    # set to 0 to advance on any key-press

    # -------------------------------------------------------------- display
    line_width: int = 72            # console text wrap width


# Singleton used by the rest of the package
config = ExperimentConfig()
