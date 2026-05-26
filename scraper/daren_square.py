from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, Response

import config
from scraper.page_utils import dismiss_overlays
from scraper.time_estimate import filter_summary
from scraper.urls import DAREN_SQUARE_FILTERED_URL

CONTACT_MARKER = config.CONTACT_FILTER


@dataclass
class DarenItem:
    name: str
    uid: str
    profile_url: str
    fans_count: str = ""
    has_contact: bool = True


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


def _tag_dict_has_contact(tag_dict: dict) -> bool:
    contact_icon = tag_dict.get("contact_icon") or ""
    if CONTACT_MARKER in str(contact_icon):
        return True

    for key in ("author_rec_reasons", "author_label_rec_reasons"):
        reasons = tag_dict.get(key) or []
        if not isinstance(reasons, list):
            continue
        for reason in reasons:
            if isinstance(reason, dict):
                text = reason.get("reason") or reason.get("name") or ""
            else:
                text = str(reason)
            if CONTACT_MARKER in text:
                return True
    return False


def _row_has_contact(row: dict) -> bool:
    base = row.get("author_base") or {}

    for key in ("has_contact", "has_author_contact", "contact_status"):
        value = base.get(key)
        if value in (True, 1, "1"):
            return True
        if value in (False, 0, "0"):
            return False

    for key in ("contact_info", "author_contact_info"):
        contact = row.get(key) or {}
        if contact.get("has_contact") in (True, 1, "1"):
            return True
        mode = contact.get("contact_mode") or contact.get("contact_type")
        if mode in (1, 2, 3, "1", "2", "3"):
            return True

    tag_sources = [
        row.get("author_tag"),
        row.get("tags"),
        base.get("author_tag"),
        base.get("tag_list"),
        base.get("tags"),
    ]
    for tags in tag_sources:
        if not tags:
            continue
        if isinstance(tags, dict):
            if _tag_dict_has_contact(tags):
                return True
            tags = list(tags.values())
        if isinstance(tags, str):
            tags = [tags]
        for tag in tags:
            if isinstance(tag, dict):
                if _tag_dict_has_contact(tag):
                    return True
                text = tag.get("name") or tag.get("text") or tag.get("tag_name") or tag.get("reason") or ""
            else:
                text = str(tag)
            if CONTACT_MARKER in text:
                return True

    return False


def parse_search_feed_author(payload: dict, *, contact_only: bool = False) -> list[DarenItem]:
    rows = payload.get("data", {}).get("list", [])
    items: list[DarenItem] = []
    seen_uids: set[str] = set()

    for row in rows:
        if contact_only and not _row_has_contact(row):
            continue

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
                has_contact=_row_has_contact(row),
            )
        )
    return items


def _click_filter_option(page: Page, row_label: str, option_text: str) -> bool:
    script = """
    ({ rowLabel, optionText }) => {
      const rows = [...document.querySelectorAll('*')].filter(el => {
        const text = (el.innerText || '').trim();
        return text === rowLabel || text.startsWith(rowLabel);
      });
      for (const label of rows) {
        let container = label;
        for (let depth = 0; depth < 8 && container; depth++) {
          const options = [...container.querySelectorAll('*')].filter(el => {
            const t = (el.innerText || '').trim();
            return t === optionText && el.children.length === 0;
          });
          if (options.length) {
            options[0].click();
            return true;
          }
          container = container.parentElement;
        }
      }
      return false;
    }
    """
    clicked = page.evaluate(script, {"rowLabel": row_label, "optionText": option_text})
    if not clicked:
        try:
            page.get_by_text(option_text, exact=True).first.click(force=True)
            clicked = True
        except Exception:
            clicked = False
    page.wait_for_timeout(800)
    return bool(clicked)


def _active_filter_tags(page: Page) -> list[str]:
    tags: list[str] = page.evaluate(
        """
        () => {
          const markers = [];
          for (const el of document.querySelectorAll('*')) {
            const text = (el.innerText || '').trim();
            if (!text || text.length > 30) continue;
            if (text.includes('：') || text.includes(':')) markers.push(text);
          }
          return markers.slice(0, 30);
        }
        """
    )
    return tags


def _filters_applied(page: Page) -> bool:
    return page.evaluate(
        """
        ({ category, contact }) => {
          const body = document.body ? document.body.innerText : '';
          return body.includes(category) && body.includes(contact);
        }
        """,
        {"category": config.CATEGORY_FILTER, "contact": CONTACT_MARKER},
    )


def apply_square_filters(page: Page, *, log: Callable[[str], None] | None = None) -> None:
    dismiss_overlays(page)
    category_ok = _click_filter_option(page, "主推类目", config.CATEGORY_FILTER)
    page.wait_for_timeout(1000)
    contact_ok = _click_filter_option(page, "达人信息", CONTACT_MARKER)
    page.wait_for_timeout(1500)

    if log:
        log(f"已点击筛选：{filter_summary()}")
        if not category_ok:
            log(f"警告：未能点击「{config.CATEGORY_FILTER}」，请检查页面筛选区")
        if not contact_ok:
            log(f"警告：未能点击「{CONTACT_MARKER}」，请检查页面筛选区")

    active = _active_filter_tags(page)
    if log and active:
        log(f"当前筛选标签：{' | '.join(active[:5])}")


