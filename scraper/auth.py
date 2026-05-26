from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

import config

WEBDRIVER_HIDE_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""


@dataclass
class BrowserSession:
    playwright: Playwright
    browser: Browser
    context: BrowserContext
    attached: bool = False


def ensure_dirs() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def find_system_edge() -> Path:
    candidates: list[Path] = []
    for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Microsoft" / "Edge" / "Application" / "msedge.exe")

    for path in candidates:
        if path.exists():
            return path

    raise RuntimeError(f"[{config.APP_BRAND}] 未找到 Microsoft Edge，请先安装 Edge。")


def _check_cdp_url(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/json/version", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def discover_edge_cdp_urls() -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for url in (config.EDGE_CDP_URL,):
        if url not in seen:
            urls.append(url)
            seen.add(url)

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        port_file = Path(local_app_data) / "Microsoft" / "Edge" / "User Data" / "DevToolsActivePort"
        if port_file.exists():
            try:
                port = port_file.read_text(encoding="utf-8", errors="ignore").splitlines()[0].strip()
                if port.isdigit():
                    dynamic = f"http://127.0.0.1:{port}"
                    if dynamic not in seen:
                        urls.append(dynamic)
                        seen.add(dynamic)
            except (IndexError, OSError):
                pass

    return urls


def resolve_edge_cdp_url() -> str | None:
    for url in discover_edge_cdp_urls():
        if _check_cdp_url(url):
            return url
    return None


def is_edge_cdp_available() -> bool:
    return resolve_edge_cdp_url() is not None


def has_saved_auth() -> bool:
    return is_edge_cdp_available()


def restart_edge_for_cdp(*, log: Callable[[str], None] | None = None) -> None:
    edge_exe = find_system_edge()
    if log:
        log("正在连接您的 Edge（将短暂重启 Edge，已保存的登录状态会保留）...")

    subprocess.run(
        ["taskkill", "/IM", "msedge.exe", "/F"],
        capture_output=True,
        check=False,
    )
    time.sleep(1.5)

    subprocess.Popen(
        [
            str(edge_exe),
            f"--remote-debugging-port={config.EDGE_DEBUG_PORT}",
            config.DAREN_SQUARE_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )

    for _ in range(40):
        if resolve_edge_cdp_url():
            if log:
                log("Edge 已连接，可直接复用登录态。")
            return
        time.sleep(0.25)

    raise RuntimeError(f"[{config.APP_BRAND}] Edge 重启后仍无法连接，请稍后重试。")


def ensure_edge_cdp_ready(
    *,
    log: Callable[[str], None] | None = None,
    auto_restart: bool = True,
) -> str:
    url = resolve_edge_cdp_url()
    if url:
        if log:
            log("已连接正在运行的 Edge。")
        return url

    if not auto_restart:
        raise RuntimeError(
            f"[{config.APP_BRAND}] 无法连接 Edge。\n"
            "请点击「连接 Edge」，程序会短暂重启 Edge 并保留您的登录状态。"
        )

    restart_edge_for_cdp(log=log)
    url = resolve_edge_cdp_url()
    if url:
        return url

    raise RuntimeError(f"[{config.APP_BRAND}] 无法连接 Edge，请稍后重试。")


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


def save_auth_state(context: BrowserContext) -> None:
    ensure_dirs()
    context.storage_state(path=str(config.AUTH_STATE_PATH))


def connect_to_edge_cdp(*, log: Callable[[str], None] | None = None) -> BrowserSession:
    if sys.platform != "win32":
        raise RuntimeError(f"[{config.APP_BRAND}] 连接已登录 Edge 目前仅支持 Windows。")

    cdp_url = ensure_edge_cdp_ready(log=log, auto_restart=True)

    playwright = sync_playwright().start()
    browser = playwright.chromium.connect_over_cdp(cdp_url)
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    return BrowserSession(playwright, browser, context, attached=True)


def launch_session(
    *,
    browser_name: str = "edge",
    headless: bool = False,
    firefox_profile: str | None = None,
    import_browser_auth: bool = True,
    log: Callable[[str], None] | None = None,
) -> BrowserSession:
    del browser_name, headless, firefox_profile, import_browser_auth

    ensure_dirs()
    if sys.platform == "win32":
        return connect_to_edge_cdp(log=log)

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)
    context_kwargs: dict = {"viewport": {"width": 1920, "height": 1080}}
    if config.AUTH_STATE_PATH.exists() and config.AUTH_STATE_PATH.stat().st_size > 0:
        context_kwargs["storage_state"] = str(config.AUTH_STATE_PATH)
    context = browser.new_context(**context_kwargs)
    context.add_init_script(WEBDRIVER_HIDE_SCRIPT)
    return BrowserSession(playwright, browser, context, attached=False)


def ensure_authenticated(
    session: BrowserSession,
    *,
    force_relogin: bool = False,
    firefox_profile: str | None = None,
    import_browser_auth: bool = True,
    login_confirm: Callable[[], None] | None = None,
    log: Callable[[str], None] | None = None,
) -> None:
    del force_relogin, firefox_profile, import_browser_auth, login_confirm

    page = session.context.new_page()
    page.set_default_timeout(config.ELEMENT_TIMEOUT_MS)

    try:
        if not is_logged_in(page):
            raise RuntimeError(
                f"[{config.APP_BRAND}] Edge 中尚未登录百应（buyin.jinritemai.com）。\n"
                "注意：抖店（fxg.jinritemai.com）与百应不是同一系统。\n"
                "请在 Edge 打开 buyin.jinritemai.com 完成登录后，再点「开始采集」。"
            )
        if log:
            log("已确认 Edge 百应登录态有效。")
    finally:
        page.close()


def close_session(session: BrowserSession) -> None:
    try:
        session.browser.close()
    except Exception:
        pass
    session.playwright.stop()
