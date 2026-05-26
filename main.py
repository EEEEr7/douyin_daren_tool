from __future__ import annotations

import argparse
import sys
from typing import Callable, Optional

import config
from scraper.auth import close_session, ensure_authenticated, launch_session
from scraper.daily_quota import (
    detect_session,
    format_quota_summary,
    load_daily_stats,
    load_processed_uids,
    mark_uid_processed,
    record_session_run,
    remaining_today,
    session_limit,
)
from scraper.daren_profile import fetch_wechat_for_all
from scraper.daren_square import scrape_daren_list
from scraper.exporter import export_to_excel
from scraper.progress import ConsoleProgress, ProgressReporter, ProgressState


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=config.APP_BRAND,
        description=f"{config.APP_FULL_NAME}（{config.APP_COPYRIGHT}）",
    )
    parser.add_argument("--relogin", action="store_true", help="强制从浏览器重新导入 Cookie")
    parser.add_argument("--headless", action="store_true", help="无头模式运行")
    parser.add_argument(
        "--browser",
        choices=["firefox", "chromium"],
        default="chromium",
        help="自动化浏览器（默认 chromium）",
    )
    parser.add_argument("--firefox-profile", help="Firefox 配置文件目录")
    parser.add_argument("--no-import-firefox", action="store_true", help="不从系统浏览器导入 Cookie")
    parser.add_argument(
        "--session",
        choices=["morning", "noon", "evening", "auto"],
        default="auto",
        help="运行时段（默认 auto 按当前时间判断早/中/晚）",
    )
    parser.add_argument("--limit", type=int, default=0, help="覆盖单次上限（默认按每日配额自动计算）")
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="快速模式：短延迟、忽略每日配额（不推荐）",
    )
    parser.add_argument("--gui", action="store_true", help="启动图形界面")
    parser.add_argument("--cli", action="store_true", help="使用命令行模式（无界面）")
    return parser.parse_args(argv)


def select_items(items, limit: int, processed_uids: set[str]):
    fresh = [item for item in items if item.uid not in processed_uids]
    skipped = len(items) - len(fresh)
    return fresh[:limit], skipped


def run_scraper(
    args: argparse.Namespace,
    progress: Optional[ProgressReporter] = None,
    login_confirm: Callable[[], None] | None = None,
) -> int:
    progress = progress or ConsoleProgress()
    import_browser_auth = not args.no_import_firefox
    session_name = detect_session() if args.session == "auto" else args.session

    stats = load_daily_stats()
    daily_done = int(stats.get("success_count", 0))
    state = ProgressState(
        session=session_name,
        daily_done=daily_done,
        daily_target=config.DAILY_TARGET,
        status="准备中...",
    )
    progress.update(state)

    if args.aggressive:
        run_limit = args.limit if args.limit > 0 else 999
        progress.log("警告: 已启用 --aggressive 快速模式，风控风险更高。")
    else:
        run_limit = args.limit if args.limit > 0 else session_limit(session_name)
        progress.log(format_quota_summary(session_name, run_limit))
        if run_limit <= 0:
            state.status = f"今日目标 {config.DAILY_TARGET} 条已达成"
            progress.update(state)
            progress.log("本次不再抓取。")
            return 0

    session = launch_session(
        browser_name=args.browser,
        headless=args.headless,
        firefox_profile=args.firefox_profile,
        import_browser_auth=import_browser_auth,
        log=progress.log,
    )

    try:
        state.status = "正在验证登录..."
        progress.update(state)
        ensure_authenticated(
            session,
            force_relogin=args.relogin,
            firefox_profile=args.firefox_profile,
            import_browser_auth=import_browser_auth,
            login_confirm=login_confirm,
            log=progress.log,
        )

        page = session.context.new_page()
        page.set_default_timeout(config.ELEMENT_TIMEOUT_MS)

        state.status = "正在加载达人列表..."
        progress.update(state)
        items = scrape_daren_list(page)
        progress.log(f"列表页共 {len(items)} 位达人")

        processed = load_processed_uids()
        items, skipped = select_items(items, run_limit, processed)
        if skipped:
            progress.log(f"已跳过 {skipped} 位历史已抓取达人")

        if not items:
            state.status = "没有可抓取的新达人"
            progress.update(state)
            progress.log("列表为空或均已抓取过。")
            return 0

        state.session_total = len(items)
        state.session_done = 0
        state.status = "正在抓取微信号..."
        progress.update(state)
        progress.log(
            f"本次将处理 {len(items)} 位达人（间隔 {config.REQUEST_DELAY_MIN_SEC}-{config.REQUEST_DELAY_MAX_SEC} 秒）"
        )

        def on_item(index: int, total: int, name: str, wechat: str | None, error: str) -> None:
            state.session_done = index
            state.current_name = name
            display = wechat or (f"失败({error})" if error else "失败")
            state.status = f"已完成 {index}/{total}: {name}"
            progress.update(state)
            progress.log(f"[{index}/{total}] {name} -> {display}")

        contacts = fetch_wechat_for_all(
            page,
            items,
            aggressive=args.aggressive,
            on_item_done=on_item,
        )

        for contact in contacts:
            if contact.wechat:
                mark_uid_processed(contact.uid)

        output_path = export_to_excel(contacts, session_label=session_name)
        success_count = sum(1 for c in contacts if c.wechat)

        if not args.aggressive:
            record_session_run(session_name, success_count)

        daily_done = config.DAILY_TARGET - remaining_today()
        state.daily_done = daily_done
        state.session_done = len(contacts)
        state.output_path = str(output_path)
        state.status = f"完成 {success_count}/{len(contacts)} 条"
        progress.update(state)

        progress.log(f"完成: {success_count}/{len(contacts)} 条微信号已获取")
        if not args.aggressive:
            progress.log(f"今日累计: {daily_done}/{config.DAILY_TARGET}")
        progress.log(f"结果已保存: {output_path}")
        return 0 if success_count > 0 else 1
    except KeyboardInterrupt:
        state.status = "用户中断"
        progress.update(state)
        progress.log("用户中断")
        return 130
    except Exception as exc:
        state.status = f"错误: {exc}"
        progress.update(state)
        progress.log(f"错误: {exc}")
        return 1
    finally:
        close_session(session)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    args = parse_args(argv)
    use_gui = args.gui or not args.cli
    if use_gui and not args.cli:
        from gui import launch_gui

        launch_gui(default_args=args)
        return 0
    return run_scraper(args)


if __name__ == "__main__":
    raise SystemExit(main())
