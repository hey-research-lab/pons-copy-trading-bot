from __future__ import annotations

import sys
from datetime import datetime, timezone


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _write(level: str, message: str, extra: object | None = None) -> None:
    line = f"[{_stamp()}] {level.upper():<5} {message}"
    stream = sys.stderr if level == "error" else sys.stdout
    if extra is not None:
        print(line, extra, file=stream, flush=True)
        return
    print(line, file=stream, flush=True)


class _Log:
    def debug(self, message: str, extra: object | None = None) -> None:
        _write("debug", message, extra)

    def info(self, message: str, extra: object | None = None) -> None:
        _write("info", message, extra)

    def warn(self, message: str, extra: object | None = None) -> None:
        _write("warn", message, extra)

    def error(self, message: str, extra: object | None = None) -> None:
        _write("error", message, extra)


log = _Log()
