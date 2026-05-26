from __future__ import annotations

import json
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Callable

import config
from scraper.firefox_cookies import import_firefox_cookies

TARGET_DOMAINS = ("jinritemai.com", "douyin.com")


def _cookiejar_to_playwright(cj: CookieJar) -> list[dict]:
    cookies: list[dict] = []
    for cookie in cj:
        expires = cookie.expires if cookie.expires else -1
        if expires and expires > 10**11:
            expires = expires / 1000
        cookies.append(
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path or "/",
                "expires": float(expires) if expires != -1 else -1,
                "httpOnly": False,
                "secure": bool(cookie.secure),
                "sameSite": "Lax",
            }
        )
    return cookies


def _dedupe_cookies(cookies: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    unique: list[dict] = []
    for cookie in cookies:
        key = (cookie["name"], cookie["domain"], cookie["path"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(cookie)
    return unique


def _save_cookies(cookies: list[dict], output_path: Path | None = None) -> int:
    if not cookies:
        raise RuntimeError("未找到抖店/百应相关 Cookie")
    output_path = output_path or config.AUTH_STATE_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    storage_state = {"cookies": cookies, "origins": []}
    output_path.write_text(json.dumps(storage_state, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(cookies)


def import_from_chrome(output_path: Path | None = None) -> int:
    try:
        import browser_cookie3
    except ImportError as exc:
        raise RuntimeError("未安装 browser-cookie3") from exc

    cookies: list[dict] = []
    for domain in TARGET_DOMAINS:
        jar = browser_cookie3.chrome(domain_name=domain)
        cookies.extend(_cookiejar_to_playwright(jar))
    return _save_cookies(_dedupe_cookies(cookies), output_path)


def import_from_edge(output_path: Path | None = None) -> int:
    try:
        import browser_cookie3
    except ImportError as exc:
        raise RuntimeError("未安装 browser-cookie3") from exc

    cookies: list[dict] = []
    for domain in TARGET_DOMAINS:
        jar = browser_cookie3.edge(domain_name=domain)
        cookies.extend(_cookiejar_to_playwright(jar))
    return _save_cookies(_dedupe_cookies(cookies), output_path)


def sync_auth_from_system_browsers(
    firefox_profile: str | None = None,
    *,
    log: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    from scraper.auth import _resolve_firefox_profile

    attempts: list[tuple[str, Callable[[], int]]] = []

    profile_dir = _resolve_firefox_profile(firefox_profile)
    if profile_dir:
        attempts.append(("Firefox", lambda: import_firefox_cookies(profile_dir, config.AUTH_STATE_PATH)))

    attempts.extend(
        [
            ("Chrome", lambda: import_from_chrome(config.AUTH_STATE_PATH)),
            ("Edge", lambda: import_from_edge(config.AUTH_STATE_PATH)),
        ]
    )

    errors: list[str] = []
    for name, importer in attempts:
        try:
            count = importer()
            message = f"已从 {name} 导入 {count} 条 Cookie"
            if log:
                log(message)
            return count, name
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    raise RuntimeError(f"[{config.APP_BRAND}] 无法从浏览器导入登录态，请使用「浏览器内登录」。\n" + "\n".join(errors))
