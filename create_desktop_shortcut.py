from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import config


def _resolve_launch_target(project_root: Path) -> tuple[Path, str]:
    exe_path = project_root / config.APP_EXE_NAME
    if exe_path.exists():
        return exe_path, ""

    pythonw = shutil.which("pythonw") or shutil.which("python")
    if not pythonw:
        raise RuntimeError(f"未找到 {config.APP_EXE_NAME}，也未找到 Python。请先运行 build_exe.bat。")
    return Path(pythonw), str(project_root / "gui.py")


def create_desktop_shortcut() -> Path:
    project_root = Path(__file__).resolve().parent
    desktop = Path.home() / "Desktop"
    shortcut_path = desktop / f"{config.APP_FULL_NAME}.lnk"
    icon_path = project_root / "assets" / "app_icon.ico"
    target_path, arguments = _resolve_launch_target(project_root)

    if not icon_path.exists() and target_path.suffix.lower() != ".exe":
        raise FileNotFoundError(f"未找到图标: {icon_path}")

    icon_location = f"{target_path},0" if target_path.suffix.lower() == ".exe" else f"{icon_path},0"

    ps = f"""
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut('{shortcut_path}')
$link.TargetPath = '{target_path}'
$link.Arguments = '{arguments}'
$link.WorkingDirectory = '{project_root}'
$link.IconLocation = '{icon_location}'
$link.Description = '{config.APP_FULL_NAME} · {config.APP_COPYRIGHT} · {config.APP_AUTHOR}'
$link.Save()
"""

    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "创建快捷方式失败")

    return shortcut_path


def main() -> int:
    try:
        path = create_desktop_shortcut()
    except Exception as exc:
        print(f"[{config.APP_BRAND}] 创建桌面快捷方式失败: {exc}", file=sys.stderr)
        return 1

    print(f"[{config.APP_BRAND}] 桌面快捷方式已创建: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
