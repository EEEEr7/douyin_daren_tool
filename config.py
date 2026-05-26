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
APP_TAGLINE = "XTeink · 精选联盟达人采集 · 稳妥模式 · 每日目标 50 条"
EXCEL_FILENAME = "XTeink_达人联系方式.xlsx"
EXCEL_SHEET_NAME = "XTeink 达人"

AUTH_STATE_PATH = DATA_DIR / "auth.json"
PROCESSED_UIDS_PATH = DATA_DIR / "processed_uids.json"
DAILY_STATS_PATH = DATA_DIR / "daily_stats.json"
OUTPUT_EXCEL_PATH = OUTPUT_DIR / EXCEL_FILENAME

BASE_URL = "https://buyin.jinritemai.com"
DAREN_SQUARE_URL = f"{BASE_URL}/dashboard/servicehall/daren-square"
DAREN_PROFILE_URL = f"{BASE_URL}/dashboard/servicehall/daren-profile"

CATEGORY_FILTER = "3C数码家电"
CONTACT_FILTER = "有联系方式"

BROWSER = os.environ.get("BROWSER", "chromium")
FIREFOX_PROFILE_DIR = os.environ.get("FIREFOX_PROFILE_DIR", "")

# 稳妥模式：每日至少 50 条，早/中/晚各跑 1 次（约 18 条/次，留失败余量）
DAILY_TARGET = 50
SESSIONS_PER_DAY = 3
PER_SESSION_TARGET = 18

# 随机延迟（秒），模拟人工操作
REQUEST_DELAY_MIN_SEC = 5.0
REQUEST_DELAY_MAX_SEC = 12.0
PROFILE_READY_JITTER_MS = 1500

PAGE_LOAD_TIMEOUT_MS = 60000
ELEMENT_TIMEOUT_MS = 15000

# 旧版快速模式参数（仅 --aggressive 时使用）
AGGRESSIVE_REQUEST_DELAY_SEC = 1.5
