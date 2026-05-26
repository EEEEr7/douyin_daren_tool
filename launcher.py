"""XTeink 可执行文件入口。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _prepare_runtime() -> None:
    if not getattr(sys, "frozen", False):
        return

    root = Path(sys.executable).resolve().parent
    os.chdir(root)
    # 全程使用系统 Edge，不依赖打包的 Chromium
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")


def main() -> None:
    _prepare_runtime()
    from gui import launch_gui

    launch_gui()


if __name__ == "__main__":
    main()
