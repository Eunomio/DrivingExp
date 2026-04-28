"""
Tests for the Range Anxiety & System Trust experience script.

Run with:
    pytest tests/
"""

import csv
import os
import random
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------

from experience_script.scenarios import (
    ALL_SCENARIOS,
    RANGE_ANXIETY_SCENARIOS,
    SCENARIOS_BY_TOPIC,
    SYSTEM_TRUST_SCENARIOS,
    Scenario,
)


class TestScenarios:
    def test_range_anxiety_scenarios_exist(self):
        assert len(RANGE_ANXIETY_SCENARIOS) >= 5

    def test_system_trust_scenarios_exist(self):
        assert len(SYSTEM_TRUST_SCENARIOS) >= 5

    def test_all_scenarios_unique_ids(self):
        ids = [s.id for s in RANGE_ANXIETY_SCENARIOS + SYSTEM_TRUST_SCENARIOS]
        assert len(ids) == len(set(ids)), "Duplicate scenario IDs found"

    def test_all_scenarios_have_required_fields(self):
        for s in RANGE_ANXIETY_SCENARIOS + SYSTEM_TRUST_SCENARIOS:
            assert s.id, f"Scenario missing id: {s}"
            assert s.topic in ("range_anxiety", "system_trust")
            assert s.title
            assert s.description
            assert s.probe

    def test_scenarios_by_topic_keys(self):
        assert "range_anxiety" in SCENARIOS_BY_TOPIC
        assert "system_trust" in SCENARIOS_BY_TOPIC

    def test_all_scenarios_lookup(self):
        for sid, scenario in ALL_SCENARIOS.items():
            assert isinstance(scenario, Scenario)
            assert scenario.id == sid

    def test_range_anxiety_topic_tag(self):
        for s in RANGE_ANXIETY_SCENARIOS:
            assert s.topic == "range_anxiety"

    def test_system_trust_topic_tag(self):
        for s in SYSTEM_TRUST_SCENARIOS:
            assert s.topic == "system_trust"


# ---------------------------------------------------------------------------
# questionnaire
# ---------------------------------------------------------------------------

from experience_script.questionnaire import (
    DEBRIEF_ITEMS,
    RANGE_ANXIETY_SCALE,
    TRUST_IN_AUTOMATION_SCALE,
    LikertItem,
    OpenItem,
)


class TestQuestionnaire:
    def test_trust_in_automation_scale_length(self):
        assert len(TRUST_IN_AUTOMATION_SCALE) == 12

    def test_range_anxiety_scale_length(self):
        assert len(RANGE_ANXIETY_SCALE) == 6

    def test_debrief_items_count(self):
        assert len(DEBRIEF_ITEMS) == 2

    def test_likert_items_are_7_point(self):
        for item in TRUST_IN_AUTOMATION_SCALE + RANGE_ANXIETY_SCALE:
            assert item.scale_min == 1
            assert item.scale_max == 7

    def test_all_scale_ids_unique(self):
        all_items = TRUST_IN_AUTOMATION_SCALE + RANGE_ANXIETY_SCALE
        ids = [i.id for i in all_items]
        assert len(ids) == len(set(ids))

    def test_debrief_items_are_open_items(self):
        for item in DEBRIEF_ITEMS:
            assert isinstance(item, OpenItem)
            assert item.id
            assert item.text

    def test_likert_item_anchors_present(self):
        for item in TRUST_IN_AUTOMATION_SCALE:
            assert item.anchor_low
            assert item.anchor_high


# ---------------------------------------------------------------------------
# data_logger
# ---------------------------------------------------------------------------

from experience_script.data_logger import DataLogger
from experience_script import config as config_module


