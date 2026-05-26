from pathlib import Path
import os
import sys


def _resolve_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _resolve_bundle_dir(base_dir: Path) -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", base_dir))
    return base_dir


BASE_DIR = _resolve_base_dir()
BUNDLE_DIR = _resolve_bundle_dir(BASE_DIR)
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BUNDLE_DIR / "assets" if (BUNDLE_DIR / "assets").exists() else BASE_DIR / "assets"

APP_BRAND = "XTeink"
APP_NAME = "达人微信号采集"
APP_FULL_NAME = f"{APP_BRAND} · {APP_NAME}"
APP_EXE_NAME = "XTeink 抖音达人微信采集.exe"
APP_VERSION = "v1.1.0"
APP_PUBLISHER = "阅星曈"
APP_COPYRIGHT = "© 2026 阅星曈 v1.1.0"
APP_AUTHOR = "Er7"
APP_COPYRIGHT_LINE = APP_COPYRIGHT
APP_TAGLINE = "XTeink · 3C数码家电 + 有联系方式 · 凑满20条即停"
EXCEL_FILENAME = "XTeink_达人联系方式.xlsx"
EXCEL_SHEET_NAME = "XTeink 达人"

AUTH_STATE_PATH = DATA_DIR / "auth.json"
EDGE_CDP_URL = os.environ.get("EDGE_CDP_URL", "http://127.0.0.1:9222")
EDGE_DEBUG_PORT = int(os.environ.get("EDGE_DEBUG_PORT", "9222"))
PROCESSED_UIDS_PATH = DATA_DIR / "processed_uids.json"
DAILY_STATS_PATH = DATA_DIR / "daily_stats.json"
OUTPUT_EXCEL_PATH = OUTPUT_DIR / EXCEL_FILENAME

BASE_URL = "https://buyin.jinritemai.com"
DAREN_SQUARE_URL = f"{BASE_URL}/dashboard/servicehall/daren-square"
DAREN_PROFILE_URL = f"{BASE_URL}/dashboard/servicehall/daren-profile"

CATEGORY_FILTER = "3C数码家电"
CONTACT_FILTER = "有联系方式"

BROWSER = os.environ.get("BROWSER", "edge")

# 单次目标：凑满 20 条微信号立即停止
SESSION_TARGET = 20
RUN_BUDGET_SEC = 60  # 仅用于界面预估参考，不作为停止条件
LIST_CANDIDATE_POOL = 80

DAILY_TARGET = 200
SESSIONS_PER_DAY = 3
PER_SESSION_TARGET = SESSION_TARGET

REQUEST_DELAY_MIN_SEC = 0.1
REQUEST_DELAY_MAX_SEC = 0.3
PROFILE_READY_JITTER_MS = 200
REVEAL_WAIT_MIN_MS = 600
REVEAL_WAIT_MAX_MS = 1000
REVEAL_RESPONSE_TIMEOUT_MS = 5000

PAGE_LOAD_TIMEOUT_MS = 15000
ELEMENT_TIMEOUT_MS = 6000
PROFILE_CHECK_TIMEOUT_MS = 4000

AGGRESSIVE_REQUEST_DELAY_SEC = 0.2
