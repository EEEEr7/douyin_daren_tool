"""打包发给同事的解压即用发布包。"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import config

ROOT = Path(__file__).resolve().parent
RELEASE_ROOT = ROOT / "release"
PACKAGE_DIR = RELEASE_ROOT / "XTeink_达人微信采集"
ZIP_PATH = RELEASE_ROOT / f"XTeink_达人微信采集_{config.APP_VERSION}.zip"
TEMPLATE = ROOT / "release_template"
PLAYWRIGHT_SRC = Path.home() / "AppData" / "Local" / "ms-playwright"


def _ensure_exe() -> Path:
    exe_path = ROOT / config.APP_EXE_NAME
    if exe_path.exists():
        return exe_path

    print("[打包] 未找到 exe，正在构建...")
    subprocess.run(["pyinstaller", "--noconfirm", "--clean", "XTeink.spec"], cwd=ROOT, check=True)
    built = ROOT / "dist" / config.APP_EXE_NAME
    shutil.copy2(built, exe_path)
    return exe_path


def _copy_browsers(target: Path) -> None:
    if not PLAYWRIGHT_SRC.exists():
        raise FileNotFoundError(
            f"未找到 Playwright 浏览器: {PLAYWRIGHT_SRC}\n请在本机先运行: playwright install chromium"
        )

    dest = target / "ms-playwright"
    dest.mkdir(parents=True, exist_ok=True)

    patterns = ("chromium-*", "chromium_headless_shell-*", "ffmpeg-*", "winldd-*")
    copied = 0
    for pattern in patterns:
        matches = sorted(p for p in PLAYWRIGHT_SRC.glob(pattern) if p.is_dir())
        if not matches:
            print(f"[警告] 未找到: {pattern}")
            continue
        src = matches[-1]
        dst = dest / src.name
        if dst.exists():
            shutil.rmtree(dst)
        print(f"[复制] {src.name} ...")
        shutil.copytree(src, dst)
        copied += 1

    if copied == 0:
        raise RuntimeError("未能复制任何浏览器文件，无法打包。")


def package() -> Path:
    print("[打包] 准备发布目录...")
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True)

    _ensure_exe()
    shutil.copy2(ROOT / config.APP_EXE_NAME, PACKAGE_DIR / config.APP_EXE_NAME)

    for name in ("启动.bat", "启动Edge.bat", "创建桌面快捷方式.bat", "使用说明.txt"):
        shutil.copy2(TEMPLATE / name, PACKAGE_DIR / name)

    for name in ("使用说明书.md", "使用说明书.txt"):
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, PACKAGE_DIR / name)

    (PACKAGE_DIR / "data").mkdir(exist_ok=True)
    (PACKAGE_DIR / "output").mkdir(exist_ok=True)
    (PACKAGE_DIR / "data" / ".gitkeep").write_text("", encoding="utf-8")
    (PACKAGE_DIR / "output" / ".gitkeep").write_text("", encoding="utf-8")

    print("[打包] 使用系统 Edge，无需复制 Chromium（体积更小）...")

    print("[打包] 压缩 zip（UTF-8 文件名，避免中文乱码）...")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for path in PACKAGE_DIR.rglob("*"):
            if not path.is_file():
                continue
            arcname = path.relative_to(RELEASE_ROOT).as_posix()
            info = zipfile.ZipInfo(arcname)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits |= 0x800
            zf.writestr(info, path.read_bytes())

    size_mb = ZIP_PATH.stat().st_size / 1024 / 1024
    print(f"[完成] 文件夹: {PACKAGE_DIR}")
    print(f"[完成] 压缩包: {ZIP_PATH} ({size_mb:.1f} MB)")
    return ZIP_PATH


if __name__ == "__main__":
    package()