class TestDataLogger:
    def test_creates_csv_file(self, tmp_path):
        config_module.config.data_dir = str(tmp_path)
        with DataLogger("P01") as logger:
            pass
        files = list(tmp_path.glob("*.csv"))
        assert len(files) == 1

    def test_csv_has_header(self, tmp_path):
        config_module.config.data_dir = str(tmp_path)
        with DataLogger("P02") as logger:
            pass
        csv_file = next(tmp_path.glob("*.csv"))
        with open(csv_file, newline="") as f:
            reader = csv.DictReader(f)
            assert set(reader.fieldnames) == set(DataLogger.FIELDNAMES)

    def test_log_writes_row(self, tmp_path):
        config_module.config.data_dir = str(tmp_path)
        with DataLogger("P03") as logger:
            logger.log(item_id="RA_01_probe", response="5",
                       block_index=0, scenario_id="RA_01")
        csv_file = next(tmp_path.glob("*.csv"))
        with open(csv_file, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        row = rows[0]
        assert row["participant_id"] == "P03"
        assert row["item_id"] == "RA_01_probe"
        assert row["response"] == "5"
        assert row["scenario_id"] == "RA_01"

    def test_participant_id_in_filename(self, tmp_path):
        config_module.config.data_dir = str(tmp_path)
        with DataLogger("TESTPART") as logger:
            pass
        files = list(tmp_path.glob("*.csv"))
        assert any("TESTPART" in f.name for f in files)

    def test_session_id_is_uuid(self, tmp_path):
        import uuid
        config_module.config.data_dir = str(tmp_path)
        with DataLogger("P04") as logger:
            session_id = logger.session_id
        # Should not raise
        uuid.UUID(session_id)

    def test_multiple_rows(self, tmp_path):
        config_module.config.data_dir = str(tmp_path)
        with DataLogger("P05") as logger:
            for i in range(5):
                logger.log(item_id=f"ITEM_{i}", response=str(i))
        csv_file = next(tmp_path.glob("*.csv"))
        with open(csv_file, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 5

    def test_context_manager_closes_file(self, tmp_path):
        config_module.config.data_dir = str(tmp_path)
        with DataLogger("P06") as logger:
            fp = logger._file
        assert fp.closed


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

from experience_script.config import ExperimentConfig


class TestConfig:
    def test_default_blocks(self):
        cfg = ExperimentConfig()
        assert "range_anxiety" in cfg.topic_blocks
        assert "system_trust" in cfg.topic_blocks

    def test_line_width_positive(self):
        cfg = ExperimentConfig()
        assert cfg.line_width > 0

    def test_study_name_non_empty(self):
        cfg = ExperimentConfig()
        assert cfg.study_name


# ---------------------------------------------------------------------------
# main – unit-test the CLI argument parsing and session logic
# ---------------------------------------------------------------------------

from experience_script.main import main, run_session


class TestMain:
    """
    Smoke-tests for run_session and CLI parsing.
    All I/O is mocked so no TTY is needed.
    """

    def _make_inputs(self, *values):
        """Return a side_effect list for builtins.input."""
        return list(values)

    def test_cli_exits_on_empty_participant(self, tmp_path, capsys):
        config_module.config.data_dir = str(tmp_path)
        with patch("builtins.input", return_value=""):
            with pytest.raises(SystemExit):
                main([])

    def test_run_session_creates_data_file(self, tmp_path):
        """run_session with all mocked input should produce a CSV."""
        config_module.config.data_dir = str(tmp_path)
        config_module.config.randomise_block_order = False
        config_module.config.randomise_scenarios_within_block = False
        config_module.config.scenario_read_time = 0

        # Number of input() calls expected:
        #   5 range-anxiety probe answers (1 each)
        #   6 range-anxiety scale items
        #   5 system-trust probe answers
        #   12 trust-in-automation scale items
        #   2 open-ended debrief (free text)
        #   1 "press enter to continue" for RA block intro
        #   5 "press enter" for RA scenario reads (scenario_read_time=0)
        #   1 "press enter" for ST block intro
        #   5 "press enter" for ST scenario reads
        # Total ≈ many inputs; supply 100 inputs of "5" / "yes" to be safe.
        inputs = ["5"] * 100

        with patch("builtins.input", side_effect=inputs):
            run_session("MOCK_PARTICIPANT")

        files = list(tmp_path.glob("*.csv"))
        assert len(files) == 1
        with open(files[0], newline="") as f:
            rows = list(csv.DictReader(f))
        # At least probes + scale items should have been logged
        assert len(rows) >= 5 + 6 + 5 + 12