def _parse_contact_darens_js(page: Page) -> list[DarenItem]:
    raw = page.evaluate(
        """
        ({ contactMarker, profilePath }) => {
          const results = [];
          const seen = new Set();

          const hasContactBadge = (node) => {
            let current = node;
            for (let depth = 0; depth < 14 && current; depth++) {
              const text = current.innerText || '';
              if (text.includes(contactMarker)) {
                return true;
              }
              current = current.parentElement;
            }
            return false;
          };

          for (const link of document.querySelectorAll(`a[href*="${profilePath}"]`)) {
            if (!hasContactBadge(link)) continue;
            const href = link.href || link.getAttribute('href') || '';
            const match = href.match(/uid=([^&]+)/);
            if (!match) continue;
            const uid = decodeURIComponent(match[1]);
            if (!uid || seen.has(uid)) continue;
            seen.add(uid);
            const name = (link.innerText || '').trim().split('\\n').map(s => s.trim()).filter(Boolean)[0] || uid;
            results.push({ uid, name, href });
          }
          return results;
        }
        """,
        {"contactMarker": CONTACT_MARKER, "profilePath": "daren-profile"},
    )

    items: list[DarenItem] = []
    for row in raw:
        uid = row.get("uid") or ""
        name = (row.get("name") or "").strip()
        if not uid:
            continue
        items.append(
            DarenItem(
                name=name or uid[:20],
                uid=uid,
                profile_url=_build_profile_url(uid),
                has_contact=True,
            )
        )
    return items


def _wait_for_square_list(page: Page, *, timeout_ms: int = 8000) -> None:
    try:
        page.wait_for_function(
            """
            () => {
              const links = document.querySelectorAll('a[href*="daren-profile"]');
              return links.length >= 3;
            }
            """,
            timeout=timeout_ms,
        )
    except Exception:
        pass


def _merge_daren_items(primary: list[DarenItem], secondary: list[DarenItem]) -> list[DarenItem]:
    merged: list[DarenItem] = []
    seen: set[str] = set()
    secondary_map = {item.uid: item for item in secondary}

    for item in primary:
        if item.uid in seen:
            continue
        seen.add(item.uid)
        extra = secondary_map.get(item.uid)
        if extra:
            merged.append(
                DarenItem(
                    name=extra.name or item.name,
                    uid=item.uid,
                    profile_url=item.profile_url,
                    fans_count=extra.fans_count or item.fans_count,
                    has_contact=True,
                )
            )
        else:
            merged.append(item)

    for item in secondary:
        if item.uid not in seen:
            seen.add(item.uid)
            merged.append(item)
    return merged


def scrape_daren_list(page: Page, *, log: Callable[[str], None] | None = None) -> list[DarenItem]:
    if log:
        log(f"正在打开达人广场：{config.DAREN_SQUARE_URL}")
        log(f"目标筛选：{filter_summary()}")

    api_items: list[DarenItem] = []
    api_contact_items: list[DarenItem] = []

    def capture_response(response: Response) -> None:
        nonlocal api_items, api_contact_items
        if "search_feed_author" not in response.url or response.status != 200:
            return
        try:
            payload = response.json()
        except Exception:
            return
        parsed = parse_search_feed_author(payload, contact_only=False)
        if parsed:
            api_items = parsed
        contact_parsed = parse_search_feed_author(payload, contact_only=True)
        if contact_parsed:
            api_contact_items = contact_parsed

    page.on("response", capture_response)

    page.goto(DAREN_SQUARE_FILTERED_URL, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT_MS)
    page.wait_for_timeout(1500)
    dismiss_overlays(page)

    apply_square_filters(page, log=log)
    _wait_for_square_list(page)
    page.wait_for_timeout(2000)
    dismiss_overlays(page)

    if not _filters_applied(page):
        if log:
            log("筛选标签未生效，正在重新应用...")
        apply_square_filters(page, log=log)
        _wait_for_square_list(page)
        page.wait_for_timeout(2000)

    js_items = _parse_contact_darens_js(page)
    if log:
        log(f"API 识别 {len(api_contact_items)} 位 / JS 识别 {len(js_items)} 位带「{CONTACT_MARKER}」标签的达人")

    if api_contact_items:
        js_map = {item.uid: item for item in js_items}
        items = []
        for item in api_contact_items:
            js_item = js_map.get(item.uid)
            items.append(
                DarenItem(
                    name=item.name,
                    uid=item.uid,
                    profile_url=item.profile_url,
                    fans_count=item.fans_count,
                    has_contact=True,
                )
                if not js_item
                else DarenItem(
                    name=item.name or js_item.name,
                    uid=item.uid,
                    profile_url=item.profile_url,
                    fans_count=item.fans_count or js_item.fans_count,
                    has_contact=True,
                )
            )
        js_only = [item for item in js_items if item.uid not in {i.uid for i in items}]
        if js_only:
            items = _merge_daren_items(items, js_only)
    elif js_items:
        items = _merge_daren_items(js_items, api_items)
    else:
        items = []

    if log:
        log(f"最终候选 {len(items)} 位达人")

    if not items:
        raise RuntimeError(
            f"[{config.APP_BRAND}] 未在列表中找到带「{CONTACT_MARKER}」的达人。"
            f"请确认已登录百应，且达人广场已选中「{config.CATEGORY_FILTER}」和「{CONTACT_MARKER}」。"
        )

    if log:
        names = "、".join(item.name for item in items[:5])
        suffix = "..." if len(items) > 5 else ""
        log(f"将依次进入 {len(items)} 位达人主页采集微信：{names}{suffix}")

    return items
