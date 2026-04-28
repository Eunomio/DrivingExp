"""
CSV-based data logger for the Range Anxiety & System Trust experience script.

One CSV file is created per participant session inside `config.data_dir`.
File naming convention:  <data_dir>/participant_<pid>_<ISO-timestamp>.csv

Columns written for every response row
---------------------------------------
participant_id  : str   – assigned participant identifier
session_id      : str   – unique session UUID
timestamp       : str   – ISO-8601 datetime of the response
block_index     : int   – which block within the session (0-based)
scenario_id     : str   – e.g. "RA_01" or "ST_03" (blank for scale items)
item_id         : str   – questionnaire item identifier
response        : str   – numeric rating or free-text answer
"""

import csv
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import config


class DataLogger:
    """Opens (or creates) a per-participant CSV file and appends rows."""

    FIELDNAMES = [
        "participant_id",
        "session_id",
        "timestamp",
        "block_index",
        "scenario_id",
        "item_id",
        "response",
    ]

    def __init__(self, participant_id: str) -> None:
        self.participant_id = participant_id
        self.session_id = str(uuid.uuid4())
        self._file_path = self._init_file()
        self._file = open(self._file_path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self.FIELDNAMES)
        if os.path.getsize(self._file_path) == 0:
            self._writer.writeheader()

    # ------------------------------------------------------------------
    def _init_file(self) -> Path:
        data_dir = Path(config.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"participant_{self.participant_id}_{timestamp}.csv"
        return data_dir / filename

    # ------------------------------------------------------------------
    def log(
        self,
        item_id: str,
        response: str,
        block_index: int = 0,
        scenario_id: Optional[str] = None,
    ) -> None:
        """Append a single response row to the CSV."""
        self._writer.writerow(
            {
                "participant_id": self.participant_id,
                "session_id": self.session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "block_index": block_index,
                "scenario_id": scenario_id or "",
                "item_id": item_id,
                "response": response,
            }
        )
        self._file.flush()

    # ------------------------------------------------------------------
    def close(self) -> None:
        self._file.close()

    # ------------------------------------------------------------------
    @property
    def file_path(self) -> Path:
        return self._file_path

    # ------------------------------------------------------------------
    def __enter__(self) -> "DataLogger":
        return self

    def __exit__(self, *_) -> None:
        self.close()
