"""
Main experiment runner for the Range Anxiety & System Trust experience script.

Usage
-----
Run from the repository root:

    python -m experience_script

Or with an explicit participant ID:

    python -m experience_script --participant P42

Outputs
-------
* A timestamped CSV file written to  ./data/  for each session.
* Console progress messages shown to the experimenter.
"""

import random
import sys
import textwrap
import time
from typing import List

from .config import config
from .data_logger import DataLogger
from .questionnaire import (
    DEBRIEF_ITEMS,
    RANGE_ANXIETY_SCALE,
    TRUST_IN_AUTOMATION_SCALE,
    LikertItem,
    OpenItem,
)
from .scenarios import SCENARIOS_BY_TOPIC, Scenario


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _hr(char: str = "─") -> str:
    return char * config.line_width


def _print_wrapped(text: str, indent: int = 0) -> None:
    prefix = " " * indent
    for line in textwrap.wrap(text, width=config.line_width - indent):
        print(prefix + line)


def _clear() -> None:
    print("\n" + _hr("═") + "\n")


def _press_enter(prompt: str = "Press Enter to continue...") -> None:
    input(f"\n{prompt}")


# ---------------------------------------------------------------------------
# Input collection helpers
# ---------------------------------------------------------------------------

def _collect_likert(item: LikertItem, block_index: int,
                    logger: DataLogger,
                    scenario_id: str | None = None) -> int:
    """Present a Likert item and return the validated integer response."""
    _print_wrapped(item.text)
    scale_str = "  ".join(
        f"{n}" for n in range(item.scale_min, item.scale_max + 1)
    )
    print(
        f"\n  {item.anchor_low} [{item.scale_min}]"
        f"  {'─' * 10}  [{item.scale_max}] {item.anchor_high}"
    )
    print(f"\n  Scale: {scale_str}")
    while True:
        raw = input("\n  Your answer: ").strip()
        try:
            value = int(raw)
            if item.scale_min <= value <= item.scale_max:
                logger.log(
                    item_id=item.id,
                    response=str(value),
                    block_index=block_index,
                    scenario_id=scenario_id,
                )
                return value
        except ValueError:
            pass
        print(
            f"  Please enter a whole number between "
            f"{item.scale_min} and {item.scale_max}."
        )


def _collect_open(item: OpenItem, block_index: int,
                  logger: DataLogger) -> str:
    """Present an open-ended question and return the text response."""
    _print_wrapped(item.text)
    print("\n  (Type your answer and press Enter)")
    response = input("\n  Your answer: ").strip()
    logger.log(
        item_id=item.id,
        response=response,
        block_index=block_index,
    )
    return response


# ---------------------------------------------------------------------------
# Scenario presenter
# ---------------------------------------------------------------------------

def _run_scenario(scenario: Scenario, block_index: int,
                  logger: DataLogger) -> None:
    _clear()
    print(f"  Scenario {scenario.id}: {scenario.title}\n")
    print(_hr())
    print()
    _print_wrapped(scenario.description, indent=2)
    print()
    print(_hr())

    if config.scenario_read_time > 0:
        print(
            f"\n  Please read the scenario carefully.  "
            f"The probe question will appear in "
            f"{config.scenario_read_time} seconds..."
        )
        time.sleep(config.scenario_read_time)
    else:
        _press_enter("Press Enter when you have read the scenario...")

    # Probe question
    _clear()
    print(f"  Scenario {scenario.id}  ─  Probe Question\n")
    print(_hr())
    print()

    # Build a temporary LikertItem from the scenario's probe text
    probe_item = LikertItem(
        id=f"{scenario.id}_probe",
        text=scenario.probe,
        anchor_low="Not at all",
        anchor_high="Extremely",
    )
    _collect_likert(probe_item, block_index=block_index,
                    logger=logger, scenario_id=scenario.id)


# ---------------------------------------------------------------------------
# Block runners
# ---------------------------------------------------------------------------

