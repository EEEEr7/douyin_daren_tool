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
WECHAT_SECTION = "其他信息"
WECHAT_ROW_MARKER = "data-xteink-wechat-row"
WECHAT_MASK_PATTERN = re.compile(r"\*{3,}")
REVEAL_MAX_ATTEMPTS = 3
WECHAT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-.]{3,}$")
INVALID_WECHAT_VALUES = frozenset(
    {
        "首页",
        "复制",
        "查看",
        "联系方式",
        "达人微信号",
        "微信号",
        "点击",
        "小眼睛",
        "暂无",
        "-",
        "--",
    }
)

_FIND_WECHAT_ROW_JS = """
({ label, sectionLabel, marker }) => {
  const hasMask = (text) => /\\*{3,}/.test(text || '');
  const inSection = (el) => {
    let node = el;
    for (let depth = 0; depth < 14 && node; depth++) {
      const text = node.innerText || '';
      if (text.includes(sectionLabel)) return true;
      node = node.parentElement;
    }
    return false;
  };

  document.querySelectorAll(`[${marker}]`).forEach(el => el.removeAttribute(marker));

  const candidates = [...document.querySelectorAll('*')].filter(el => {
    const text = (el.innerText || '').trim();
    if (!text.includes(label)) return false;
    if (!hasMask(text)) return false;
    return text.length <= 140;
  });

  candidates.sort((a, b) => {
    const aSection = inSection(a) ? 0 : 1;
    const bSection = inSection(b) ? 0 : 1;
    if (aSection !== bSection) return aSection - bSection;
    return (a.innerText || '').length - (b.innerText || '').length;
  });

  const row = candidates[0];
  if (!row) return false;
  row.setAttribute(marker, '1');
  row.scrollIntoView({ block: 'center', inline: 'nearest' });
  return true;
}
"""

_CLICK_WECHAT_REVEAL_JS = """
({ marker, strategy }) => {
  const row = document.querySelector(`[${marker}]`);
  if (!row) return false;

  const fireClick = (el) => {
    if (!el) return false;
    try {
      el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    } catch (e) {}
    if (typeof el.click === 'function') el.click();
    return true;
  };

  const isSmallIcon = (el) => {
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.width <= 40 && rect.height <= 40;
  };

  if (strategy === 0 || strategy === 1) {
    const eyeNodes = row.querySelectorAll('[class*="eye" i], [class*="Eye"], [aria-label*="查看" i]');
    if (eyeNodes.length) return fireClick(eyeNodes[eyeNodes.length - 1]);
  }

  if (strategy === 1 || strategy === 2) {
    const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
    let maskNode = null;
    while (walker.nextNode()) {
      if (/\\*{3,}/.test(walker.currentNode.textContent || '')) {
        maskNode = walker.currentNode;
        break;
      }
    }
    if (maskNode && maskNode.parentElement) {
      let sibling = maskNode.parentElement.nextElementSibling;
      while (sibling) {
        const target = sibling.matches('svg, i, span, img, button, [role="button"]')
          ? sibling
          : sibling.querySelector('svg, i, span, img, button, [role="button"]');
        if (target) return fireClick(target);
        sibling = sibling.nextElementSibling;
      }
    }
  }

  const smallSvgs = [...row.querySelectorAll('svg')].filter(isSmallIcon);
  if (smallSvgs.length) return fireClick(smallSvgs[smallSvgs.length - 1]);

  const clickables = row.querySelectorAll('svg, i, span, img, button, [role="button"]');
  if (clickables.length) return fireClick(clickables[clickables.length - 1]);
  return false;
}
"""


def _is_valid_wechat(value: str) -> bool:
    value = (value or "").strip()
    if not value or len(value) < 4:
        return False
    if value in INVALID_WECHAT_VALUES:
        return False
    if "*" in value:
        return False
    if WECHAT_PATTERN.match(value):
        return True
    if re.fullmatch(r"[A-Za-z0-9_\-.]{4,}", value):
        return True
    return False


def _normalize_wechat(value: str) -> str:
    value = (value or "").strip()
    return value if _is_valid_wechat(value) else ""


def _row_text_has_masked_wechat(text: str) -> bool:
    text = text or ""
    return WECHAT_LABEL in text and bool(WECHAT_MASK_PATTERN.search(text))


def _parse_contact_info_value(body: dict) -> str:
    contact = (body.get("data") or {}).get("contact_info") or {}
    value = (contact.get("contact_value") or "").strip()
    return _normalize_wechat(value)


def _extract_wechat_from_text(text: str) -> str:
    if WECHAT_LABEL in text:
        text = text.split(WECHAT_LABEL, 1)[-1]
    text = text.lstrip("：:").strip()
    for line in text.splitlines():
        line = line.strip().lstrip("：:").strip()
        if not line or line.startswith("达人"):
            continue
        if _is_valid_wechat(line):
            return line
    return ""


