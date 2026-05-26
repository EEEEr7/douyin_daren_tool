from __future__ import annotations

import json
import sys
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Callable

import config
from scraper.edge_profile_auth import sync_auth_from_edge_profile

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


def import_from_edge_legacy(output_path: Path | None = None) -> int:
    """旧版 Edge 的 Cookie 直读方式（Edge 127+ 通常不可用）。"""
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
    del firefox_profile

    if sys.platform == "win32":
        try:
            return sync_auth_from_edge_profile(log=log)
        except Exception as profile_exc:
            if log:
                log(f"Edge 配置读取失败，尝试旧版 Cookie 导入: {profile_exc}")
            try:
                count = import_from_edge_legacy(config.AUTH_STATE_PATH)
                if log:
                    log(f"已从 Edge 导入 {count} 条 Cookie（旧版方式）")
                return count, "Edge"
            except Exception:
                raise RuntimeError(
                    f"[{config.APP_BRAND}] 无法从 Edge 导入登录态。\n"
                    "请确认：\n"
                    "1. 已在 Edge 登录 buyin.jinritemai.com\n"
                    "2. 已完全关闭 Edge（任务管理器无 msedge.exe）\n"
                    "3. 或改用「浏览器内登录」\n"
                    f"详情: {profile_exc}"
                ) from profile_exc

    raise RuntimeError(f"[{config.APP_BRAND}] 从 Edge 导入登录态目前仅支持 Windows，请使用「浏览器内登录」。")
