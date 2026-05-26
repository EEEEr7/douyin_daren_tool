from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

import config
from scraper.browser_cookies import sync_auth_from_system_browsers


@dataclass
class BrowserSession:
    playwright: Playwright
    browser: Browser
    context: BrowserContext


def ensure_dirs() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def find_default_firefox_profile() -> Path | None:
    app_data = os.environ.get("APPDATA")
    if not app_data:
        return None

    profiles_ini = Path(app_data) / "Mozilla" / "Firefox" / "profiles.ini"
    if not profiles_ini.exists():
        return None

    parser = configparser.RawConfigParser()
    parser.read(profiles_ini, encoding="utf-8")

    firefox_root = profiles_ini.parent
    default_path: str | None = None

    for section in parser.sections():
        if section.startswith("Install") and parser.has_option(section, "Default"):
            default_path = parser.get(section, "Default")
            break

    if not default_path:
        for section in parser.sections():
            if parser.has_option(section, "Default") and parser.get(section, "Default") == "1":
                default_path = parser.get(section, "Path", fallback=None)
                if default_path:
                    break

    if not default_path:
        return None

    profile_dir = firefox_root / default_path if not Path(default_path).is_absolute() else Path(default_path)
    return profile_dir if profile_dir.exists() else None


def _resolve_firefox_profile(firefox_profile: str | None) -> Path | None:
    if firefox_profile:
        profile_path = Path(firefox_profile).expanduser().resolve()
        if not profile_path.exists():
            raise FileNotFoundError(f"Firefox 配置文件目录不存在: {profile_path}")
        return profile_path

    if config.FIREFOX_PROFILE_DIR:
        profile_path = Path(config.FIREFOX_PROFILE_DIR).expanduser().resolve()
        if profile_path.exists():
            return profile_path

    return find_default_firefox_profile()


def has_saved_auth() -> bool:
    return config.AUTH_STATE_PATH.exists() and config.AUTH_STATE_PATH.stat().st_size > 0


def sync_auth_from_firefox(firefox_profile: str | None = None) -> int:
    count, name = sync_auth_from_system_browsers(firefox_profile)
    print(f"[{config.APP_BRAND}] 已从 {name} 导入 {count} 条 Cookie 到: {config.AUTH_STATE_PATH}")
    return count


def is_logged_in(page: Page) -> bool:
    page.goto(config.DAREN_SQUARE_URL, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT_MS)
    page.wait_for_timeout(2000)

    current_url = page.url.lower()
    if "login" in current_url or "passport" in current_url:
        return False

    login_indicators = [
        page.get_by_text("扫码登录"),
        page.get_by_text("手机号登录"),
        page.get_by_text("请登录"),
    ]
    for indicator in login_indicators:
        try:
            if indicator.count() > 0 and indicator.first.is_visible():
                return False
        except Exception:
            continue

    return True


def manual_login(page: Page, confirm: Callable[[], None] | None = None) -> None:
    page.goto(config.BASE_URL, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT_MS)
    if confirm is None:
        print(f"\n[{config.APP_BRAND}] 请在浏览器窗口中完成登录（支持扫码或账号密码）。")
        print(f"[{config.APP_BRAND}] 登录成功后，确保能正常进入百应后台，然后回到终端按回车继续...")
        input()
    else:
        confirm()


def save_auth_state(context: BrowserContext) -> None:
    ensure_dirs()
    context.storage_state(path=str(config.AUTH_STATE_PATH))


def launch_session(
    *,
    browser_name: str = "chromium",
    headless: bool = False,
    firefox_profile: str | None = None,
    import_browser_auth: bool = True,
    log: Callable[[str], None] | None = None,
) -> BrowserSession:
    ensure_dirs()
    playwright = sync_playwright().start()
    browser_name = browser_name.lower()

    if import_browser_auth:
        try:
            sync_auth_from_system_browsers(firefox_profile, log=log)
        except Exception as exc:
            if not has_saved_auth():
                if log:
                    log(f"浏览器 Cookie 导入失败: {exc}")
            elif log:
                log(f"浏览器 Cookie 导入跳过（将使用已有 auth.json）: {exc}")

    browser = (
        playwright.chromium.launch(headless=headless)
        if browser_name == "chromium"
        else playwright.firefox.launch(headless=headless)
    )

    context_kwargs: dict = {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
    }
    if has_saved_auth():
        context_kwargs["storage_state"] = str(config.AUTH_STATE_PATH)

    context = browser.new_context(**context_kwargs)
    context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """
    )
    return BrowserSession(playwright, browser, context)


def ensure_authenticated(
    session: BrowserSession,
    *,
    force_relogin: bool = False,
    firefox_profile: str | None = None,
    import_browser_auth: bool = True,
    login_confirm: Callable[[], None] | None = None,
    log: Callable[[str], None] | None = None,
) -> None:
    if force_relogin and import_browser_auth:
        try:
            sync_auth_from_system_browsers(firefox_profile, log=log)
        except Exception as exc:
            if log:
                log(f"重新导入 Cookie 失败: {exc}")

    page = session.context.new_page()
    page.set_default_timeout(config.ELEMENT_TIMEOUT_MS)

    try:
        if force_relogin or not has_saved_auth() or not is_logged_in(page):
            if has_saved_auth() and not force_relogin and import_browser_auth:
                if log:
                    log("当前登录态无效，尝试从 Chrome / Edge / Firefox 重新导入...")
                try:
                    sync_auth_from_system_browsers(firefox_profile, log=log)
                    session.context.close()
                    context_kwargs = {
                        "viewport": {"width": 1920, "height": 1080},
                        "user_agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                        ),
                        "storage_state": str(config.AUTH_STATE_PATH),
                    }
                    session.context = session.browser.new_context(**context_kwargs)
                    session.context.add_init_script(
                        """
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        """
                    )
                    page = session.context.new_page()
                    page.set_default_timeout(config.ELEMENT_TIMEOUT_MS)
                    if is_logged_in(page):
                        if log:
                            log("重新导入浏览器 Cookie 后登录成功。")
                        return
                except Exception as exc:
                    if log:
                        log(f"重新导入失败: {exc}")

            manual_login(page, confirm=login_confirm)
            if not is_logged_in(page):
                raise RuntimeError(f"[{config.APP_BRAND}] 登录失败，请确认已在浏览器中登录 buyin.jinritemai.com。")
            save_auth_state(session.context)
            if log:
                log("登录成功，登录态已保存。")
    finally:
        page.close()


def close_session(session: BrowserSession) -> None:
    session.context.close()
    session.browser.close()
    session.playwright.stop()
