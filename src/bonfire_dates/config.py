"""Fixed settings. Nothing personal lives here: local state is in data/."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/London")
CALENDAR_NAME = "Bonfire"
MARK = "bonfire-dates:"  # each event's URL: this, then its key (see calendar.js)
QUESTION_BELOW = 70  # titles of events rated below this get a trailing "?"

REPO_DIR = Path(__file__).resolve().parents[2]
SOCIETIES_FILE = REPO_DIR / "societies.toml"
CONFIRMED_FILE = REPO_DIR / "confirmed.toml"


def data_dir() -> Path:
    """Where local state lives. BONFIRE_DATA_DIR overrides (used by tests)."""
    override = os.environ.get("BONFIRE_DATA_DIR")
    return Path(override) if override else REPO_DIR / "data"


def known_file() -> Path:
    """Dates known first-hand ("verified"): private, never committed."""
    return data_dir() / "known.toml"
