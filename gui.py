from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

import config
from main import parse_args, run_scraper
from scraper.auth import (
    close_session,
    has_saved_auth,
    is_logged_in,
    launch_session,
    manual_login,
    save_auth_state,
)
from scraper.browser_cookies import sync_auth_from_system_browsers
from scraper.progress import CallbackProgress, ProgressState

SESSION_LABELS = {
    "auto": "自动（按当前时间）",
    "morning": "上午",
    "noon": "下午",
    "evening": "晚上",
}

ASSETS_DIR = config.ASSETS_DIR
APP_ICON_ICO = ASSETS_DIR / "app_icon.ico"
APP_ICON_PNG = ASSETS_DIR / "app_icon_512.png"
APP_LOGO = ASSETS_DIR / "app_icon.png"
APP_ID = "xteink.daren.tool.v1.1.0.opaque"

COLORS = {
    "bg": "#f4f6f8",
    "surface": "#ffffff",
    "topbar": "#ffffff",
    "border": "#e5e7eb",
    "text": "#111827",
    "muted": "#6b7280",
    "accent": "#ff6a00",
    "accent_hover": "#e85d00",
    "accent_soft": "#fff4eb",
    "success": "#059669",
    "success_bg": "#ecfdf5",
    "warning": "#d97706",
    "warning_bg": "#fffbeb",
    "footer": "#f9fafb",
    "log_bg": "#0f172a",
    "log_fg": "#e2e8f0",
    "badge_bg": "#111827",
    "badge_fg": "#ffffff",
}


def configure_windows_app() -> None:
    if sys.platform != "win32":
        return

    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def set_window_icon(root: tk.Tk) -> tk.PhotoImage | None:
    if sys.platform == "win32" and APP_ICON_ICO.exists():
        ico_path = str(APP_ICON_ICO.resolve())
        root.iconbitmap(default=ico_path)
        root.wm_iconbitmap(ico_path)
        return None

    for candidate in (APP_ICON_PNG, ASSETS_DIR / "app_icon_256.png", APP_LOGO):
        if not candidate.exists():
            continue
        try:
            icon_ref = tk.PhotoImage(file=str(candidate.resolve()))
            root.iconphoto(True, icon_ref)
            return icon_ref
        except Exception:
            continue
    return None


def load_header_logo() -> tk.PhotoImage | None:
    if not APP_LOGO.exists():
        return None
    try:
        from PIL import Image, ImageTk

        image = Image.open(APP_LOGO).convert("RGBA")
        width, height = image.size
        target_width = 168
        target_height = max(1, int(height * target_width / width))
        image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)
    except Exception:
        return None


