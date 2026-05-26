from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, Response

import config
from scraper.page_utils import dismiss_overlays
from scraper.urls import DAREN_SQUARE_FILTERED_URL


@dataclass
class DarenItem:
    name: str
    uid: str
    profile_url: str
    fans_count: str = ""


def _extract_uid_from_href(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    query = parse_qs(parsed.query)
    uid_list = query.get("uid", [])
    if uid_list:
        return uid_list[0]
    match = re.search(r"uid=([^&\"'\\s]+)", href)
    return match.group(1) if match else ""


def _build_profile_url(uid: str) -> str:
    return f"{config.DAREN_PROFILE_URL}?uid={uid}"


def _format_fans_count(fans_num) -> str:
    if fans_num is None:
        return ""
    if isinstance(fans_num, (int, float)):
        if fans_num >= 10000:
            return f"{fans_num / 10000:.2f}万"
        return str(int(fans_num))
    return str(fans_num)


def parse_search_feed_author(payload: dict) -> list[DarenItem]:
    rows = payload.get("data", {}).get("list", [])
    items: list[DarenItem] = []
    seen_uids: set[str] = set()

    for row in rows:
        base = row.get("author_base") or {}
        uid = base.get("uid") or ""
        name = (base.get("nickname") or "").strip()
        if not uid or not name or uid in seen_uids:
            continue
        seen_uids.add(uid)
        items.append(
            DarenItem(
                name=name,
                uid=uid,
                profile_url=_build_profile_url(uid),
                fans_count=_format_fans_count(base.get("fans_num")),
            )
        )
    return items


def _wait_for_list_response(page: Page) -> list[DarenItem]:
    api_items: list[DarenItem] = []

    def handle_response(response: Response) -> None:
        nonlocal api_items
        if "search_feed_author" not in response.url or response.status != 200:
            return
        try:
            payload = response.json()
        except Exception:
            return
        parsed = parse_search_feed_author(payload)
        if parsed:
            api_items = parsed

    page.on("response", handle_response)
    page.goto(DAREN_SQUARE_FILTERED_URL, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT_MS)
    page.wait_for_timeout(8000)
    dismiss_overlays(page)

    if not api_items:
        page.wait_for_timeout(5000)

    return api_items


def _parse_from_dom(page: Page) -> list[DarenItem]:
    links = page.locator('a[href*="daren-profile"]:visible')
    items: list[DarenItem] = []
    seen_uids: set[str] = set()

    for i in range(links.count()):
        link = links.nth(i)
        href = link.get_attribute("href") or ""
        uid = _extract_uid_from_href(href)
        if not uid or uid in seen_uids:
            continue
        seen_uids.add(uid)
        name = link.inner_text().strip().split("\n")[0]
        items.append(
            DarenItem(
                name=name or uid[:20],
                uid=uid,
                profile_url=_build_profile_url(uid),
            )
        )
    return items


def scrape_daren_list(page: Page) -> list[DarenItem]:
    items = _wait_for_list_response(page)
    if not items:
        items = _parse_from_dom(page)

    if not items:
        raise RuntimeError(f"[{config.APP_BRAND}] 第一页未解析到达人，请检查筛选条件或登录权限。")

    print(f"[{config.APP_BRAND}] 第一页共解析到 {len(items)} 位达人")
    return items
