from __future__ import annotations

import argparse
import sys
import time
from typing import Callable, Optional

import config
from scraper.auth import close_session, ensure_authenticated, launch_session
from scraper.daily_quota import detect_session, load_processed_uids, mark_uid_processed, record_session_run
from scraper.daren_profile import fetch_wechat_collect
from scraper.daren_square import scrape_daren_list
from scraper.exporter import export_to_excel
from scraper.progress import ConsoleProgress, ProgressReporter, ProgressState
from scraper.time_estimate import filter_summary, format_duration, format_eta_text


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
    parser.add_argument("--relogin", action="store_true", help="开始前重新验证 Edge 登录态")
    parser.add_argument("--headless", action="store_true", help="无头模式运行")
    parser.add_argument(
        "--browser",
        choices=["edge", "chromium", "firefox"],
        default="edge",
        help="自动化浏览器（Windows 默认 Edge）",
    )
    parser.add_argument("--firefox-profile", help="（已弃用）保留兼容")
    parser.add_argument("--no-import-firefox", action="store_true", help="（已弃用）保留兼容")
    parser.add_argument(
        "--session",
        choices=["morning", "noon", "evening", "auto"],
        default="auto",
        help="运行时段（默认 auto 按当前时间判断早/中/晚）",
    )
    parser.add_argument("--limit", type=int, default=0, help="覆盖单次目标条数（默认 20）")
    parser.add_argument("--aggressive", action="store_true", help="（已弃用）保留兼容")
    parser.add_argument("--gui", action="store_true", help="启动图形界面")
    parser.add_argument("--cli", action="store_true", help="使用命令行模式（无界面）")
    return parser.parse_args(argv)


def run_scraper(
    args: argparse.Namespace,
    progress: Optional[ProgressReporter] = None,
    login_confirm: Callable[[], None] | None = None,
) -> int:
    del login_confirm
    progress = progress or ConsoleProgress()
    import_browser_auth = not args.no_import_firefox
    session_name = detect_session() if args.session == "auto" else args.session
    target_count = args.limit if args.limit > 0 else config.SESSION_TARGET

    state = ProgressState(
        session=session_name,
        daily_done=0,
        daily_target=target_count,
        status="准备中...",
    )
    progress.update(state)
    progress.log(
        f"目标：{filter_summary()} · 凑满 {target_count} 个微信号立即停止"
    )

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
            log=progress.log,
        )

        page = session.context.new_page()
        page.set_default_timeout(config.ELEMENT_TIMEOUT_MS)

        state.status = "正在加载达人列表..."
        progress.update(state)
        items = scrape_daren_list(page, log=progress.log)

        processed = load_processed_uids()
        candidates = [item for item in items if item.uid not in processed]
        skipped = len(items) - len(candidates)
        items = candidates[: config.LIST_CANDIDATE_POOL]

        if skipped:
            progress.log(f"已跳过 {skipped} 位历史已抓取达人")

        if not items:
            state.status = "没有可抓取的新达人"
            progress.update(state)
            progress.log("列表为空或均已抓取过。")
            return 0

        state.session_total = target_count
        state.session_done = 0
        state.eta_text = format_eta_text(0, target_count, 0, fast=True)
        state.status = "正在抓取微信号..."
        progress.update(state)
        progress.log(f"候选 {len(items)} 位（均有联系方式），凑满 {target_count} 条成功即停止")

        scrape_started_at = time.monotonic()

        def on_item(
            successes: int,
            target: int,
            attempted: int,
            name: str,
            wechat: str | None,
            error: str,
        ) -> None:
            elapsed = time.monotonic() - scrape_started_at
            state.session_done = successes
            state.session_total = target
            state.current_name = name
            state.eta_text = format_eta_text(successes, target, elapsed, fast=True)
            if wechat:
                state.status = f"已获取 {successes}/{target}（第 {attempted} 位）"
                progress.log(f"[{successes}/{target}] {name} -> {wechat} | {state.eta_text}")
            else:
                state.status = f"跳过无微信号 {name}"
                progress.log(f"[跳过] {name} -> {error or '无微信号'}")
            progress.update(state)

        contacts = fetch_wechat_collect(
            page,
            items,
            target_count=target_count,
            fast=True,
            on_item_done=on_item,
            log=progress.log,
        )

        for contact in contacts:
            mark_uid_processed(contact.uid)

        output_path = export_to_excel(contacts, session_label=session_name)
        success_count = len(contacts)
        record_session_run(session_name, success_count)

        elapsed_total = time.monotonic() - scrape_started_at
        state.session_done = success_count
        state.eta_text = f"耗时 {format_duration(int(elapsed_total))}"
        state.output_path = str(output_path)
        state.status = f"完成 {success_count}/{target_count} 条"
        progress.update(state)

        progress.log(
            f"完成: 导出 {success_count} 条微信号到 Excel，耗时 {format_duration(int(elapsed_total))}"
        )
        progress.log(f"结果已保存: {output_path}")

        if success_count < target_count:
            progress.log(
                f"提示: 本次获取 {success_count}/{target_count} 条，"
                "当前页符合「有联系方式」的候选已用尽，可稍后重试或翻页后再跑。"
            )

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