class ScraperApp:
    def __init__(self, default_args: argparse.Namespace | None = None) -> None:
        configure_windows_app()
        self.root = tk.Tk()
        self.root.title(config.APP_FULL_NAME)
        self.root.geometry("1400x1000")
        self.root.minsize(1200, 900)
        self.root.configure(bg=COLORS["bg"])
        self._window_icon = set_window_icon(self.root)
        self._header_logo = load_header_logo()

        self.default_args = default_args or parse_args(["--cli"])
        self.worker: threading.Thread | None = None
        self.running = False
        self.login_running = False
        self.last_output_path: str | None = None

        self.session_var = tk.StringVar(value=self.default_args.session)
        self.relogin_var = tk.BooleanVar(value=self.default_args.relogin)

        self.daily_var = tk.StringVar(value=f"今日进度  0 / {config.DAILY_TARGET}")
        self.session_var_text = tk.StringVar(value="本次进度  0 / 0")
        self.status_var = tk.StringVar(value="就绪")
        self.current_var = tk.StringVar(value="当前达人：-")
        self.auth_var = tk.StringVar(value="检查登录状态中...")

        self._setup_styles()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._refresh_auth_status)

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["surface"])
        style.configure("Topbar.TFrame", background=COLORS["topbar"])
        style.configure("Footer.TFrame", background=COLORS["footer"])
        style.configure("CardTitle.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("TopMuted.TLabel", background=COLORS["topbar"], foreground=COLORS["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("Brand.TLabel", background=COLORS["topbar"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 15, "bold"))
        style.configure("Tagline.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Microsoft YaHei UI", 10))
        style.configure("Status.TLabel", background=COLORS["surface"], foreground=COLORS["accent"], font=("Microsoft YaHei UI", 10))
        style.configure("Metric.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("AuthOk.TLabel", background=COLORS["success_bg"], foreground=COLORS["success"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("AuthWarn.TLabel", background=COLORS["warning_bg"], foreground=COLORS["warning"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Version.TLabel", background=COLORS["badge_bg"], foreground=COLORS["badge_fg"], font=("Microsoft YaHei UI", 9, "bold"))
        style.configure("Footer.TLabel", background=COLORS["footer"], foreground=COLORS["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("FooterBrand.TLabel", background=COLORS["footer"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 9, "bold"))

        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=(16, 9))
        style.map(
            "Accent.TButton",
            background=[("active", COLORS["accent_hover"]), ("!disabled", COLORS["accent"])],
            foreground=[("!disabled", "#ffffff")],
        )
        style.configure("Secondary.TButton", font=("Microsoft YaHei UI", 10), padding=(12, 8))
        style.configure("TCombobox", padding=4)
        style.configure("TProgressbar", troughcolor="#eef2f7", background=COLORS["accent"], thickness=12)
        style.configure("TLabelframe", background=COLORS["surface"], bordercolor=COLORS["border"])
        style.configure("TLabelframe.Label", background=COLORS["surface"], foreground=COLORS["muted"], font=("Microsoft YaHei UI", 9))

    def _card(self, parent: tk.Misc, title: str | None = None, *, expand: bool = False) -> ttk.Frame:
        outer = tk.Frame(parent, bg=COLORS["border"], padx=1, pady=1)
        outer.pack(fill="both" if expand else "x", padx=20, pady=5, expand=expand)
        card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        card.pack(fill="both", expand=expand)
        if title:
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 12))
        return card

    def _build_topbar(self) -> None:
        topbar_wrap = tk.Frame(self.root, bg=COLORS["border"])
        topbar_wrap.pack(fill="x", pady=(0, 1))
        topbar = ttk.Frame(topbar_wrap, style="Topbar.TFrame", padding=(20, 14))
        topbar.pack(fill="x")

        brand_row = ttk.Frame(topbar, style="Topbar.TFrame")
        brand_row.pack(side="left", fill="x", expand=True)

        if self._header_logo is not None:
            logo_label = tk.Label(brand_row, image=self._header_logo, bg=COLORS["topbar"], borderwidth=0)
            logo_label.pack(side="left", padx=(0, 14))
        else:
            ttk.Label(brand_row, text=config.APP_BRAND, style="Brand.TLabel").pack(side="left", padx=(0, 10))

        text_col = ttk.Frame(brand_row, style="Topbar.TFrame")
        text_col.pack(side="left", fill="y")
        ttk.Label(text_col, text=config.APP_NAME, style="Brand.TLabel").pack(anchor="w")
        ttk.Label(text_col, text=config.APP_TAGLINE, style="TopMuted.TLabel").pack(anchor="w", pady=(2, 0))

    def _build_footer(self, parent: tk.Misc) -> None:
        footer_wrap = tk.Frame(parent, bg=COLORS["border"])
        footer_wrap.pack(fill="x", side="bottom", pady=(1, 0))
        footer = ttk.Frame(footer_wrap, style="Footer.TFrame", padding=(20, 10))
        footer.pack(fill="x")

        ttk.Label(footer, text=f"{config.APP_BRAND} · {config.APP_NAME}", style="FooterBrand.TLabel").pack(side="left")
        ttk.Label(
            footer,
            text=f"{config.APP_COPYRIGHT} · {config.APP_AUTHOR}",
            style="Footer.TLabel",
        ).pack(side="right")

    def _build_ui(self) -> None:
        self._build_topbar()

        body = ttk.Frame(self.root)
        body.pack(fill="x")

        auth_card = self._card(body, "登录状态")
        auth_row = ttk.Frame(auth_card, style="Card.TFrame")
        auth_row.pack(fill="x")

        self.auth_badge = ttk.Label(auth_row, textvariable=self.auth_var, style="AuthWarn.TLabel", padding=(10, 6))
        self.auth_badge.pack(side="left")

        ttk.Button(auth_row, text="从浏览器导入", style="Secondary.TButton", command=self.import_auth).pack(side="right", padx=(6, 0))
        ttk.Button(auth_row, text="浏览器内登录", style="Secondary.TButton", command=self.browser_login).pack(side="right", padx=(6, 0))

        ttk.Label(
            auth_card,
            text="先在 Chrome 或 Edge 登录 buyin.jinritemai.com，再点「从浏览器导入」；或直接「浏览器内登录」。",
            style="Muted.TLabel",
            wraplength=820,
        ).pack(anchor="w", pady=(10, 0))

        middle = ttk.Frame(body)
        middle.pack(fill="x")
        middle.columnconfigure(0, weight=1)
        middle.columnconfigure(1, weight=1)

        settings_outer = tk.Frame(middle, bg=COLORS["border"], padx=1, pady=1)
        settings_outer.grid(row=0, column=0, sticky="nsew", padx=(20, 8), pady=5)
        settings_card = ttk.Frame(settings_outer, style="Card.TFrame", padding=16)
        settings_card.pack(fill="both", expand=True)
        ttk.Label(settings_card, text="运行设置", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 12))

        ttk.Label(settings_card, text="运行时段", style="Metric.TLabel").pack(anchor="w")
        session_box = ttk.Combobox(
            settings_card,
            textvariable=self.session_var,
            values=list(SESSION_LABELS.keys()),
            state="readonly",
            width=22,
        )
        session_box.pack(anchor="w", pady=(6, 4))
        session_box.bind("<<ComboboxSelected>>", lambda _e: self._refresh_session_label())
        self.session_hint = ttk.Label(settings_card, text=SESSION_LABELS[self.session_var.get()], style="Muted.TLabel")
        self.session_hint.pack(anchor="w", pady=(0, 12))
        ttk.Checkbutton(settings_card, text="重新导入浏览器登录", variable=self.relogin_var).pack(anchor="w")

        progress_outer = tk.Frame(middle, bg=COLORS["border"], padx=1, pady=1)
        progress_outer.grid(row=0, column=1, sticky="nsew", padx=(8, 20), pady=5)
        progress_card = ttk.Frame(progress_outer, style="Card.TFrame", padding=16)
        progress_card.pack(fill="both", expand=True)
        ttk.Label(progress_card, text="采集进度", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 12))

        ttk.Label(progress_card, textvariable=self.daily_var, style="Metric.TLabel").pack(anchor="w")
        self.daily_bar = ttk.Progressbar(progress_card, maximum=config.DAILY_TARGET, mode="determinate")
        self.daily_bar.pack(fill="x", pady=(6, 12))

        ttk.Label(progress_card, textvariable=self.session_var_text, style="Metric.TLabel").pack(anchor="w")
        self.session_bar = ttk.Progressbar(progress_card, maximum=1, mode="determinate")
        self.session_bar.pack(fill="x", pady=(6, 12))

        ttk.Label(progress_card, textvariable=self.current_var, style="Muted.TLabel", wraplength=360).pack(anchor="w")
        ttk.Label(progress_card, textvariable=self.status_var, style="Status.TLabel", wraplength=360).pack(anchor="w", pady=(8, 0))

        log_card = self._card(body, "运行日志")
        self.log_box = scrolledtext.ScrolledText(
            log_card,
            height=8,
            wrap="word",
            font=("Consolas", 10),
            bg=COLORS["log_bg"],
            fg=COLORS["log_fg"],
            insertbackground=COLORS["log_fg"],
            relief="flat",
            padx=10,
            pady=8,
        )
        self.log_box.pack(fill="x")
        self.log_box.configure(state="disabled")

        action_wrap = ttk.Frame(body)
        action_wrap.pack(fill="x", padx=20, pady=(8, 12))
        self.start_btn = ttk.Button(action_wrap, text="开始采集", style="Accent.TButton", command=self.start)
        self.start_btn.pack(side="left")
        ttk.Button(action_wrap, text="打开结果文件夹", style="Secondary.TButton", command=self.open_output_dir).pack(side="left", padx=10)
        ttk.Button(action_wrap, text="退出", style="Secondary.TButton", command=self._on_close).pack(side="right")

        self._build_footer(self.root)

    def _refresh_session_label(self) -> None:
        self.session_hint.configure(text=SESSION_LABELS.get(self.session_var.get(), ""))

    def _set_auth_status(self, ok: bool, message: str) -> None:
        self.auth_var.set(message)
        style = "AuthOk.TLabel" if ok else "AuthWarn.TLabel"
        self.auth_badge.configure(style=style)

    def _refresh_auth_status(self) -> None:
        if has_saved_auth():
            self._set_auth_status(True, "已保存登录态（auth.json）")
        else:
            self._set_auth_status(False, "未登录 · 请先导入或浏览器内登录")

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _update_progress(self, state: ProgressState) -> None:
        self.daily_var.set(f"今日进度  {state.daily_done} / {state.daily_target}")
        self.daily_bar["maximum"] = max(state.daily_target, 1)
        self.daily_bar["value"] = state.daily_done

        total = max(state.session_total, 1)
        self.session_var_text.set(f"本次进度  {state.session_done} / {state.session_total or '?'}")
        self.session_bar["maximum"] = total
        self.session_bar["value"] = state.session_done

        current = state.current_name or "-"
        self.current_var.set(f"当前达人：{current}")
        self.status_var.set(state.status)
        if state.output_path:
            self.last_output_path = state.output_path

    def _make_progress(self) -> CallbackProgress:
        def on_update(state: ProgressState) -> None:
            self.root.after(0, lambda s=state: self._update_progress(s))

        def on_log(message: str) -> None:
            self.root.after(0, lambda m=message: self._append_log(m))

        return CallbackProgress(on_update=on_update, on_log=on_log)

    def _make_login_confirm(self):
        def confirm() -> None:
            done = threading.Event()

            def ask() -> None:
                messagebox.showinfo(config.APP_BRAND, "请在打开的浏览器窗口完成百应登录，完成后点击确定。")
                done.set()

            self.root.after(0, ask)
            done.wait()

        return confirm

    def import_auth(self) -> None:
        if self.running or self.login_running:
            return

        self.login_running = True
        self._append_log(f"—— {config.APP_BRAND} · 正在从浏览器导入登录 ——")

        def worker() -> None:
            try:
                count, name = sync_auth_from_system_browsers(log=lambda m: self.root.after(0, lambda msg=m: self._append_log(msg)))
                self.root.after(0, lambda: self._set_auth_status(True, f"已从 {name} 导入 {count} 条 Cookie"))
                self.root.after(0, lambda: self._append_log(f"导入成功：{name}，{count} 条 Cookie"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror(f"{config.APP_BRAND} · 导入失败", str(exc)))
                self.root.after(0, lambda: self._append_log(f"导入失败: {exc}"))
            finally:
                self.login_running = False

        threading.Thread(target=worker, daemon=True).start()

    def browser_login(self) -> None:
        if self.running or self.login_running:
            return

        self.login_running = True
        self._append_log("—— 打开浏览器，请完成登录 ——")
        confirm_event = threading.Event()

        def confirm() -> None:
            done = threading.Event()

            def ask() -> None:
                if messagebox.askokcancel(config.APP_BRAND, "请在浏览器窗口完成 buyin.jinritemai.com 登录，完成后点确定。"):
                    confirm_event.set()
                done.set()

            self.root.after(0, ask)
            done.wait()

        def worker() -> None:
            session = None
            try:
                session = launch_session(browser_name="chromium", headless=False, import_browser_auth=False)
                page = session.context.new_page()
                page.set_default_timeout(config.ELEMENT_TIMEOUT_MS)
                manual_login(page, confirm=confirm)

                if not confirm_event.is_set():
                    raise RuntimeError("已取消登录")

                if not is_logged_in(page):
                    raise RuntimeError(f"[{config.APP_BRAND}] 登录验证失败，请确认已成功进入百应后台")

                save_auth_state(session.context)
                self.root.after(0, lambda: self._set_auth_status(True, "浏览器内登录成功"))
                self.root.after(0, lambda: self._append_log("浏览器内登录成功，登录态已保存"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror(f"{config.APP_BRAND} · 登录失败", str(exc)))
                self.root.after(0, lambda: self._append_log(f"登录失败: {exc}"))
            finally:
                if session:
                    close_session(session)
                self.login_running = False

        threading.Thread(target=worker, daemon=True).start()

    def start(self) -> None:
        if self.running or self.login_running:
            return

        if not has_saved_auth():
            if not messagebox.askyesno(config.APP_BRAND, "尚未保存登录态，是否继续？建议先点「从浏览器导入」或「浏览器内登录」。"):
                return

        self.running = True
        self.start_btn.configure(state="disabled")
        self._append_log(f"—— {config.APP_FULL_NAME} 开始采集 ——")

        args = argparse.Namespace(**vars(self.default_args))
        args.session = self.session_var.get()
        args.relogin = self.relogin_var.get()
        args.gui = False
        args.cli = True
        args.headless = False
        args.browser = "chromium"

        progress = self._make_progress()
        login_confirm = self._make_login_confirm()

        def worker() -> None:
            try:
                exit_code = run_scraper(args, progress=progress, login_confirm=login_confirm)
                self.root.after(0, lambda: self._on_finished(exit_code))
            except Exception as exc:
                self.root.after(0, lambda: self._on_finished(1, str(exc)))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _on_finished(self, exit_code: int, error: str = "") -> None:
        self.running = False
        self.start_btn.configure(state="normal")
        self._refresh_auth_status()
        if error:
            messagebox.showerror(f"{config.APP_BRAND} · 运行失败", error)
        elif exit_code == 0:
            messagebox.showinfo(config.APP_BRAND, "本次采集已完成，请查看结果文件夹。")
        elif exit_code != 130:
            messagebox.showwarning(config.APP_BRAND, "本次采集未获取到微信号，请查看日志。")

    def open_output_dir(self) -> None:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = self.last_output_path or str(config.OUTPUT_DIR.resolve())
        folder = str(Path(path).parent if path.endswith(".xlsx") else path)
        if sys.platform == "win32":
            subprocess.run(["explorer", folder], check=False)
        else:
            subprocess.run(["xdg-open", folder], check=False)

    def _on_close(self) -> None:
        if self.running or self.login_running:
            if not messagebox.askyesno(config.APP_BRAND, "任务仍在运行，确定要退出吗？"):
                return
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def launch_gui(default_args: argparse.Namespace | None = None) -> None:
    app = ScraperApp(default_args=default_args)
    app.run()


if __name__ == "__main__":
    launch_gui()