def _extract_wechat_from_dom(page: Page) -> str:
    raw = page.evaluate(
        """
        ({ label, invalidValues, marker }) => {
          const invalid = new Set(invalidValues);
          const isCandidate = (text) => {
            if (!text || text === label || text.startsWith('达人')) return false;
            if (!text || text.includes('*') || invalid.has(text)) return false;
            if (text.length < 4) return false;
            return /^[A-Za-z0-9][A-Za-z0-9_\\-.]{3,}$/.test(text);
          };

          const pickFromLines = (text) => {
            if (!text) return '';
            const lines = text.split(/\\n+/).map(s => s.trim()).filter(Boolean);
            for (const line of lines) {
              if (isCandidate(line)) return line.replace(/^[:：\\s]+/, '');
            }
            return '';
          };

          const row = document.querySelector(`[${marker}]`);
          if (row) {
            const value = pickFromLines(row.innerText || '');
            if (value) return value;
          }

          const labels = [...document.querySelectorAll('*')].filter(el => {
            const text = (el.innerText || '').trim();
            return text === label || text.startsWith(label + '：') || text.startsWith(label + ':');
          }).sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);

          for (const labelEl of labels) {
            let current = labelEl;
            for (let depth = 0; depth < 6 && current; depth++) {
              const value = pickFromLines(current.innerText || '');
              if (value) return value;
              current = current.parentElement;
            }
          }
          return '';
        }
        """,
        {
            "label": WECHAT_LABEL,
            "invalidValues": sorted(INVALID_WECHAT_VALUES),
            "marker": WECHAT_ROW_MARKER,
        },
    )
    return _normalize_wechat(raw) if raw else ""


def _wechat_already_revealed(page: Page) -> str:
    return _extract_wechat_from_dom(page)


def _find_wechat_row(page: Page) -> bool:
    return bool(
        page.evaluate(
            _FIND_WECHAT_ROW_JS,
            {"label": WECHAT_LABEL, "sectionLabel": WECHAT_SECTION, "marker": WECHAT_ROW_MARKER},
        )
    )


def _scroll_to_wechat_row(page: Page) -> bool:
    found = _find_wechat_row(page)
    if found:
        page.wait_for_timeout(300)
    return found


def _wait_for_profile_ready(page: Page, *, fast: bool = True) -> bool:
    timeout = config.PROFILE_CHECK_TIMEOUT_MS if fast else config.PAGE_LOAD_TIMEOUT_MS
    try:
        page.wait_for_function(
            """
            ({ label }) => {
              const text = document.body ? document.body.innerText : '';
              if (!text.includes(label)) return false;
              if (/\\*{3,}/.test(text)) return true;
              return text.includes(label);
            }
            """,
            arg={"label": WECHAT_LABEL},
            timeout=timeout,
        )
    except Exception:
        return False
    profile_ready_jitter(page, fast=fast)
    return True


def _click_wechat_reveal(page: Page, *, fast: bool = True, strategy: int = 0) -> bool:
    if not _scroll_to_wechat_row(page):
        _find_wechat_row(page)

    clicked = page.evaluate(
        _CLICK_WECHAT_REVEAL_JS,
        {"marker": WECHAT_ROW_MARKER, "strategy": strategy % 3},
    )
    if clicked:
        if not fast:
            page.wait_for_timeout(random.randint(300, 600))
        return True

    row = page.locator(f"[{WECHAT_ROW_MARKER}='1']")
    if row.count() == 0:
        return False

    row.first.scroll_into_view_if_needed()
    if strategy % 3 == 0:
        eye = row.locator("[class*='eye' i], [class*='Eye']").last
        if eye.count() > 0:
            eye.click(force=True)
            return True

    icons = row.locator("svg, i, span, img, button, [role='button']")
    if icons.count() > 0:
        icons.last.click(force=True)
        return True
    return False


def _is_contact_info_response(response: Response) -> bool:
    if "contact_info" not in response.url or response.status != 200:
        return False
    return True


def _poll_wechat_after_click(
    page: Page,
    captured: dict[str, str],
    *,
    timeout_ms: int,
) -> tuple[str, str]:
    deadline = timeout_ms
    step = max(config.REVEAL_WAIT_MIN_MS, 200)
    while deadline > 0:
        if captured.get("value"):
            return captured["value"], "API"
        dom_value = _extract_wechat_from_dom(page)
        if dom_value:
            return dom_value, "DOM"
        wait_ms = min(step, deadline)
        page.wait_for_timeout(wait_ms)
        deadline -= wait_ms
    if captured.get("value"):
        return captured["value"], "API"
    dom_value = _extract_wechat_from_dom(page)
    if dom_value:
        return dom_value, "DOM"
    return "", ""


