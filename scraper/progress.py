from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

import config


@dataclass
class ProgressState:
    session: str = ""
    daily_done: int = 0
    daily_target: int = 50
    session_done: int = 0
    session_total: int = 0
    current_name: str = ""
    status: str = "就绪"
    output_path: str = ""


class ProgressReporter(Protocol):
    def update(self, state: ProgressState) -> None: ...

    def log(self, message: str) -> None: ...


@dataclass
class ConsoleProgress:
    _last_status: str = field(default="", init=False)

    def update(self, state: ProgressState) -> None:
        line = (
            f"[{config.APP_BRAND}] [{state.session}] 今日 {state.daily_done}/{state.daily_target} | "
            f"本次 {state.session_done}/{state.session_total} | {state.status}"
        )
        if line != self._last_status:
            print(line)
            self._last_status = line

    def log(self, message: str) -> None:
        print(f"[{config.APP_BRAND}] {message}")


@dataclass
class CallbackProgress:
    on_update: Callable[[ProgressState], None]
    on_log: Callable[[str], None]

    def update(self, state: ProgressState) -> None:
        self.on_update(state)

    def log(self, message: str) -> None:
        self.on_log(message)
