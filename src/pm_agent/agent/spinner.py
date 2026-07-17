"""TTY 下 LLM 等待同行 spinner（非 TTY 空操作）。"""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TextIO

_FRAMES = "|/-\\"
_INTERVAL_S = 0.08


class _LlmSpinner:
    """在已打印的 thinking 行末尾轮转 |/-\\；stop 时擦除并换行。"""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._wrote = False
        self._lock = threading.Lock()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="llm-spinner", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        i = 0
        while not self._stop.is_set():
            frame = _FRAMES[i % len(_FRAMES)]
            with self._lock:
                if self._wrote:
                    self._stream.write(f"\b{frame}")
                else:
                    self._stream.write(frame)
                    self._wrote = True
                self._stream.flush()
            i += 1
            if self._stop.wait(_INTERVAL_S):
                break

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        with self._lock:
            if self._wrote:
                self._stream.write("\b \b")
                self._wrote = False
            self._stream.write("\n")
            self._stream.flush()


@contextmanager
def llm_spinner(
    *,
    enabled: bool | None = None,
    stream: TextIO | None = None,
) -> Iterator[None]:
    """LLM 阻塞期间同行动画；enabled 默认跟随 stream.isatty()。"""
    out = stream if stream is not None else sys.stdout
    active = out.isatty() if enabled is None else enabled
    if not active:
        yield
        return

    spinner = _LlmSpinner(out)
    spinner.start()
    try:
        yield
    finally:
        spinner.stop()