def _fetch_wechat_via_api(
    page: Page,
    *,
    fast: bool = True,
    log: Callable[[str], None] | None = None,
) -> tuple[str, str]:
    revealed = _wechat_already_revealed(page)
    if revealed:
        return revealed, "DOM已显示"

    captured: dict[str, str] = {"value": ""}

    def handle_response(response: Response) -> None:
        if not _is_contact_info_response(response):
            return
        try:
            value = _parse_contact_info_value(response.json())
        except Exception:
            value = ""
        if value:
            captured["value"] = value

    page.on("response", handle_response)
    per_attempt_timeout = max(config.REVEAL_RESPONSE_TIMEOUT_MS // REVEAL_MAX_ATTEMPTS, 1500)

    try:
        for attempt in range(1, REVEAL_MAX_ATTEMPTS + 1):
            if log:
                log(f"[点击小眼睛] 第 {attempt} 次尝试")

            strategy = attempt - 1
            clicked = False

            if attempt == 1:
                try:
                    with page.expect_response(_is_contact_info_response, timeout=2000) as response_info:
                        clicked = _click_wechat_reveal(page, fast=fast, strategy=strategy)
                    if clicked:
                        try:
                            value = _parse_contact_info_value(response_info.value.json())
                        except Exception:
                            value = ""
                        if value:
                            if log:
                                log("[小眼睛命中] API")
                            return value, "API"
                except Exception:
                    clicked = _click_wechat_reveal(page, fast=fast, strategy=strategy)
            else:
                clicked = _click_wechat_reveal(page, fast=fast, strategy=strategy)

            if not clicked and log:
                log("[小眼睛] 行内图标未点到，继续重试...")

            wechat, source = _poll_wechat_after_click(
                page,
                captured,
                timeout_ms=per_attempt_timeout,
            )
            if wechat:
                if log:
                    log(f"[小眼睛命中] {source}")
                return wechat, source

        if log:
            log("[小眼睛失败] 未找到行内图标或未 reveal")
    finally:
        page.remove_listener("response", handle_response)

    dom_value = _extract_wechat_from_dom(page)
    if dom_value:
        return dom_value, "DOM回退"

    return "", ""


def fetch_wechat_for_daren(
    page: Page,
    item: DarenItem,
    *,
    fast: bool = True,
    log: Callable[[str], None] | None = None,
) -> DarenContact | None:
    if not item.has_contact:
        return None

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

        if not _wait_for_profile_ready(page, fast=fast):
            result.error = "主页无微信号入口，已跳过"
            if log:
                log(f"[跳过] {item.name} -> {result.error}")
            return result

        dismiss_overlays(page)
        wechat, source = _fetch_wechat_via_api(page, fast=fast, log=log)
        if not _is_valid_wechat(wechat or ""):
            result.error = "未能读取微信号，已跳过" if not wechat else "微信号格式无效，已跳过"
            if log:
                log(f"[跳过] {item.name} -> {result.error}")
        else:
            result.wechat = wechat
            if log:
                log(f"[读取] {item.name} -> {wechat} ({source})")

    except Exception as exc:
        result.error = str(exc)
        if log:
            log(f"[跳过] {item.name} -> {result.error}")

    return result


def fetch_wechat_collect(
    page: Page,
    items: list[DarenItem],
    *,
    target_count: int | None = None,
    fast: bool = True,
    on_item_done: Optional[
        Callable[[int, int, int, str, str | None, str], None]
    ] = None,
    log: Callable[[str], None] | None = None,
) -> list[DarenContact]:
    target_count = target_count or config.SESSION_TARGET
    successes: list[DarenContact] = []
    attempted = 0

    for item in items:
        if len(successes) >= target_count:
            break

        attempted += 1
        contact = fetch_wechat_for_daren(page, item, fast=fast, log=log)
        if contact is None:
            continue

        if contact.wechat:
            successes.append(contact)
            if on_item_done:
                on_item_done(len(successes), target_count, attempted, item.name, contact.wechat, "")
        else:
            if on_item_done:
                on_item_done(len(successes), target_count, attempted, item.name, None, contact.error)

        if len(successes) < target_count:
            human_delay(fast=fast)

    return successes


def fetch_wechat_for_all(
    page: Page,
    items: list[DarenItem],
    *,
    aggressive: bool = False,
    on_item_done: Optional[Callable[[int, int, str, str | None, str], None]] = None,
) -> list[DarenContact]:
    del aggressive

    def bridge(successes: int, target: int, attempted: int, name: str, wechat: str | None, error: str) -> None:
        if on_item_done:
            on_item_done(attempted, target, name, wechat, error)

    return fetch_wechat_collect(page, items, on_item_done=bridge if on_item_done else None)