def _run_range_anxiety_block(block_index: int, logger: DataLogger) -> None:
    _clear()
    print("  BLOCK: RANGE ANXIETY\n")
    _print_wrapped(
        "In this block you will read a series of situations that an "
        "electric vehicle driver might encounter related to battery range.  "
        "After each situation, please answer the probe question honestly "
        "based on how YOU would feel."
    )
    _press_enter()

    scenarios: List[Scenario] = list(SCENARIOS_BY_TOPIC["range_anxiety"])
    if config.randomise_scenarios_within_block:
        random.shuffle(scenarios)

    for scenario in scenarios:
        _run_scenario(scenario, block_index=block_index, logger=logger)

    # Block-level scale
    _clear()
    print("  RANGE ANXIETY QUESTIONNAIRE\n")
    _print_wrapped(
        "Please rate your general agreement with the following statements "
        "about driving electric vehicles.  Think about your own experience "
        "or how you IMAGINE you would feel as an EV driver."
    )
    print()
    for item in RANGE_ANXIETY_SCALE:
        print()
        _collect_likert(item, block_index=block_index, logger=logger)


def _run_system_trust_block(block_index: int, logger: DataLogger) -> None:
    _clear()
    print("  BLOCK: SYSTEM TRUST\n")
    _print_wrapped(
        "In this block you will read situations involving driver-assistance "
        "or autonomous driving features.  After each situation, answer the "
        "probe question based on how you would react."
    )
    _press_enter()

    scenarios: List[Scenario] = list(SCENARIOS_BY_TOPIC["system_trust"])
    if config.randomise_scenarios_within_block:
        random.shuffle(scenarios)

    for scenario in scenarios:
        _run_scenario(scenario, block_index=block_index, logger=logger)

    # Block-level scale
    _clear()
    print("  TRUST IN AUTOMATION QUESTIONNAIRE\n")
    _print_wrapped(
        "The following statements are about automated systems in vehicles "
        "in general.  Please rate each item as it applies to your current "
        "perception."
    )
    print()
    for item in TRUST_IN_AUTOMATION_SCALE:
        print()
        _collect_likert(item, block_index=block_index, logger=logger)


# ---------------------------------------------------------------------------
# Session entry-point
# ---------------------------------------------------------------------------

_BLOCK_RUNNERS = {
    "range_anxiety": _run_range_anxiety_block,
    "system_trust": _run_system_trust_block,
}


def run_session(participant_id: str) -> None:
    """Execute a complete experiment session for one participant."""
    with DataLogger(participant_id) as logger:
        # Welcome screen
        _clear()
        print(f"  {config.study_name}  (v{config.study_version})\n")
        print(_hr())
        _print_wrapped(
            "Welcome, and thank you for taking part in this study.  "
            "You will be presented with a series of driving scenarios.  "
            "For each scenario, please read carefully and answer the "
            "questions that follow.  There are no right or wrong answers — "
            "we are interested in your genuine perceptions and feelings.",
            indent=2,
        )
        print()
        _print_wrapped(
            "Your responses are anonymous and will only be used for "
            "research purposes.",
            indent=2,
        )
        _press_enter()

        # Determine block order
        blocks: List[str] = list(config.topic_blocks)
        if config.randomise_block_order:
            random.shuffle(blocks)

        for block_index, block_name in enumerate(blocks):
            runner = _BLOCK_RUNNERS.get(block_name)
            if runner is None:
                print(f"  [WARNING] Unknown block '{block_name}' — skipping.")
                continue
            runner(block_index=block_index, logger=logger)

        # Debrief
        _clear()
        print("  DEBRIEF — Open Questions\n")
        _print_wrapped(
            "Finally, please answer the following two open-ended questions.  "
            "Take as much time as you need."
        )
        print()
        for item in DEBRIEF_ITEMS:
            print()
            _collect_open(item, block_index=len(blocks), logger=logger)

        # End screen
        _clear()
        print("  SESSION COMPLETE\n")
        _print_wrapped(
            "Thank you for completing this study!  Your responses have been "
            "recorded.  Please inform the experimenter that you have finished."
        )
        print(f"\n  Data saved to: {logger.file_path}")
        print()


# ---------------------------------------------------------------------------
# CLI entry-point (also invoked via __main__.py)
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=config.study_name,
    )
    parser.add_argument(
        "--participant",
        "-p",
        default=None,
        metavar="ID",
        help="Participant identifier (prompted interactively if omitted).",
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=None,
        metavar="N",
        help="Random seed for reproducible block/scenario ordering.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.seed is not None:
        random.seed(args.seed)

    participant_id = args.participant
    if not participant_id:
        participant_id = input("Enter participant ID: ").strip()
        if not participant_id:
            print("Participant ID cannot be empty.  Exiting.")
            sys.exit(1)

    run_session(participant_id)


if __name__ == "__main__":
    main()
