# DrivingExp — Range Anxiety & System Trust Experience Script

A Python-based experiment runner for a driving-experience study focused on
two topics:

| Topic | Description |
|---|---|
| **Range anxiety** | Scenarios involving EV battery depletion concern |
| **System trust** | Scenarios involving reliance on / scepticism of driver-assistance features |

---

## Structure

```
experience_script/
├── __init__.py
├── __main__.py        # enables  python -m experience_script
├── config.py          # experiment settings (tweak before running)
├── main.py            # session runner & CLI entry-point
├── scenarios.py       # 10 vignette scenarios (5 per topic)
├── questionnaire.py   # validated scales + debrief items
└── data_logger.py     # CSV data logger

tests/
└── test_experience_script.py   # pytest test suite (27 tests)

requirements.txt       # only pytest is needed (stdlib otherwise)
```

---

## Requirements

- Python 3.10 or later (uses the `list[T]` and `str | None` syntax)
- No third-party runtime dependencies — everything uses the Python standard
  library
- `pytest` is required only to run the tests

---

## Running the script

```bash
# from the repository root
python -m experience_script --participant P01
```

```
Options:
  -p / --participant ID   Participant identifier (prompted if omitted)
  -s / --seed N           Random seed for reproducible ordering
```

The script will:
1. Welcome the participant
2. Present two blocks (order randomised by default):
   - **Range Anxiety** — 5 vignettes + Range Anxiety Scale (6 items)
   - **System Trust** — 5 vignettes + Trust in Automation Scale (12 items)
3. Administer two open-ended debrief questions
4. Save all responses to `data/participant_<ID>_<timestamp>.csv`

---

## Configuration

Edit `experience_script/config.py` (or create a subclass of
`ExperimentConfig`) to change:

| Setting | Default | Description |
|---|---|---|
| `data_dir` | `"data"` | Directory for CSV output files |
| `randomise_block_order` | `True` | Randomise the two topic blocks |
| `randomise_scenarios_within_block` | `True` | Randomise scenario order within each block |
| `scenario_read_time` | `10` | Seconds before the probe appears (0 = press-to-advance) |
| `line_width` | `72` | Console text wrap width |

---

## Running the tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Scales used

| Scale | Reference | Items |
|---|---|---|
| Trust in Automation (TIA) | Jian et al. (2000) | 12 items, 7-point |
| Range Anxiety Scale (RAS) | Adapted from Rauh et al. (2015) | 6 items, 7-point |

---

## Output CSV columns

| Column | Description |
|---|---|
| `participant_id` | Assigned participant identifier |
| `session_id` | Unique UUID for the session |
| `timestamp` | ISO-8601 UTC datetime of the response |
| `block_index` | Which block within the session (0-based) |
| `scenario_id` | Scenario identifier, e.g. `RA_01` (blank for block-level items) |
| `item_id` | Questionnaire item identifier, e.g. `TIA_06` or `RA_01_probe` |
| `response` | Numeric rating (1–7) or free-text answer |