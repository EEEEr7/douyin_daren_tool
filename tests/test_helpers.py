from datetime import date
from pathlib import Path

import config
from scraper.daily_quota import (
    load_daily_stats,
    mark_uid_processed,
    record_session_run,
    remaining_today,
    session_limit,
    load_processed_uids,
    session_label_cn,
)
from scraper.daren_profile import DarenContact, _extract_wechat_from_text
from scraper.daren_square import _extract_uid_from_href, parse_search_feed_author
from scraper.exporter import export_to_excel, run_output_dir


def test_extract_uid():
    href = "/dashboard/servicehall/daren-profile?uid=v2_abc123&enter_from=1"
    assert _extract_uid_from_href(href) == "v2_abc123"


def test_extract_wechat_from_text():
    assert _extract_wechat_from_text("达人微信号：***********") == ""
    assert _extract_wechat_from_text("达人微信号：DOLA-523") == "DOLA-523"


def test_parse_search_feed_author():
    payload = {
        "data": {
            "list": [
                {
                    "author_base": {
                        "uid": "v2_test",
                        "nickname": "菠萝有品",
                        "fans_num": 844900,
                    }
                }
            ]
        }
    }
    items = parse_search_feed_author(payload)
    assert len(items) == 1
    assert items[0].name == "菠萝有品"


def test_session_label_cn():
    assert session_label_cn("morning") == "上午"
    assert session_label_cn("noon") == "下午"
    assert session_label_cn("evening") == "晚上"


def test_run_output_dir(tmp_path, monkeypatch):
    import re

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    folder = run_output_dir("noon")
    assert folder.parent == tmp_path
    assert re.fullmatch(r"XTeink_\d{8}_\d{4}_下午", folder.name)


def test_daily_quota(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DAILY_STATS_PATH", tmp_path / "daily_stats.json")
    monkeypatch.setattr(config, "PROCESSED_UIDS_PATH", tmp_path / "processed_uids.json")

    assert session_limit("morning") == config.PER_SESSION_TARGET
    record_session_run("morning", 10)
    assert load_daily_stats()["success_count"] == 10
    assert remaining_today() == config.DAILY_TARGET - 10


def test_processed_uids(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "PROCESSED_UIDS_PATH", tmp_path / "processed_uids.json")

    mark_uid_processed("v2_a")
    assert "v2_a" in load_processed_uids()


def test_export_excel(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)

    contacts = [
        DarenContact(
            name="菠萝有品",
            uid="v2_test",
            wechat="DOLA-523",
            fans_count="84.49万",
            profile_url="https://example.com",
        )
    ]
    path = export_to_excel(contacts, session_label="morning")
    assert path.exists()
    assert path.parent.name.endswith("_上午")
    assert path.name == config.EXCEL_FILENAME
