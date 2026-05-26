from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from playwright.sync_api import sync_playwright

import config

LOCK_FILES = frozenset({"SingletonLock", "SingletonCookie", "lockfile", "LOCK", "DevToolsActivePort"})
SKIP_DIRS = frozenset(
    {
        "Cache",
        "Code Cache",
        "GPUCache",
        "GrShaderCache",
        "ShaderCache",
        "Service Worker",
        "blob_storage",
        "JumpListIconsRecentClosed",
        "JumpListIconsMostVisited",
        "optimization_guide_hint_cache_store",
    }
)


def _edge_user_data_dir() -> Path:
    localappdata = os.environ.get("LOCALAPPDATA")
    if not localappdata:
        raise RuntimeError("未找到 LOCALAPPDATA 环境变量")
    path = Path(localappdata) / "Microsoft" / "Edge" / "User Data"
    if not path.exists():
        raise RuntimeError(f"未找到 Edge 用户数据目录: {path}")
    return path


def default_profile_name(user_data: Path) -> str:
    local_state_path = user_data / "Local State"
    if not local_state_path.exists():
        return "Default"
    try:
        data = json.loads(local_state_path.read_text(encoding="utf-8"))
        return data.get("profile", {}).get("last_used") or "Default"
    except (json.JSONDecodeError, OSError):
        return "Default"


def ensure_edge_closed() -> None:
    if sys.platform != "win32":
        return
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq msedge.exe", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.stdout and "msedge.exe" in result.stdout.lower():
        raise RuntimeError(
            "检测到 Edge 仍在运行。请先完全关闭 Edge（任务管理器中结束所有 msedge.exe 进程）后再导入。"
        )


def _ignore_for_copy(_dir: str, names: list[str]) -> set[str]:
    return {name for name in names if name in LOCK_FILES or name in SKIP_DIRS}


def _copy_edge_profile_snapshot(source: Path, dest: Path, log: Callable[[str], None] | None = None) -> str:
    profile_name = default_profile_name(source)
    profile_src = source / profile_name
    if not profile_src.exists():
        raise RuntimeError(f"未找到 Edge 配置文件: {profile_src}")

    dest.mkdir(parents=True, exist_ok=True)
    if log:
        log(f"正在复制 Edge 配置 ({profile_name})，请稍候...")

    shutil.copy2(source / "Local State", dest / "Local State")
    shutil.copytree(profile_src, dest / profile_name, ignore=_ignore_for_copy, dirs_exist_ok=True)
    return profile_name


def _count_saved_cookies(path: Path) -> int:
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data.get("cookies", []))


def sync_auth_from_edge_profile(*, log: Callable[[str], None] | None = None) -> tuple[int, str]:
    """通过启动系统 Edge 读取已登录配置，绕过新版 Edge 的 Cookie 加密限制。"""
    if sys.platform != "win32":
        raise RuntimeError("从 Edge 导入登录态目前仅支持 Windows。")

    ensure_edge_closed()
    source = _edge_user_data_dir()
    temp_root = Path(tempfile.mkdtemp(prefix="xteink_edge_"))
    snapshot_dir = temp_root / "User Data"

    try:
        _copy_edge_profile_snapshot(source, snapshot_dir, log=log)

        if log:
            log("正在启动 Edge 验证百应登录...")

        from scraper.auth import is_logged_in

        playwright = sync_playwright().start()
        context = None
        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(snapshot_dir),
                channel="msedge",
                headless=False,
                viewport={"width": 1920, "height": 1080},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(config.ELEMENT_TIMEOUT_MS)

            if not is_logged_in(page):
                raise RuntimeError(
                    "Edge 中尚未登录百应。请先在 Edge 打开 buyin.jinritemai.com 完成登录，"
                    "关闭 Edge 后再点「从 Edge 导入」。"
                )

            config.AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(config.AUTH_STATE_PATH))
        finally:
            if context is not None:
                context.close()
            playwright.stop()

        count = _count_saved_cookies(config.AUTH_STATE_PATH)
        if count == 0:
            raise RuntimeError("未能保存任何 Cookie，请确认 Edge 已登录百应。")

        if log:
            log(f"已从 Edge 导出 {count} 条 Cookie")
        return count, "Edge"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
