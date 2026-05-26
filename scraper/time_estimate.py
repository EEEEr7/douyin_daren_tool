from __future__ import annotations

import config


def estimate_item_seconds(*, fast: bool = True, aggressive: bool = False) -> float:
    del aggressive
    if fast:
        delay_avg = (config.REQUEST_DELAY_MIN_SEC + config.REQUEST_DELAY_MAX_SEC) / 2
        profile_avg = 2.5 + (config.REVEAL_WAIT_MIN_MS + config.REVEAL_WAIT_MAX_MS) / 2000.0
        return delay_avg + profile_avg
    delay_avg = (config.REQUEST_DELAY_MIN_SEC + config.REQUEST_DELAY_MAX_SEC) / 2
    profile_avg = 12.0 + config.PROFILE_READY_JITTER_MS / 2000.0
    return delay_avg + profile_avg


def estimate_total_seconds(item_count: int, *, fast: bool = True, aggressive: bool = False) -> int:
    if item_count <= 0:
        return 0
    return min(config.RUN_BUDGET_SEC, int(item_count * estimate_item_seconds(fast=fast, aggressive=aggressive)))


def estimate_remaining_seconds(
    done: int,
    total: int,
    elapsed_sec: float,
    *,
    fast: bool = True,
    aggressive: bool = False,
) -> int:
    remaining = max(total - done, 0)
    if remaining <= 0:
        return 0
    if done <= 0:
        return estimate_total_seconds(remaining, fast=fast, aggressive=aggressive)
    avg_per_item = max(elapsed_sec / done, 0.8)
    return min(config.RUN_BUDGET_SEC, int(remaining * avg_per_item))


def format_duration(seconds: int) -> str:
    seconds = max(int(seconds), 0)
    if seconds < 60:
        return f"{seconds} 秒"
    minutes, secs = divmod(seconds, 60)
    if secs == 0:
        return f"{minutes} 分钟"
    return f"{minutes} 分 {secs} 秒"


def format_eta_text(
    done: int,
    total: int,
    elapsed_sec: float,
    *,
    fast: bool = True,
    aggressive: bool = False,
) -> str:
    remaining_sec = estimate_remaining_seconds(done, total, elapsed_sec, fast=fast, aggressive=aggressive)
    if done <= 0:
        return f"目标 {total} 条 · 凑满即停"
    if remaining_sec <= 0 or done >= total:
        return f"已完成 {done}/{total}"
    return f"已得 {done}/{total} · 预估剩余 {format_duration(remaining_sec)}"


def filter_summary() -> str:
    return f"{config.CATEGORY_FILTER} + {config.CONTACT_FILTER}"
