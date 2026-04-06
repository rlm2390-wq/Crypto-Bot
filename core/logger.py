"""core/logger.py — Shared activity log and standard logger."""

import logging
from collections import deque

# In-memory activity log (last 200 entries)
ACTIVITY_LOG = deque(maxlen=200)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    handlers=[
        logging.FileHandler("engine.log"),
        logging.StreamHandler()
    ]
)

_log = logging.getLogger("ENGINE")


def activity(msg: str, level: str = "INFO"):
    """Add entry to in-memory activity log and write to standard logger."""
    from datetime import datetime
    entry = {
        "ts":    datetime.now().strftime("%H:%M:%S"),
        "msg":   msg,
        "level": level,
    }
    ACTIVITY_LOG.appendleft(entry)
    getattr(_log, level.lower(), _log.info)(msg)
