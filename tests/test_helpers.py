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
from scraper.daren_profile import (
    DarenContact,
    _extract_wechat_from_text,
    _is_valid_wechat,
    _parse_contact_info_value,
    _row_text_has_masked_wechat,
)
from scraper.edge_profile_auth import default_profile_name
from scraper.daren_square import _extract_uid_from_href, parse_search_feed_author
from scraper.exporter import export_to_excel, run_output_dir


def test_default_profile_name(tmp_path):
    user_data = tmp_path / "User Data"
    user_data.mkdir()
    (user_data / "Local State").write_text(
        '{"profile":{"last_used":"Profile 1"}}',
        encoding="utf-8",
    )
    assert default_profile_name(user_data) == "Profile 1"


def test_format_eta_text():
    from scraper.time_estimate import format_eta_text

    assert "目标" in format_eta_text(0, 20, 0)
    assert "已得" in format_eta_text(2, 20, 40)


def test_row_has_contact():
    from scraper.daren_square import _row_has_contact

    assert _row_has_contact({"author_tag": ["有联系方式"], "author_base": {"uid": "1", "nickname": "a"}})
    assert not _row_has_contact({"author_base": {"uid": "1", "nickname": "a", "has_contact": False}})


def test_row_has_contact_author_tag_dict():
    from scraper.daren_square import _row_has_contact

    row = {
        "author_base": {"uid": "v2_test", "nickname": "菠萝有品"},
        "author_tag": {
            "contact_icon": "达人自主披露联系方式，你可点击小眼睛进行查看",
            "author_rec_reasons": [
                {"tag_type": 1006, "reason": "有联系方式", "extra": ""},
            ],
        },
    }
    assert _row_has_contact(row)


def test_parse_contact_info_value():
    body = {
        "data": {
            "contact_info": {
                "times_left": 998,
                "contact_value": "DOLA-523",
            }
        }
    }
    assert _parse_contact_info_value(body) == "DOLA-523"
    assert _parse_contact_info_value({"data": {"contact_info": {"contact_value": "********"}}}) == ""


def test_extract_wechat_from_text():
    assert _extract_wechat_from_text("达人微信号\nDOLA-523") == "DOLA-523"
    assert _extract_wechat_from_text("达人微信号\n********") == ""
    assert _extract_wechat_from_text("达人微信号：DOLA-523") == "DOLA-523"
    assert _extract_wechat_from_text("达人微信号\n首页") == ""
    assert _extract_wechat_from_text("达人微信号\n首页\nDOLA-523") == "DOLA-523"


def test_is_valid_wechat():
    assert not _is_valid_wechat("首页")
    assert not _is_valid_wechat("复制")
    assert not _is_valid_wechat("***")
    assert not _is_valid_wechat("abc")
    assert _is_valid_wechat("DOLA-523")
    assert _is_valid_wechat("wxid_1234")


def test_masked_row_text():
    assert _row_text_has_masked_wechat("达人微信号\n***********\n")
    assert not _row_text_has_masked_wechat("达人微信号\nDOLA-523")
    assert _extract_wechat_from_text("达人微信号\n***********\n") == ""


def test_parse_search_feed_author():
    payload = {
        "data": {
            "list": [
                {
                    "author_tag": ["有联系方式"],
                    "author_base": {
                        "uid": "v2_test",
                        "nickname": "菠萝有品",
                        "fans_num": 844900,
                    },
                },
                {
                    "author_base": {
                        "uid": "v2_other",
                        "nickname": "无联系方式",
                        "fans_num": 1000,
                    },
                },
            ]
        }
    }
    items = parse_search_feed_author(payload)
    assert len(items) == 2
    assert items[0].name == "菠萝有品"
    assert items[0].has_contact is True
    assert items[1].has_contact is False

    contact_only = parse_search_feed_author(payload, contact_only=True)
    assert len(contact_only) == 1
    assert contact_only[0].uid == "v2_test"


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
