"""Single shared console and the ASCII/Unicode charset toggle.

CLAUDE.md asks for ASCII-safe output by default, with Unicode as an opt-in via
`--unicode`. Renderers draw through `CHARS` rather than hardcoding glyphs, so
one switch changes every chart.
"""

from dataclasses import dataclass

from rich import box as _box
from rich.box import Box
from rich.console import Console

console = Console()
# Warnings go to stderr so they never land in a redirected report or a pipe.
err_console = Console(stderr=True)


def warn(message: str, hint: str | None = None) -> None:
    """Print a non-fatal warning to stderr."""
    err_console.print(f"[yellow]Warning:[/yellow] {message}")
    if hint:
        err_console.print(f"[dim]{hint}[/dim]")


@dataclass(frozen=True)
class Charset:
    name: str
    # Bars
    bar: str                # solid bar body
    frac: str               # fractional tails, coarse -> fine (index 0 unused)
    empty: str              # unfilled remainder of a fixed-width bar
    spark: str              # sparkline ramp, low -> high
    density: str            # heatmap/calendar ramp, none -> high
    # Marks
    dot: str                # scatter point
    milestone: str          # zero-length event
    # Box drawing
    h: str
    v: str
    corner: str
    arrow: str
    trend_up: str
    trend_down: str
    # Typography
    dash: str               # range separator, e.g. 0-10
    emdash: str             # "no value" / separator
    bullet: str             # inline separator
    times: str              # multiplication, e.g. week x weekday
    # Box plot
    whisker: str
    fence: str
    box_left: str
    box_right: str
    median: str

    def bar_of(self, value: float, max_value: float, width: int) -> str:
        """A proportional bar, using fractional glyphs when available."""
        if max_value <= 0 or width <= 0:
            return ""
        steps = len(self.frac) or 1
        units = int(value / max_value * width * steps)
        full, part = divmod(units, steps)
        out = self.bar * full
        if part and self.frac:
            out += self.frac[part]
        return out

    def gauge(self, fraction: float, width: int) -> str:
        """A fixed-width [####----] style bar."""
        filled = max(0, min(width, int(fraction * width)))
        return self.bar * filled + self.empty * (width - filled)

    def ramp(self, fraction: float) -> str:
        """Pick a density glyph for a 0..1 fraction."""
        if fraction <= 0:
            return self.density[0]
        idx = min(len(self.density) - 1, int(fraction * (len(self.density) - 1)) + 1)
        return self.density[idx]


ASCII = Charset(
    name="ascii",
    bar="#", frac="", empty="-", spark=".:-=+*#%", density=" .+*#",
    dot="o", milestone="*",
    h="-", v="|", corner="+", arrow="->", trend_up="^", trend_down="v",
    dash="-", emdash="-", bullet="*", times="x",
    whisker="-", fence="=", box_left="[", box_right="]", median="|",
)

UNICODE = Charset(
    name="unicode",
    bar="█", frac=" ▏▎▍▌▋▊▉", empty="░", spark="▁▂▃▄▅▆▇█", density=" ·+*█",
    dot="◆", milestone="◆",
    h="─", v="│", corner="└", arrow="→", trend_up="↑", trend_down="↓",
    dash="–", emdash="—", bullet="·", times="×",
    whisker="─", fence="═", box_left="┠", box_right="┨", median="┃",
)

CHARS: Charset = ASCII
DATE_FORMAT: str = "%Y-%m-%d"


def set_charset(use_unicode: bool) -> None:
    """Select the active charset. Called once from the CLI callback."""
    global CHARS
    CHARS = UNICODE if use_unicode else ASCII


def set_date_format(fmt: str) -> None:
    """Set how dates are displayed. Called once from the CLI callback."""
    global DATE_FORMAT
    DATE_FORMAT = fmt


def date_format() -> str:
    return DATE_FORMAT


def charset() -> Charset:
    """The active charset. Call this at render time, not at import time."""
    return CHARS


# `box.SIMPLE_HEAD` draws its header underline with a Unicode dash; this is the
# same shape in plain ASCII.
ASCII_SIMPLE_HEAD = Box(
    "    \n"
    "    \n"
    " -- \n"
    "    \n"
    "    \n"
    "    \n"
    "    \n"
    "    \n"
)

ASCII_SIMPLE = Box(
    "    \n"
    "    \n"
    " -- \n"
    "    \n"
    "    \n"
    " -- \n"
    "    \n"
    "    \n"
)


def table_box(heavy: bool = False):
    """The table box style matching the active charset."""
    if CHARS is UNICODE:
        return _box.SIMPLE if heavy else _box.SIMPLE_HEAD
    return ASCII_SIMPLE if heavy else ASCII_SIMPLE_HEAD


def overflow_mode() -> str:
    """Rich hardcodes a Unicode ellipsis when truncating, so ASCII mode folds instead."""
    return "ellipsis" if CHARS is UNICODE else "fold"
