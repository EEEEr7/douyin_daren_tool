from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Callable, Optional

from playwright.sync_api import Page, Response

import config
from scraper.daren_square import DarenItem
from scraper.delay_utils import human_delay, profile_ready_jitter
from scraper.page_utils import dismiss_overlays


@dataclass
class DarenContact:
    name: str
    uid: str
    wechat: str | None
    fans_count: str
    profile_url: str
    error: str = ""


WECHAT_LABEL = "达人微信号"
WECHAT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-.]{3,}$")


def _extract_wechat_from_text(text: str) -> str:
    if WECHAT_LABEL in text:
        text = text.split(WECHAT_LABEL, 1)[-1]
    text = text.lstrip("：:").strip()
    for line in text.splitlines():
        line = line.strip().lstrip("：:").strip()
        if not line or line.startswith("达人"):
            continue
        if "*" in line:
            continue
        if WECHAT_PATTERN.match(line):
            return line
        if line:
            return line
    return ""


def _wait_for_profile_ready(page: Page) -> None:
    page.wait_for_function(
        f"() => document.body && document.body.innerText.includes('{WECHAT_LABEL}')",
        timeout=config.PAGE_LOAD_TIMEOUT_MS,
    )
    profile_ready_jitter(page)


def _click_wechat_reveal(page: Page) -> None:
    label = page.get_by_text(WECHAT_LABEL).first
    label.scroll_into_view_if_needed()
    page.wait_for_timeout(random.randint(400, 900))
    container = label.locator("xpath=ancestor::div[1]")
    for _ in range(6):
        icons = container.locator("svg, button, [role='button'], [class*='eye'], [class*='Eye'], img")
        if icons.count() > 0:
            icons.last.click(force=True)
            return
        container = container.locator("xpath=..")
    raise RuntimeError(f"[{config.APP_BRAND}] 未找到微信号 Reveal 按钮")


def _fetch_wechat_via_api(page: Page) -> str:
    revealed = {"value": ""}

    def handle_response(response: Response) -> None:
        if "contact_info" not in response.url or response.status != 200:
            return
        if "contact_mode=2" not in response.url and "contact_mode=3" not in response.url:
            return
        try:
            body = response.json()
        except Exception:
            return
        value = (body.get("data") or {}).get("contact_info", {}).get("contact_value", "")
        if value:
            revealed["value"] = value

    page.on("response", handle_response)
    _click_wechat_reveal(page)
    page.wait_for_timeout(random.randint(2500, 4500))
    return revealed["value"] or _extract_wechat_from_text(page.get_by_text(WECHAT_LABEL).first.inner_text())


def fetch_wechat_for_daren(page: Page, item: DarenItem) -> DarenContact:
    result = DarenContact(
        name=item.name,
        uid=item.uid,
        wechat=None,
        fans_count=item.fans_count,
        profile_url=item.profile_url,
    )

    try:
        page.goto(item.profile_url, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT_MS)
        dismiss_overlays(page)
        _wait_for_profile_ready(page)
        dismiss_overlays(page)

        wechat = _fetch_wechat_via_api(page)
        if not wechat:
            result.error = "未能读取微信号（可能需手动Reveal或权限不足）"
        else:
            result.wechat = wechat

    except Exception as exc:
        result.error = str(exc)

    return result


def fetch_wechat_for_all(
    page: Page,
    items: list[DarenItem],
    *,
    aggressive: bool = False,
    on_item_done: Optional[Callable[[int, int, str, str | None, str], None]] = None,
) -> list[DarenContact]:
    results: list[DarenContact] = []
    total = len(items)

    for index, item in enumerate(items, start=1):
        contact = fetch_wechat_for_daren(page, item)
        results.append(contact)

        if on_item_done:
            on_item_done(index, total, item.name, contact.wechat, contact.error)
        else:
            wechat_display = contact.wechat or f"失败({contact.error})"
            print(f"[{index}/{total}] {item.name} -> {wechat_display}")

        if index < total:
            human_delay(aggressive=aggressive)

    return results
