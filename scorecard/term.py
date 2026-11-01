"""Small helpers for readable terminal output on Windows, macOS and Linux."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap

if os.name == "nt":  # turn on ANSI colors in Windows terminals
    os.system("")

_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def bold(t): return _c("1", t)
def dim(t): return _c("2", t)
def green(t): return _c("32", t)
def red(t): return _c("31", t)
def yellow(t): return _c("33", t)
def purple(t): return _c("35", t)


def width() -> int:
    return max(50, min(88, shutil.get_terminal_size((80, 20)).columns))


def rule(title: str = "") -> None:
    w = width()
    if title:
        print(purple("── ") + bold(title) + " " + purple("─" * max(2, w - len(title) - 4)))
    else:
        print(purple("─" * w))


def box(text: str) -> None:
    w = width() - 4
    lines = []
    for para in text.splitlines():
        lines += textwrap.wrap(para, w) or [""]
    print(dim("┌" + "─" * (w + 2) + "┐"))
    for ln in lines:
        print(dim("│ ") + ln.ljust(w) + dim(" │"))
    print(dim("└" + "─" * (w + 2) + "┘"))


def mark(ok: bool) -> str:
    return green("PASS") if ok else red("FAIL")


def copy_to_clipboard(text: str) -> bool:
    """Copy text to the clipboard if the OS has a tool for it."""
    candidates = []
    if os.name == "nt":
        candidates.append(["clip"])
    elif sys.platform == "darwin":
        candidates.append(["pbcopy"])
    else:
        candidates += [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            try:
                data = text.encode("utf-16") if cmd[0] == "clip" else text.encode()
                subprocess.run(cmd, input=data, check=True, timeout=5)
                return True
            except Exception:  # noqa: BLE001
                continue
    return False


def ask(question: str, default: str = "") -> str:
    try:
        answer = input(question)
    except EOFError:
        return default
    return answer.strip() or default
