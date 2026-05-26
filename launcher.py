"""XTeink 可执行文件入口。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _prepare_runtime() -> None:
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
        os.chdir(root)
        bundled_browsers = root / "ms-playwright"
        if bundled_browsers.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled_browsers)


def main() -> None:
    _prepare_runtime()
    from gui import launch_gui

    launch_gui()


if __name__ == "__main__":
    main()
