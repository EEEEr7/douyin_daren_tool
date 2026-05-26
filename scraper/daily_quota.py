from __future__ import annotations

import json
from datetime import date, datetime
from typing import Literal

import config

SessionName = Literal["morning", "noon", "evening"]

SESSION_LABELS_CN = {
    "morning": "上午",
    "noon": "下午",
    "evening": "晚上",
}


def session_label_cn(session: SessionName | str) -> str:
    if session == "auto":
        session = detect_session()
    return SESSION_LABELS_CN.get(session, "下午")


def _today_str() -> str:
    return date.today().isoformat()


def _load_json(path, default):
    if not path.exists() or path.stat().st_size == 0:
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _save_json(path, data) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_session(hour: int | None = None) -> SessionName:
    hour = hour if hour is not None else datetime.now().hour
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "noon"
    return "evening"


def load_processed_uids() -> set[str]:
    data = _load_json(config.PROCESSED_UIDS_PATH, {"uids": []})
    return set(data.get("uids", []))


def mark_uid_processed(uid: str) -> None:
    uids = load_processed_uids()
    if uid in uids:
        return
    uids.add(uid)
    _save_json(config.PROCESSED_UIDS_PATH, {"uids": sorted(uids)})


def load_daily_stats() -> dict:
    stats = _load_json(
        config.DAILY_STATS_PATH,
        {"date": _today_str(), "success_count": 0, "sessions": []},
    )
    if stats.get("date") != _today_str():
        stats = {"date": _today_str(), "success_count": 0, "sessions": []}
    return stats


def save_daily_stats(stats: dict) -> None:
    _save_json(config.DAILY_STATS_PATH, stats)


def remaining_today() -> int:
    stats = load_daily_stats()
    return max(0, config.DAILY_TARGET - int(stats.get("success_count", 0)))


def session_limit(session: SessionName | None = None) -> int:
    stats = load_daily_stats()
    remaining = remaining_today()
    if remaining <= 0:
        return 0

    session = session or detect_session()
    if session in stats.get("sessions", []):
        # 同一段已跑过：仍允许补量，但单次上限更保守
        per_session = max(6, config.PER_SESSION_TARGET // 2)
    else:
        per_session = config.PER_SESSION_TARGET

    return min(per_session, remaining)


def record_session_run(session: SessionName, success_count: int) -> None:
    stats = load_daily_stats()
    if session not in stats.setdefault("sessions", []):
        stats["sessions"].append(session)
    stats["success_count"] = int(stats.get("success_count", 0)) + success_count
    save_daily_stats(stats)


def format_quota_summary(session: SessionName, planned: int) -> str:
    stats = load_daily_stats()
    return (
        f"时段: {session} | 本次计划: {planned} 条 | "
        f"今日已成功: {stats.get('success_count', 0)}/{config.DAILY_TARGET} | "
        f"今日已跑时段: {', '.join(stats.get('sessions', [])) or '无'}"
    )
