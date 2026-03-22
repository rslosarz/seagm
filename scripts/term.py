"""ANSI terminal styling for CLI scripts (respect NO_COLOR, TTY)."""

from __future__ import annotations

import os
import sys

BANNER_WIDTH = 52


class Term:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _c(self, code: str, s: str) -> str:
        if not self.enabled:
            return s
        return f"\033[{code}m{s}\033[0m"

    def bold(self, s: str) -> str:
        return self._c("1", s)

    def dim(self, s: str) -> str:
        return self._c("2", s)

    def green(self, s: str) -> str:
        return self._c("32", s)

    def red(self, s: str) -> str:
        return self._c("31", s)

    def yellow(self, s: str) -> str:
        return self._c("33", s)

    def cyan(self, s: str) -> str:
        return self._c("36", s)


def use_color(*, no_color_flag: bool = False) -> bool:
    if no_color_flag:
        return False
    if os.environ.get("NO_COLOR", "").strip():
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    return sys.stdout.isatty()


def print_run_header(term: Term, title: str) -> None:
    line = term.dim("━" * BANNER_WIDTH)
    print(line)
    print(f"  {term.bold(term.cyan(title))}")
    print(line)


def print_run_footer(term: Term) -> None:
    print(term.dim("━" * BANNER_WIDTH))
