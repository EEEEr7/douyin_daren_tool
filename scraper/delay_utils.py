from __future__ import annotations

import json
import random
import time
from datetime import datetime

import config


def human_delay(*, aggressive: bool = False) -> None:
    if aggressive:
        time.sleep(config.AGGRESSIVE_REQUEST_DELAY_SEC)
        return
    delay = random.uniform(config.REQUEST_DELAY_MIN_SEC, config.REQUEST_DELAY_MAX_SEC)
    time.sleep(delay)


def profile_ready_jitter(page) -> None:
    jitter = random.randint(800, config.PROFILE_READY_JITTER_MS)
    page.wait_for_timeout(jitter)
