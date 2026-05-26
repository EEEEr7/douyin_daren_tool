from __future__ import annotations

import random
import time

import config


def human_delay(*, fast: bool = True, aggressive: bool = False) -> None:
    if aggressive or fast:
        time.sleep(random.uniform(config.REQUEST_DELAY_MIN_SEC, config.REQUEST_DELAY_MAX_SEC))
        return
    delay = random.uniform(config.REQUEST_DELAY_MIN_SEC, config.REQUEST_DELAY_MAX_SEC)
    time.sleep(delay)


def profile_ready_jitter(page, *, fast: bool = True) -> None:
    if fast:
        page.wait_for_timeout(random.randint(150, config.PROFILE_READY_JITTER_MS))
        return
    jitter = random.randint(800, config.PROFILE_READY_JITTER_MS)
    page.wait_for_timeout(jitter)
