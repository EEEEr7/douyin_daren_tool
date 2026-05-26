from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import config

SAME_SITE_MAP = {0: "None", 1: "Lax", 2: "Strict"}
TARGET_HOSTS = ("jinritemai.com", "douyin.com", "bytedance.com")


def _matches_target_host(host: str) -> bool:
    host = host.lstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in TARGET_HOSTS)


def import_firefox_cookies(profile_dir: Path, output_path: Path | None = None) -> int:
    cookies_db = profile_dir / "cookies.sqlite"
    if not cookies_db.exists():
        raise FileNotFoundError(f"未找到 Firefox Cookie 文件: {cookies_db}")

    output_path = output_path or config.AUTH_STATE_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        shutil.copy2(cookies_db, tmp_path)
        conn = sqlite3.connect(tmp_path)
        cursor = conn.execute(
            """
            SELECT name, value, host, path, expiry, isSecure, isHttpOnly, sameSite
            FROM moz_cookies
            """
        )

        cookies = []
        for name, value, host, path, expiry, is_secure, is_http_only, same_site in cursor:
            if not _matches_target_host(host):
                continue
            if not expiry or expiry <= 0:
                expires = -1
            elif expiry > 10**11:
                expires = float(expiry) / 1000
            else:
                expires = float(expiry)
            cookies.append(
                {
                    "name": name,
                    "value": value,
                    "domain": host,
                    "path": path or "/",
                    "expires": expires,
                    "httpOnly": bool(is_http_only),
                    "secure": bool(is_secure),
                    "sameSite": SAME_SITE_MAP.get(same_site, "Lax"),
                }
            )
        conn.close()
    finally:
        tmp_path.unlink(missing_ok=True)

    if not cookies:
        raise RuntimeError(f"[{config.APP_BRAND}] Firefox 中未找到百应 Cookie，请先在 Firefox 登录 buyin.jinritemai.com")

    storage_state = {"cookies": cookies, "origins": []}
    output_path.write_text(json.dumps(storage_state, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(cookies)
